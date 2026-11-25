"""Which heavy tools this machine has, for tests that need them.

Blender, the Manim venv, Tesseract, the downloaded Poly Haven assets and the installed agent skills
live on the production PC only. On any other checkout (a laptop, CI, a cloud session) a test that
needs one of them used to *error*, which buried the real failures under a wall of
FileNotFoundError. Those tests now skip with the reason instead.

On the production PC nothing changes: the tools are there, so the tests run. To be sure a missing
tool is never skipped silently there, set STORYLOOM_REQUIRE_TOOLCHAIN=1 and every skip below turns
back into a failure.
"""
import os
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflow.config import blender_executable  # noqa: E402


def _missing(reason):
    if os.environ.get("STORYLOOM_REQUIRE_TOOLCHAIN") == "1":
        raise AssertionError(f"{reason} (STORYLOOM_REQUIRE_TOOLCHAIN=1)")
    raise unittest.SkipTest(reason)


def _runnable(path):
    path = Path(path)
    return path.is_file() or shutil.which(str(path)) is not None


def require_blender():
    """The Blender the pipeline renders with (BLENDER_EXE or workflow/blender.json)."""
    exe = blender_executable(ROOT)
    if not _runnable(exe):
        _missing(f"no Blender at {exe} (set BLENDER_EXE)")
    return exe


def require_file(path, what):
    if not Path(path).is_file():
        _missing(f"{what} is not on this machine: {path}")
    return Path(path)


def require_dir_content(path, what, ignore=("manifest.json",)):
    """A download folder that holds more than its committed index."""
    path = Path(path)
    if not path.is_dir() or not any(p.name not in ignore for p in path.iterdir()):
        _missing(f"{what} is not downloaded: {path}")
    return path


def require_skills():
    """The agent skills workflow/skills.json names, installed on this machine."""
    from workflow.skills import skills_map
    try:
        return skills_map(ROOT)
    except ValueError as exc:
        if "not installed" not in str(exc):
            raise
        _missing(f"agent skills are not installed here: {exc}")


def require_ocr():
    """Tesseract, which the archive mirror guard needs to claim a clip has no text."""
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        _missing("pytesseract is not installed")
    if not (shutil.which("tesseract") or Path("C:/Program Files/Tesseract-OCR/tesseract.exe").is_file()):
        _missing("the tesseract executable is not installed")
