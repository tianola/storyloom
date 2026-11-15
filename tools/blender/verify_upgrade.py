import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "work/blender-upgrade"
SCRIPT = ROOT / "tools/blender/verification_beat.py"
BLENDERS = {
    "blender-4.1": ROOT / "tools/blender-4.1.0-windows-x64/blender.exe",
    "blender-4.5": ROOT / "tools/blender-4.5.15-windows-x64/blender.exe",
}
ERROR_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"EEVEE.*(?:error|fail)",
        r"(?:error|fail).*EEVEE",
        r"(?:OpenGL|GPU|driver).*(?:error|fail|not supported)",
        r"(?:error|fail|not supported).*(?:OpenGL|GPU|driver)",
        r"Unable to open a display",
    )
)


def relative(path):
    return path.relative_to(ROOT).as_posix()


def driver_errors(log_text):
    return [
        line.strip()
        for line in log_text.splitlines()
        if any(pattern.search(line) for pattern in ERROR_PATTERNS)
    ]


def render(name, executable):
    png = OUTPUT / f"{name}.png"
    log_path = OUTPUT / f"{name}.log"
    command = [
        str(executable),
        "--background",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "--python",
        str(SCRIPT),
        "--",
        "--output",
        str(png),
    ]
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            check=False,
        )
        returncode = completed.returncode
        log_text = completed.stdout
    except (OSError, subprocess.TimeoutExpired) as exc:
        returncode = -1
        log_text = f"Host subprocess failure: {type(exc).__name__}: {exc}\n"
        if isinstance(exc, subprocess.TimeoutExpired) and exc.stdout:
            output = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout
            log_text = output + log_text
    elapsed = time.perf_counter() - started
    log_path.write_text(log_text, encoding="utf-8")
    version_match = re.search(r"^BLENDER_VERSION:\s*(.+)$", log_text, re.MULTILINE)
    engine_match = re.search(r"^BLENDER_ENGINE:\s*(.+)$", log_text, re.MULTILINE)
    return {
        "version": version_match.group(1).strip() if version_match else "unknown",
        "executable": relative(executable),
        "command": command,
        "returncode": returncode,
        "output": relative(png),
        "output_bytes": png.stat().st_size if png.is_file() else 0,
        "elapsed_seconds": round(elapsed, 3),
        "log": relative(log_path),
        "engine": engine_match.group(1).strip() if engine_match else "unknown",
        "driver_errors": driver_errors(log_text),
    }


def render_succeeded(result):
    return result["returncode"] == 0 and result["output_bytes"] > 0 and not result["driver_errors"]


def create_comparison():
    output = OUTPUT / "comparison.png"
    log_path = OUTPUT / "comparison.log"
    command = [
        shutil.which("ffmpeg") or "ffmpeg",
        "-y",
        "-i",
        str(OUTPUT / "blender-4.1.png"),
        "-i",
        str(OUTPUT / "blender-4.5.png"),
        "-filter_complex",
        "hstack=inputs=2",
        "-frames:v",
        "1",
        str(output),
    ]
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    elapsed = time.perf_counter() - started
    log_path.write_text(completed.stdout, encoding="utf-8")
    return {
        "command": command,
        "returncode": completed.returncode,
        "output": relative(output),
        "output_bytes": output.stat().st_size if output.is_file() else 0,
        "elapsed_seconds": round(elapsed, 3),
        "log": relative(log_path),
    }


def successful_report(report):
    return (
        report.get("success") is True
        and all(render_succeeded(report.get("renders", {}).get(name, {})) for name in BLENDERS)
        and report.get("comparison", {}).get("returncode") == 0
        and report.get("comparison", {}).get("output_bytes", 0) > 0
        and (OUTPUT / "comparison.png").stat().st_size > 0
    )


def accept(report):
    if not successful_report(report):
        raise RuntimeError("Cannot accept Blender 4.5 without a complete successful same-beat report")
    production = "tools/blender-4.5.15-windows-x64/blender.exe"
    config = ROOT / "workflow/blender.json"
    config.write_text(json.dumps({"production": production}, indent=2) + "\n", encoding="utf-8")
    print(f"Accepted after external visual inspection: {relative(config)}")
    print(json.dumps(json.loads(config.read_text(encoding="utf-8")), indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--accept", action="store_true")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT / "report.json"

    if args.accept:
        if not report_path.is_file():
            raise RuntimeError("Cannot accept Blender 4.5 without an existing successful report")
        accept(json.loads(report_path.read_text(encoding="utf-8")))
        return 0

    renders = {name: render(name, executable) for name, executable in BLENDERS.items()}
    if all(render_succeeded(result) for result in renders.values()):
        comparison = create_comparison()
    else:
        comparison = {
            "returncode": None,
            "output": "work/blender-upgrade/comparison.png",
            "output_bytes": (OUTPUT / "comparison.png").stat().st_size if (OUTPUT / "comparison.png").is_file() else 0,
            "elapsed_seconds": 0.0,
            "error": "Comparison not run because at least one render failed",
        }
    report = {
        "success": all(render_succeeded(result) for result in renders.values())
        and comparison["returncode"] == 0
        and comparison["output_bytes"] > 0,
        "versions": {name: result["version"] for name, result in renders.items()},
        "renders": renders,
        "comparison": comparison,
        "visual_inspection": "required before --accept",
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["success"]:
        return 1
    print(f"Render gate passed. Read {relative(OUTPUT / 'comparison.png')} before running --accept.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, KeyError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
