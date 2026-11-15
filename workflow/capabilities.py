"""The preflight gate: what this machine must have before an episode stage runs.

#138 audited the capabilities, #139 installed them, and both live in a session log — which is a
one-time event. A video build is the opposite: it repeats, and it takes hours. The failure mode this
closes has already bitten twice, and it is a stage dying 40 minutes into a render because a binary
had moved, a model snapshot had been cleaned out of the cache, or a wheel had half-downloaded and
still looked present in `pip list`.

So the registry is data (`workflow/capabilities.json`) and this module reads it on every run. Three
rules the file cannot express on its own, each earned by a measurement:

* `path` checks carry `min_bytes`. Existence is not wholeness — the 325 MB Kokoro weights are the
  artefact that can half-download and pass a bare `is_file()`.
* An `executable` candidate that carries a separator is checked where it is named, never through
  PATH. Tesseract is installed here at `C:/Program Files/Tesseract-OCR/tesseract.exe` and is not on
  PATH; a PATH-only probe calls a working tool missing, and a gate that cries wolf gets skipped.
* A module probe uses `importlib.util.find_spec` rather than `import`. `import onnxruntime` costs
  seconds and `import faster_whisper` drags ctranslate2 in behind it; a gate in front of every stage
  has to cost milliseconds.

Run it directly: `python -m workflow.capabilities [--phase vo]` — exit 1 when a required capability
fails, which is what `init_episode` uses as its stop.
"""

import json
import os
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from workflow.config import EPISODE_PHASES

CAPABILITIES_FILENAME = "capabilities.json"
CHECK_KINDS = ("path", "executable", "module", "blender")
REFUSED = 4  # free in every guarded stage: 1 is a failed run, 2 is bad usage, 3 a missing asset
_GLOB = re.compile(r"[*?\[]")


@dataclass(frozen=True)
class Finding:
    """One answer to one declared check, phrased so a human can act on it without reading this file."""

    capability: str
    ok: bool
    detail: str
    remediation: str
    required: bool


def capabilities(root: Path) -> dict:
    """The registry, loaded. Only the shape the gate needs is enforced here; the vocabulary rules
    live in `python/test_capabilities.py`, so a registry edit is caught by the suite and not by a run."""
    path = Path(root) / "workflow" / CAPABILITIES_FILENAME
    if not path.is_file():
        raise ValueError(f"{path} is missing - the preflight has nothing to check")
    registry = json.loads(path.read_text(encoding="utf-8"))
    missing = [key for key in ("name", "interpreters", "capabilities") if not registry.get(key)]
    if missing:
        raise ValueError(f"{path} is missing {missing}")
    for key, interpreter in registry["interpreters"].items():
        if not str(interpreter.get("python", "")).strip():
            raise ValueError(f"{path}: interpreter {key} declares no python executable")
    return registry


def resolve_path(root: Path, declared: str) -> Path:
    """Where a declared path actually is on this machine, right now.

    Three forms are accepted because the registry needs all three: repo-relative (the Kokoro
    weights), home-relative (the Hugging Face cache, which is not on the repo volume), and a
    pattern. The cache puts a revision hash mid-path, so a literal entry would rot the day the model
    is re-downloaded; a pattern resolves to the first matching file, and a pattern that matches
    nothing stays a pattern so the finding reads `missing` instead of raising.
    """
    path = _where(root, declared)
    if not _GLOB.search(str(path)):
        return path
    parts = path.parts
    first = next(index for index, part in enumerate(parts) if _GLOB.search(part))
    try:
        hits = sorted(p for p in Path(*parts[:first]).glob(str(Path(*parts[first:]))) if p.is_file())
    except OSError:
        return path
    return hits[0] if hits else path


def resolve_interpreter(root: Path, registry: dict, key: str) -> str:
    """The interpreter a `module` check runs against, forward-slashed so it prints usefully.

    `pipeline` is a bare name because it is found on PATH; `narration` is a repo-relative
    executable because the pinned venv is the only interpreter that can install that set at all.
    """
    declared = registry["interpreters"][key]["python"]
    return declared if not _is_path_like(declared) else _flat(_where(root, declared))


