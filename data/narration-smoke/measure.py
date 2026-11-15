"""Measure the narration CLI on this machine: wall/CPU time, peak memory, WAV probes.

Run from the project root with the project venv:
    .venv/Scripts/python.exe data/narration-smoke/measure.py

Writes report.json next to this file. Nothing here is imported by production code.
"""

import ctypes
import json
import os
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe"
NARRATE = ROOT / "python" / "narrate.py"
MODEL = ROOT / "models" / "kokoro" / "kokoro-v1.0.onnx"
VOICES = ROOT / "models" / "kokoro" / "voices-v1.0.bin"
OUT = HERE

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010


class ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_uint32),
        ("PageFaultCount", ctypes.c_uint32),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


class ProcessEntry32(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("cntUsage", ctypes.c_uint32),
        ("th32ProcessID", ctypes.c_uint32),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", ctypes.c_uint32),
        ("cntThreads", ctypes.c_uint32),
        ("th32ParentProcessID", ctypes.c_uint32),
        ("pcPriClassBase", ctypes.c_int32),
        ("dwFlags", ctypes.c_uint32),
        ("szExeFile", ctypes.c_char * 260),
    ]


def _mb(value):
    return round(value / 1048576, 1) if value else None


def own_peak_working_set_mb() -> float:
    psapi = ctypes.WinDLL("psapi")
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(ProcessMemoryCounters)
    if not psapi.GetProcessMemoryInfo(ctypes.c_void_p(-1), ctypes.byref(counters), counters.cb):
        return None
    return _mb(int(counters.PeakWorkingSetSize))


def snapshot_children(kernel32):
    """Map parent pid -> child pids for the whole machine, one snapshot."""
    TH32CS_SNAPPROCESS = 0x2
    INVALID = ctypes.c_void_p(-1).value
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap in (None, INVALID):
        return {}
    try:
        entry = ProcessEntry32()
        entry.dwSize = ctypes.sizeof(ProcessEntry32)
        children = {}
        if not kernel32.Process32First(snap, ctypes.byref(entry)):
            return {}
        while True:
            children.setdefault(entry.th32ParentProcessID, []).append(entry.th32ProcessID)
            if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                break
        return children
    finally:
        kernel32.CloseHandle(snap)


def tree_pids(kernel32, root_pid: int) -> set:
    children = snapshot_children(kernel32)
    found, queue = {root_pid}, [root_pid]
    while queue:
        for child in children.get(queue.pop(), ()):
            if child not in found:
                found.add(child)
                queue.append(child)
    return found


