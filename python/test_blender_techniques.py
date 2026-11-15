"""Integration test for the Blender 3D technique pack (Task 5).

Invokes Blender in background mode to build four scenes (cutaway, exploded,
x-ray, zoom-inside) and validates each one against the test contract.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLENDER_CONFIG = ROOT / "workflow" / "config.py"
sys.path.insert(0, str(ROOT))
from workflow.config import blender_executable

TECHNIQUES_DIR = ROOT / "tools" / "blender" / "techniques"
BUILD_SCRIPT = TECHNIQUES_DIR / "build.py"
VALIDATE_SCRIPT = TECHNIQUES_DIR / "validate.py"

SCENES = ["cutaway", "exploded", "xray", "zoom-inside"]


def _blender_exe() -> Path:
    return blender_executable(ROOT)


def _run_blender(script: Path, extra_args: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    """Run a Blender background-mode Python script."""
    cmd = [
        str(_blender_exe()),
        "--background",
        "--factory-startup",
        "--python-exit-code", "1",
        "--python", str(script),
        "--",
    ] + extra_args
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


class TestBlenderTechniques(unittest.TestCase):
    """Build all four technique scenes and validate them."""

    @classmethod
    def setUpClass(cls):
        """Build all scenes into a temp directory once for the whole class."""
        cls._tmpdir = tempfile.mkdtemp(prefix="techniques_")
        cls.output_dir = Path(cls._tmpdir)
        # Check that the build script exists
        if not BUILD_SCRIPT.exists():
            raise FileNotFoundError(
                f"Build script does not exist: {BUILD_SCRIPT}\n"
                "This is expected during the RED phase of TDD."
            )
        started = time.perf_counter()
        cls.build_result = _run_blender(
            BUILD_SCRIPT,
            ["--output", str(cls.output_dir)],
            timeout=900,
        )
        cls.build_elapsed = time.perf_counter() - started
        cls.build_log = cls.build_result.stdout
        # Write log for debugging
        log_path = ROOT / "work" / "technique-pack" / "build.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(cls.build_log, encoding="utf-8")

    def test_01_build_exit_code(self):
        """build.py must exit with code 0."""
        self.assertEqual(
            self.build_result.returncode, 0,
            f"build.py exited with code {self.build_result.returncode}\n"
            f"Last 2000 chars of log:\n{self.build_log[-2000:]}"
        )

    def test_02_blend_files_exist(self):
        """Each scene must produce a .blend file."""
        for name in SCENES:
            blend = self.output_dir / f"{name}.blend"
            self.assertTrue(blend.exists(), f"Missing blend file: {blend}")
            self.assertGreater(blend.stat().st_size, 0, f"Empty blend file: {blend}")

    def test_03_midpoint_pngs_exist(self):
        """Each scene must produce a non-empty midpoint PNG at frame 75."""
        for name in SCENES:
            png = self.output_dir / f"{name}.png"
            self.assertTrue(png.exists(), f"Missing midpoint PNG: {png}")
            self.assertGreater(png.stat().st_size, 100, f"PNG too small (likely empty): {png}")

    def test_04_validate_cutaway(self):
        """Validate the cutaway scene contract."""
        blend = self.output_dir / "cutaway.blend"
        if not blend.exists():
            self.skipTest("cutaway.blend not built")
        result = _run_blender(
            VALIDATE_SCRIPT,
            ["--scene", "cutaway", "--blend", str(blend)],
        )
        self.assertEqual(result.returncode, 0,
                         f"validate.py cutaway failed:\n{result.stdout[-2000:]}")
        # Parse validation JSON from stdout
        vdata = self._extract_validation_json(result.stdout)
        self.assertIsNotNone(vdata, "No validation JSON found in output")
        self.assertTrue(vdata.get("has_shell"), "Missing 'shell' object")
        self.assertTrue(vdata.get("has_core"), "Missing 'core' object")
        self.assertTrue(vdata.get("has_cutaway_modifier"), "Missing CUTAWAY modifier")
        self.assertTrue(vdata.get("has_exact_solver"), "CUTAWAY modifier not Exact solver")
        self.assertTrue(vdata.get("has_label"), "No visible label found")

    def test_05_validate_exploded(self):
        """Validate the exploded scene contract."""
        blend = self.output_dir / "exploded.blend"
        if not blend.exists():
            self.skipTest("exploded.blend not built")
        result = _run_blender(
            VALIDATE_SCRIPT,
            ["--scene", "exploded", "--blend", str(blend)],
        )
        self.assertEqual(result.returncode, 0,
                         f"validate.py exploded failed:\n{result.stdout[-2000:]}")
        vdata = self._extract_validation_json(result.stdout)
        self.assertIsNotNone(vdata, "No validation JSON found in output")
        self.assertGreaterEqual(vdata.get("part_count", 0), 4,
                                "Need at least 4 named parts")
        self.assertTrue(vdata.get("has_explode_modifier"), "Missing EXPLODE modifier")

    def test_06_validate_xray(self):
        """Validate the xray scene contract."""
        blend = self.output_dir / "xray.blend"
        if not blend.exists():
            self.skipTest("xray.blend not built")
        result = _run_blender(
            VALIDATE_SCRIPT,
            ["--scene", "xray", "--blend", str(blend)],
        )
        self.assertEqual(result.returncode, 0,
                         f"validate.py xray failed:\n{result.stdout[-2000:]}")
        vdata = self._extract_validation_json(result.stdout)
        self.assertIsNotNone(vdata, "No validation JSON found in output")
        self.assertTrue(vdata.get("has_transparent_mix"), "Shell missing Transparent BSDF mix")
        self.assertTrue(vdata.get("has_animated_mix"), "Mix factor not animated")

    def test_07_validate_zoom_inside(self):
        """Validate the zoom-inside scene contract."""
        blend = self.output_dir / "zoom-inside.blend"
        if not blend.exists():
            self.skipTest("zoom-inside.blend not built")
        result = _run_blender(
            VALIDATE_SCRIPT,
            ["--scene", "zoom-inside", "--blend", str(blend)],
        )
        self.assertEqual(result.returncode, 0,
                         f"validate.py zoom-inside failed:\n{result.stdout[-2000:]}")
        vdata = self._extract_validation_json(result.stdout)
        self.assertIsNotNone(vdata, "No validation JSON found in output")
        self.assertTrue(vdata.get("has_camera_keyframe_f1"), "No camera location keyframe at frame 1")
        self.assertTrue(vdata.get("has_camera_keyframe_f150"), "No camera location keyframe at frame 150")

    def test_08_common_scene_properties(self):
        """Every scene must have: camera, 30fps, 150-frame range, AgX, EEVEE Next."""
        for name in SCENES:
            blend = self.output_dir / f"{name}.blend"
            if not blend.exists():
                continue
            result = _run_blender(
                VALIDATE_SCRIPT,
                ["--scene", name, "--blend", str(blend), "--common-only"],
            )
            if result.returncode != 0:
                self.fail(f"validate.py --common-only failed for {name}:\n{result.stdout[-2000:]}")
            vdata = self._extract_validation_json(result.stdout)
            if vdata is None:
                self.fail(f"No validation JSON for {name}")
            self.assertTrue(vdata.get("has_camera"), f"{name}: missing Camera")
            self.assertEqual(vdata.get("fps"), 30, f"{name}: fps != 30")
            self.assertEqual(vdata.get("frame_start"), 1, f"{name}: frame_start != 1")
            self.assertEqual(vdata.get("frame_end"), 150, f"{name}: frame_end != 150")
            self.assertEqual(vdata.get("resolution_x"), 640, f"{name}: resolution_x != 640")
            self.assertEqual(vdata.get("resolution_y"), 360, f"{name}: resolution_y != 360")
            self.assertEqual(vdata.get("engine"), "BLENDER_EEVEE_NEXT", f"{name}: wrong engine")
            self.assertEqual(vdata.get("view_transform"), "AgX", f"{name}: wrong color management")

    @staticmethod
    def _extract_validation_json(stdout: str) -> dict | None:
        """Extract the VALIDATION_JSON line from Blender output."""
        for line in stdout.splitlines():
            if line.startswith("VALIDATION_JSON:"):
                return json.loads(line[len("VALIDATION_JSON:"):])
        return None


if __name__ == "__main__":
    unittest.main()
