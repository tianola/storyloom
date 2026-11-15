import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "work/blender-upgrade"
BLENDER = ROOT / "tools/blender-4.5.15-windows-x64/blender.exe"
ARCHIVE = ROOT / "tools/blender-addons/commotion.zip"
CONFIG = OUTPUT / "config"
SCRIPTS = OUTPUT / "scripts"
REPORT = OUTPUT / "commotion.json"

INSTALL_EXPRESSION = r'''
import bpy
import os
bpy.ops.preferences.addon_install(filepath=os.environ["COMMOTION_ZIP"])
bpy.ops.preferences.addon_enable(module=os.environ["COMMOTION_MODULE"])
bpy.ops.wm.save_userpref()
print("COMMOTION_INSTALL_ENABLED: " + os.environ["COMMOTION_MODULE"], flush=True)
'''

VERIFY_EXPRESSION = r'''
import addon_utils
import bpy
import importlib
import json
import os
import tomllib
from pathlib import Path
module_name = os.environ["COMMOTION_MODULE"]
module = importlib.import_module(module_name)
enabled = bool(addon_utils.check(module_name)[1])
manifest_path = Path(module.__file__).with_name("blender_manifest.toml")
with manifest_path.open("rb") as handle:
    version = tomllib.load(handle)["version"]
report = {
    "blender_version": bpy.app.version_string,
    "module": module_name,
    "module_file": module.__file__,
    "version": version,
    "enabled": enabled,
    "import_succeeded": True,
    "scene_property_registered": bpy.types.Scene.bl_rna.properties.get("commotion") is not None,
    "user_config": os.environ["BLENDER_USER_CONFIG"],
    "user_scripts": os.environ["BLENDER_USER_SCRIPTS"],
}
Path(os.environ["COMMOTION_REPORT"]).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print("COMMOTION_VERIFICATION: " + json.dumps(report), flush=True)
if not enabled:
    raise RuntimeError("Commotion imported but is not enabled")
'''


def archive_module():
    with zipfile.ZipFile(ARCHIVE) as archive:
        for name in archive.namelist():
            if name.endswith("/__init__.py") and name.count("/") == 1:
                return name.split("/", 1)[0]
    raise RuntimeError("Commotion archive has no top-level add-on module")


def run_blender(expression, log_name, module, factory):
    command = [str(BLENDER), "--background"]
    if factory:
        command.append("--factory-startup")
    command.extend(["--python-exit-code", "1", "--python-expr", expression])
    env = os.environ.copy()
    env.update(
        BLENDER_USER_CONFIG=str(CONFIG),
        BLENDER_USER_SCRIPTS=str(SCRIPTS),
        COMMOTION_ZIP=str(ARCHIVE),
        COMMOTION_MODULE=module,
        COMMOTION_REPORT=str(REPORT),
    )
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    (OUTPUT / log_name).write_text(completed.stdout, encoding="utf-8")
    return command, completed


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    CONFIG.mkdir(parents=True, exist_ok=True)
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    module = archive_module()
    install_command, install = run_blender(INSTALL_EXPRESSION, "commotion-install.log", module, factory=True)
    if install.returncode != 0:
        REPORT.write_text(
            json.dumps(
                {
                    "module": module,
                    "enabled": False,
                    "import_succeeded": False,
                    "install_returncode": install.returncode,
                    "error": "Commotion installation/enable process failed; production Blender selection is unchanged",
                    "log": "work/blender-upgrade/commotion-install.log",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print((OUTPUT / "commotion-install.log").read_text(encoding="utf-8"))
        return 1

    verify_command, verify = run_blender(VERIFY_EXPRESSION, "commotion-verify.log", module, factory=False)
    if verify.returncode != 0 or not REPORT.is_file():
        REPORT.write_text(
            json.dumps(
                {
                    "module": module,
                    "enabled": False,
                    "import_succeeded": False,
                    "install_returncode": install.returncode,
                    "verify_returncode": verify.returncode,
                    "error": "Commotion second-process verification failed; production Blender selection is unchanged",
                    "install_log": "work/blender-upgrade/commotion-install.log",
                    "verify_log": "work/blender-upgrade/commotion-verify.log",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print((OUTPUT / "commotion-verify.log").read_text(encoding="utf-8"))
        return 1

    report = json.loads(REPORT.read_text(encoding="utf-8"))
    report.update(
        install_returncode=install.returncode,
        verify_returncode=verify.returncode,
        install_command=install_command,
        verify_command=verify_command,
        install_log="work/blender-upgrade/commotion-install.log",
        verify_log="work/blender-upgrade/commotion-verify.log",
    )
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report.get("enabled") is True else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, KeyError, ValueError, RuntimeError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
