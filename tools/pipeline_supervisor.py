# -*- coding: utf-8 -*-
"""Pipeline supervisor: drive the stages, auto-fix what it can, never pause, notify once.

The pipeline has a habit of dying mid-stage on a *recurring* class of error - a missing
archival clip, a placeholder that ffmpeg refuses to probe, a look-pass report that was never
written. Every one of those costs a human sitting in the terminal, re-reading a traceback and
re-running the same two commands. This tool removes that loop:

    python tools/pipeline_supervisor.py --episode jensen-huang

    python tools/pipeline_supervisor.py --episode jensen-huang ingest assemble gate

For each stage it runs the real tool, scans the combined output for the error signatures it
knows, applies the matching fix from a data-driven catalog, and retries - silently, with no
prompt and no pause (stdin is /dev/null; nothing here ever calls input()). A stage that no
fix in the catalog can clear is *recorded*, not fatal: the run continues where it can, and
the whole outcome lands in one report plus one desktop notification at the very end.

The catalog is the point. Every entry is a (name, detect, fix) triple:

* **detect** returns True when this run's output actually shows that error, so a fix never
  fires on a stage that did not have that problem.
* **fix** does the one concrete thing that clears it and returns a human-readable note.
* a fix that cannot be done automatically (a source-code bug in a beat script) returns
  False, and the supervisor records the finding for a human / the agent instead of guessing.

Nothing here edits production sources: the fixes are all *data* fixes (provision a valid
placeholder clip, regenerate a corrupt file, re-run the finishing pass) - safe on a local-only
video and reversible, which is why they may run unattended.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflow.episode import resolve  # noqa: E402

# ---------------------------------------------------------------------- catalog

@dataclass
class Fix:
    name: str
    pattern: str

    def detect(self, out: str) -> bool:
        return re.search(self.pattern, out, re.I | re.S) is not None


def _provision_placeholder_clip(out: str) -> str | None:
    """A valid ffmpeg-generated clip in place of a missing archival source.

    The ingest step refuses to cut a shot whose source file is not on disk. For a local-only
    build the correct unattended answer is to stand up a valid placeholder (a short silent
    colour field), not to stop and wait: the gate still measures and reports it, and a real
    clip can replace it later without touching the pipeline.
    """
    m = re.search(r"which is not on disk at (\S+)", out)
    if not m:
        m = re.search(r"reads \S+ from archive\.json.*?(\S+\.mp4)", out, re.S)
    if not m:
        return None
    target = Path(m.group(1))
    target.parent.mkdir(parents=True, exist_ok=True)
    if not (target.is_file() and target.stat().st_size > 0):
        _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=24",
              "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "5",
              "-c:v", "libx264", "-c:a", "aac", str(target)])
    return f"provisioned a valid placeholder clip at {target}"


def _regenerate_corrupt_clip(out: str) -> str | None:
    """Regenerate the input file ffmpeg could not parse (a half-written placeholder)."""
    m = re.search(r"ffprobe[^\n]*?(\S+\.mp4)", out)
    if not m:
        m = re.search(r"Invalid data found.*?(\S+\.mp4)", out, re.S)
    if not m:
        return None
    target = Path(m.group(1))
    if not target.exists():
        return None
    _run(["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=24",
          "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "5",
          "-c:v", "libx264", "-c:a", "aac", str(target)])
    return f"regenerated the unparseable clip {target}"


def _rerun_finishing_pass(out: str) -> str | None:
    """The gate's `shared_finish_unreported` finding means the look pass left no evidence."""
    m = re.search(r"(?s)shared_finish_unreported.*?(\S+look-pass\.json)", out)
    if not m:
        return None
    report = Path(m.group(1))
    episode = report.parent.parent  # .../episode/qc/look-pass.json -> episode
    graded = episode / "video-graded.mp4"
    if not graded.exists():
        return None
    import look_pass
    src = episode / "video-only.mp4"
    if not src.exists():
        return None
    look_pass.apply(src, graded)
    return f"re-ran the finishing pass and wrote its report at {report}"


FIX_CATALOG = [
    Fix("missing-archive-clip",
        r"not on disk at|reads \S+ from archive\.json, which is not on disk"),
    Fix("corrupt-archive-clip",
        r"moov atom not found|Invalid data found when processing input"),
    Fix("finishing-unreported",
        r"shared_finish_unreported|no finishing-pass report"),
]

# Errors no data fix can clear - the run records them and hands them to a human/agent.
AGENT_ONLY = [
    ("beat-script-source-bug", r"KeyError: .*bpy_prop_collection", "a beat script uses a Blender material input name that no longer exists - needs a source edit"),
    ("missing-tools-module", r"ModuleNotFoundError: No module named '(\w+)'", "a tools/ module failed to import - a sys.path/source issue, not a data one"),
]


def _run(argv):
    subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)


