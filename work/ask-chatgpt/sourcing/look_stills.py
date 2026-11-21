"""One still per scene (its first beat) into an output folder, for before/after look checks.
Usage (repo root): python look_stills.py OUT_DIR [FRACTION]"""
import json, os, subprocess, sys
from pathlib import Path
EP = Path('work/ask-chatgpt')
BLENDER = os.environ.get('BLENDER_EXE', 'F:/AI-PROJECTS/longform-explainer/tools/blender-4.5.15-windows-x64/blender.exe')
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
frac = sys.argv[2] if len(sys.argv) > 2 else '0.6'
board = json.loads((EP / 'storyboard.json').read_text(encoding='utf-8'))['beats']
first = {}
for name, b in board.items():
    first.setdefault(b['scene'], name)
for scene, name in first.items():
    r = subprocess.run([BLENDER, '-b', '--factory-startup', '--python', 'tools/blender/storyboard_beats.py', '--',
                        '--episode', str(EP), '--beat', name, '--still', frac, '--out', str(out)],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    tail = [l for l in (r.stdout + r.stderr).splitlines() if 'Error' in l or 'FRAMING' in l][-3:]
    print(name, scene, 'ok' if r.returncode == 0 else 'FAILED', *tail, flush=True)