def module_probe_argv(python, name: str) -> list[str]:
    """The cheapest honest question about a package: is it findable, without importing it."""
    code = ("import importlib.util, sys; "
            "sys.exit(0 if importlib.util.find_spec(sys.argv[1]) is not None else 1)")
    return [str(python), "-c", code, name]


def executable_for(root: Path, capability_id: str, host=None) -> str | None:
    """The first candidate this machine actually has for `capability_id`, or None.

    Code that needs a binary asks the registry instead of hard-coding a path or calling a bare
    name. Tesseract is installed here and is not on PATH, so a `shutil.which` guess reports a
    working tool missing — and the ingest that mirrors an archival frame on the strength of an OCR
    answer must resolve the binary exactly the way the gate that requires it does, or the two
    disagree about whether the machine can read text at all.
    """
    host = host or RealHost()
    for capability in capabilities(root)["capabilities"]:
        if capability.get("id") != capability_id:
            continue
        for check in capability.get("checks", ()):
            if check.get("kind") != "executable":
                continue
            for candidate in check.get("any_of", ()):
                found = (Path(candidate) if _is_path_like(candidate)
                         else Path(host.which(candidate) or ""))
                if found.is_file():
                    return _flat(found)
        return None
    return None


class RealHost:
    """The questions asked of the machine this is running on."""

    def size(self, path):
        try:
            info = os.stat(path)
        except OSError:
            return None
        return info.st_size if stat.S_ISREG(info.st_mode) else None

    def which(self, name):
        return shutil.which(str(name))

    def module(self, python, name):
        """Whether `python` can find `name`, asked of the interpreter the registry named.

        A bare name is resolved here rather than left to the subprocess. On Windows CreateProcess
        searches the calling image's own directory before PATH, and every venv keeps a
        `python.exe` there, so a preflight run from inside a venv silently asks *that* venv about
        packages the registry's interpreter has. Measured: `which("python")` answered
        `C:\\Python314\\python.EXE` while the spawned child ran a uv-managed 3.12 and reported all
        five QC packages missing, which failed a required capability and made `init_episode` refuse
        a machine that could have built the episode. An interpreter this machine does not have is
        reported missing rather than spawned bare, for the same reason.
        """
        executable = str(python)
        if not os.path.isabs(executable):
            resolved = self.which(executable)
            if not resolved:
                return False
            executable = str(resolved)
        try:
            done = subprocess.run(module_probe_argv(executable, name), capture_output=True,
                                  timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            return False
        return done.returncode == 0

    def blender_executable(self, repo_root):
        from workflow.config import blender_executable

        path = blender_executable(Path(repo_root))
        return path if path.is_file() else None


def preflight(root: Path, *, phase: str | None = None, host=None) -> list[Finding]:
    """One finding per declared check per capability in scope. `phase` narrows the questions to the
    ones that stage actually asks, so `--phase vo` never spends a subprocess on Blender."""
    root = Path(root)
    if phase is not None and phase not in EPISODE_PHASES:
        raise ValueError(f"{phase!r} is not an episode phase; known phases are {list(EPISODE_PHASES)}")
    registry = capabilities(root)
    host = RealHost() if host is None else host
    findings = []
    for capability in registry["capabilities"]:
        if phase is not None and phase not in capability["phases"]:
            continue
        for check in capability["checks"]:
            findings.append(_evaluate(root, registry, capability, check, host))
    return findings


def required_failures(findings) -> list[Finding]:
    return [finding for finding in findings if finding.required and not finding.ok]


def stage_report(root: Path, phase: str, *, host=None) -> str | None:
    """None when the stage may run; otherwise the sentence that tells it to stop.

    Returning text rather than raising keeps each call site to three lines, lets every tool keep
    the exit convention it already has, and puts the stop *before* the work - which is the only
    reason the gate is worth running at all. A stage that has already spent thirty minutes in
    ffmpeg is not saved by a check that runs afterwards.
    """
    failures = required_failures(preflight(root, phase=phase, host=host))
    if not failures:
        return None
    return (f"preflight refused phase {phase}: required capabilities unavailable - "
            + ", ".join(sorted({finding.capability for finding in failures}))
            + "\n" + format_findings(failures))


def format_findings(findings) -> str:
    width = max((len(finding.capability) for finding in findings), default=0)
    rows = []
    for finding in findings:
        rows.append(f"{'PASS' if finding.ok else 'FAIL':4}  {finding.capability:<{width}}"
                    f"  {finding.detail}")
        if not finding.ok:
            rows.append(f"      fix  {finding.remediation}")
    return "\n".join(rows)


def _evaluate(root: Path, registry: dict, capability: dict, check: dict, host) -> Finding:
    kind, required = check["kind"], bool(capability["required"])
    capability_id, remediation = capability["id"], capability["remediation"]

    if kind == "path":
        declared = check["path"]
        size = host.size(resolve_path(root, declared))
        if size is None:
            return _fail(capability_id, required, remediation, f"{declared} is missing")
        minimum = int(check.get("min_bytes", 0))
        if size < minimum:
            return _fail(capability_id, required, remediation,
                         f"{declared} is {size} bytes, needs at least {minimum}")
        return _ok(capability_id, required, f"{declared} present, {size} bytes")

    if kind == "executable":
        for candidate in check["any_of"]:
            # A candidate with a separator is a promise about where it lives, not a PATH lookup.
            found = host.size(Path(candidate)) if _is_path_like(candidate) else host.which(candidate)
            if found:
                return _ok(capability_id, required, f"{candidate} found")
        return _fail(capability_id, required, remediation,
                     "nothing runnable among " + ", ".join(check["any_of"]))

    if kind == "module":
        python = resolve_interpreter(root, registry, check["interpreter"])
        if host.module(python, check["name"]):
            return _ok(capability_id, required, f"{check['name']} importable by {python}")
        return _fail(capability_id, required, remediation,
                     f"{check['name']} is not importable by {python}")

    if kind == "blender":
        where = host.blender_executable(root)
        if where is None:
            return _fail(capability_id, required, remediation,
                         "blender executable is missing (workflow/blender.json)")
        size = host.size(where)
        minimum = int(check.get("min_bytes", 0))
        if size is not None and size < minimum:
            return _fail(capability_id, required, remediation,
                         f"blender at {_flat(where)} is {size} bytes, needs at least {minimum}")
        return _ok(capability_id, required, f"blender at {_flat(where)}")

    raise ValueError(f"{capability_id}: unknown check kind {kind!r}, expected one of {CHECK_KINDS}")


def _ok(capability_id: str, required: bool, detail: str) -> Finding:
    return Finding(capability_id, True, detail, "", required)


def _fail(capability_id: str, required: bool, remediation: str, detail: str) -> Finding:
    return Finding(capability_id, False, detail, remediation, required)


def _where(root: Path, declared: str) -> Path:
    base = Path(os.path.expanduser(declared))
    return base if base.is_absolute() else Path(root) / base


def _is_path_like(candidate: str) -> bool:
    return "/" in candidate or "\\" in candidate


def _flat(path) -> str:
    return str(path).replace("\\", "/")


def main(argv: list[str]) -> int:
    root = Path(__file__).resolve().parents[1]
    phase = argv[argv.index("--phase") + 1] if "--phase" in argv else None
    findings = preflight(root, phase=phase)
    print(format_findings(findings))

    scope = f" for phase {phase}" if phase else ""
    failures = required_failures(findings)
    if failures:
        print(f"\npreflight: {len(failures)} required check(s) failed{scope} - "
              f"{', '.join(sorted({finding.capability for finding in failures}))}")
        return 1
    optional = [finding for finding in findings if not finding.required and not finding.ok]
    print(f"\npreflight: clean{scope}, {len(findings)} check(s)"
          + (f", {len(optional)} optional check(s) unavailable" if optional else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