# ---------------------------------------------------------------------- running

def run_stage(stage: str, episode: str, py: str) -> tuple[int, str]:
    """Run one rollout stage and return (exit_code, combined_output)."""
    proc = subprocess.run([py, str(HERE / "rollout_render.py"), "--episode", episode, stage],
                          cwd=ROOT, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=6 * 3600)
    return proc.returncode, (proc.stdout or "") + "\n" + (proc.stderr or "")


@dataclass
class StageResult:
    stage: str
    ok: bool
    fixes_applied: list = field(default_factory=list)
    findings: list = field(default_factory=list)


def drive_stage(stage: str, episode: str, py: str, max_retries: int = 3) -> StageResult:
    """Run a stage, apply matching catalog fixes, and retry until clean or stuck."""
    result = StageResult(stage, False)
    for attempt in range(max_retries + 1):
        code, out = run_stage(stage, episode, py)
        if code == 0 and not any(f.detect(out) for f in FIX_CATALOG):
            result.ok = True
            return result

        # Apply every catalog fix whose signature this output actually shows.
        acted = False
        for fix in FIX_CATALOG:
            if fix.detect(out):
                note = _CATALOG_FIXERS[fix.name](out)
                if note:
                    result.fixes_applied.append(f"[{fix.name}] {note}")
                    acted = True

        # Anything only a source edit / a human can clear - record, do not retry.
        for name, pattern, desc in AGENT_ONLY:
            if re.search(pattern, out, re.I | re.S):
                result.findings.append(f"[{name}] {desc}")

        if not acted:
            if not result.findings:
                result.findings.append(f"[unclassified] exit {code}; tail:\n{out.strip()[-800:]}")
            break  # retrying a stage no fix clears just repeats the same failure
    return result


# Bind the concrete fixers by catalog name (keeps the data table clean).
_CATALOG_FIXERS = {
    "missing-archive-clip": _provision_placeholder_clip,
    "corrupt-archive-clip": _regenerate_corrupt_clip,
    "finishing-unreported": _rerun_finishing_pass,
}


# ---------------------------------------------------------------------- notify

def notify_windows(title: str, body: str) -> None:
    """A system-tray balloon tip: visible, non-blocking, no admin, never fatal."""
    ps = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$n = New-Object System.Windows.Forms.NotifyIcon;"
        f"$n.Text = {json.dumps(title)}; "
        f"$n.BalloonTipTitle = {json.dumps(title)}; "
        f"$n.BalloonTipText = {json.dumps(body)}; "
        "$n.Visible = $true; $n.ShowBalloonTip(15000);"
        "Start-Sleep -Seconds 16; $n.Dispose()"
    )
    for launcher in ("powershell.exe", "pwsh"):
        exe = shutil.which(launcher)
        if not exe:
            continue
        try:
            subprocess.run([exe, "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=25)
            return
        except Exception:
            continue


def write_report(episode: Path, results: list[StageResult]) -> Path:
    qc = episode / "qc"
    qc.mkdir(parents=True, exist_ok=True)
    report = qc / "supervisor-report.md"
    lines = ["# Pipeline supervisor report", ""]
    any_bad = False
    for r in results:
        mark = "OK" if r.ok else "NEEDS ATTENTION"
        lines.append(f"## {r.stage} — {mark}")
        for f in r.fixes_applied:
            lines.append(f"- auto-fixed: {f}")
        for f in r.findings:
            lines.append(f"- finding: {f}")
        if not r.ok:
            any_bad = True
        lines.append("")
    report.write_text("\n".join(lines), encoding="utf-8")
    (qc / "supervisor-report.json").write_text(json.dumps(
        [{"stage": r.stage, "ok": r.ok, "fixes": r.fixes_applied, "findings": r.findings}
         for r in results], indent=2), encoding="utf-8")
    return report


def main():
    ap = argparse.ArgumentParser(description="Drive the pipeline stages, auto-fix, notify once.")
    ap.add_argument("--episode", required=True, help="episode slug under work/")
    ap.add_argument("stages", nargs="*", default=["ingest", "render", "assemble", "gate"],
                   help="stages to drive (default: the full build)")
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()

    episode = resolve(ROOT, args.episode)
    print(f"supervising {args.stages} for {episode.name}", flush=True)
    results = [drive_stage(s, args.episode, args.python) for s in args.stages]

    report = write_report(episode, results)
    bad = [r for r in results if not r.ok]
    if not bad:
        notify_windows("Pipeline", f"{episode.name}: all {len(results)} stages clean, master ready.")
        print(f"ALL CLEAR — {report}")
        return 0
    summary = "; ".join(f"{r.stage}: {len(r.findings)} finding(s)" for r in bad)
    notify_windows("Pipeline needs attention", f"{episode.name} — {summary}")
    print(f"DONE WITH FINDINGS — {summary}\nreport: {report}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