def observe_tree(root_pid: int, result: dict, stop: threading.Event):
    """Poll the child process tree for CPU time and working set.

    The venv ``python.exe`` on this machine is a launcher stub: it spawns the real
    interpreter as a child, so measuring only Popen.pid reports the stub (4.8 MB).
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(ProcessMemoryCounters)
    per_pid_peak = {}
    per_pid_cpu = {}
    simultaneous_peak_bytes = 0
    handles = {}

    def read_process(pid, handle):
        nonlocal simultaneous_peak_bytes
        resident = 0
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            per_pid_peak[pid] = max(per_pid_peak.get(pid, 0), int(counters.PeakWorkingSetSize))
            resident = int(counters.WorkingSetSize)
        creation = ctypes.c_ulonglong()
        exited = ctypes.c_ulonglong()
        kernel = ctypes.c_ulonglong()
        user = ctypes.c_ulonglong()
        if kernel32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exited),
                                    ctypes.byref(kernel), ctypes.byref(user)):
            per_pid_cpu[pid] = (kernel.value + user.value) / 10_000_000
        return resident

    try:
        while not stop.is_set():
            resident_total = 0
            for pid in tree_pids(kernel32, root_pid):
                if pid not in handles:
                    handles[pid] = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, 0, pid) or False
                if handles[pid]:
                    resident_total += read_process(pid, handles[pid])
            simultaneous_peak_bytes = max(simultaneous_peak_bytes, resident_total)
            stop.wait(0.02)
        # Exited children stay readable through their cached handle: capture final values.
        for pid, handle in handles.items():
            if handle:
                read_process(pid, handle)
        result["processes_seen"] = sorted(set(per_pid_peak) | set(per_pid_cpu))
        result["cpu_seconds"] = round(sum(per_pid_cpu.values()), 3)
        result["peak_working_set_bytes_sum_of_per_process_peaks"] = sum(per_pid_peak.values())
        result["peak_resident_set_bytes_simultaneous"] = simultaneous_peak_bytes
    finally:
        for handle in handles.values():
            if handle:
                kernel32.CloseHandle(handle)


def pip_field(distribution: str, field: str) -> str:
    text = subprocess.run([str(VENV_PY), "-m", "pip", "show", distribution],
                          capture_output=True, text=True, check=True).stdout
    for line in text.splitlines():
        if line.startswith(field + ":"):
            return line.split(":", 1)[1].strip()
    return ""


def probe(path: Path) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    stream = data["streams"][0]
    return {
        "file": path.name,
        "codec_name": stream.get("codec_name"),
        "sample_rate": stream.get("sample_rate"),
        "channels": stream.get("channels"),
        "duration_seconds": float(stream.get("duration") or data["format"].get("duration") or 0.0),
        "bit_rate": stream.get("bit_rate"),
    }


OFFLINE_SHIM = '''"""Imported by the child interpreter through PYTHONPATH: refuses any network use."""
import os
import socket

MARKER = os.environ["SMOKE_NETMARKER"]


def _trip(what):
    with open(MARKER, "a", encoding="utf-8") as handle:
        handle.write(what + "\\n")
    raise OSError(f"network disabled by narration smoke harness: {what}")


class _BlockedSocket(socket.socket):
    def __init__(self, *args, **kwargs):
        _trip(f"socket({args!r})")


socket.socket = _BlockedSocket
socket.create_connection = lambda *args, **kwargs: _trip(f"create_connection({args!r})")
socket.getaddrinfo = lambda *args, **kwargs: _trip(f"getaddrinfo({args!r})")
socket.gethostbyname = lambda *args, **kwargs: _trip(f"gethostbyname({args!r})")
'''


def run_offline_guarded() -> dict:
    """Re-run the CLI with socket creation blocked, proving synthesis is local-only."""
    import shutil
    import tempfile

    sandbox = Path(tempfile.mkdtemp(prefix="narration-offline-"))
    marker = sandbox / "attempts.txt"
    (sandbox / "sitecustomize.py").write_text(OFFLINE_SHIM, encoding="utf-8")
    out_dir = sandbox / "out"
    shutil.copy(HERE / "request.json", sandbox / "request.json")
    guarded = [str(VENV_PY), str(NARRATE), "--input", str(sandbox / "request.json"),
               "--output", str(out_dir), "--model", str(MODEL), "--voices", str(VOICES)]
    env = {**os.environ, "PYTHONPATH": str(sandbox), "SMOKE_NETMARKER": str(marker)}
    start = time.perf_counter()
    proc = subprocess.run(guarded, cwd=ROOT, env=env, capture_output=True, text=True)
    wall = time.perf_counter() - start
    attempts = marker.read_text(encoding="utf-8").splitlines() if marker.exists() else []
    produced = sorted(p.name for p in out_dir.iterdir()) if out_dir.exists() else []
    shutil.rmtree(sandbox, ignore_errors=True)
    return {
        "command": " ".join(f'"{p}"' if " " in p else p for p in guarded),
        "exit": proc.returncode,
        "wall_seconds": round(wall, 3),
        "network_attempts": attempts,
        "files_produced": produced,
        "stderr_tail": proc.stderr.strip().splitlines()[-1:],
    }


def main() -> int:
    report = {"commands": [], "python": sys.version.split()[0]}
    request = HERE / "request.json"
    cmdline = [str(VENV_PY), str(NARRATE), "--input", str(request), "--output", str(OUT),
               "--model", str(MODEL), "--voices", str(VOICES)]
    report["commands"].append(" ".join(f'"{p}"' if " " in p else p for p in cmdline))

    # Two cold runs: the second one exposes run-to-run drift in sample counts.
    runs = []
    for _ in range(2):
        observed = {}
        stop = threading.Event()
        start = time.perf_counter()
        proc = subprocess.Popen(cmdline, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        watcher = threading.Thread(target=observe_tree, args=(proc.pid, observed, stop), daemon=True)
        watcher.start()
        stdout, stderr = proc.communicate()
        stop.set()
        watcher.join(timeout=30)
        wall = time.perf_counter() - start
        runs.append({
            "exit": proc.returncode,
            "wall_seconds": round(wall, 3),
            "tree_cpu_seconds": observed.get("cpu_seconds"),
            "tree_peak_working_set_mb": _mb(observed.get("peak_working_set_bytes_sum_of_per_process_peaks")),
            "tree_peak_resident_mb": _mb(observed.get("peak_resident_set_bytes_simultaneous")),
            "tree_process_ids": observed.get("processes_seen"),
            "observer_error": observed.get("error"),
            "stdout": stdout.strip(),
            "stderr": stderr.strip(),
            "manifest_total_samples": (
                json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))["totalSamples"]
                if proc.returncode == 0 else None),
        })
    report["cli_runs"] = runs
    run = runs[-1]
    wall = run["wall_seconds"]
    if run["exit"] != 0:
        report["fatal"] = "CLI exited nonzero"
        (HERE / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 1

    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    probes, independent_total, mismatches = [], 0, []
    for entry in manifest["utterances"]:
        path = OUT / entry["file"]
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            independent_total += frames
            if frames != entry["samples"]:
                mismatches.append({"id": entry["id"], "wav_frames": frames,
                                   "manifest_samples": entry["samples"]})
            if handle.getframerate() != manifest["sampleRate"]:
                mismatches.append({"id": entry["id"], "wav_rate": handle.getframerate()})
            if (handle.getnchannels(), handle.getsampwidth(), handle.getcomptype()) != (1, 2, "NONE"):
                mismatches.append({"id": entry["id"],
                                   "wav_shape": [handle.getnchannels(), handle.getsampwidth(),
                                                 handle.getcomptype()]})
        probes.append(probe(path))
    audio_seconds = manifest["totalSamples"] / manifest["sampleRate"]
    report["manifest"] = manifest
    report["ffprobe"] = probes
    report["cross_check"] = {
        "manifest_total_samples": manifest["totalSamples"],
        "independent_wav_frame_sum": independent_total,
        "ffprobe_sum_seconds": round(sum(p["duration_seconds"] for p in probes), 6),
        "manifest_seconds": round(audio_seconds, 6),
        "cold_run_total_samples": [r["manifest_total_samples"] for r in runs],
        "mismatches": mismatches,
    }
    report["offline_guard"] = run_offline_guarded()

    # In-process breakdown: the CLI number includes model load; this separates the two.
    sys.path.insert(0, str(ROOT / "python"))
    import narrate

    t0 = time.perf_counter()
    cpu0 = time.process_time()
    engine = narrate.load_engine(MODEL, VOICES)
    load_seconds = time.perf_counter() - t0
    load_cpu = time.process_time() - cpu0
    voice_names = list(engine.get_voices())
    per_utterance = []
    for entry in manifest["utterances"]:
        t1 = time.perf_counter()
        c1 = time.process_time()
        audio, rate = engine.create(entry["text"], manifest["voice"], speed=1.0)
        per_utterance.append({"id": entry["id"], "text_chars": len(entry["text"]),
                              "seconds": round(time.perf_counter() - t1, 3),
                              "cpu_seconds": round(time.process_time() - c1, 3),
                              "samples": len(audio), "sample_rate": rate})
    synth_seconds = sum(u["seconds"] for u in per_utterance)
    import onnxruntime

    report["engine"] = {
        "kokoro_onnx_version": pip_field("kokoro-onnx", "Version"),
        "onnxruntime_version": pip_field("onnxruntime", "Version"),
        "available_providers": onnxruntime.get_available_providers(),
        "voices_installed_total": len(voice_names),
        "english_voices_installed": sorted(v for v in voice_names if v[:2] in ("af", "am", "bf", "bm")),
        "requested_voice_present": manifest["voice"] in voice_names,
        "model_load_seconds": round(load_seconds, 3),
        "model_load_cpu_seconds": round(load_cpu, 3),
        "own_peak_working_set_mb_after_synthesis": own_peak_working_set_mb(),
        "per_utterance": per_utterance,
        "run_to_run_drift_vs_cli_manifest": [
            {"id": in_process["id"], "cli_manifest_samples": cli["samples"],
             "in_process_samples": in_process["samples"]}
            for in_process, cli in zip(per_utterance, manifest["utterances"])
        ],
        "synth_seconds_excluding_model_load": round(synth_seconds, 3),
        "audio_seconds": round(audio_seconds, 3),
        "rtf_excluding_model_load": round(synth_seconds / audio_seconds, 3),
        "rtf_cli_end_to_end": round(wall / audio_seconds, 3),
    }
    (HERE / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"cli_runs": report["cli_runs"], "cross_check": report["cross_check"],
                      "engine": report["engine"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
