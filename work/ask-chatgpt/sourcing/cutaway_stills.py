"""Render one still in the middle of every cutaway (one Blender run per beat). Run from repo root."""
import json, os, subprocess, sys
from pathlib import Path
EP = Path('work/ask-chatgpt')
BLENDER = os.environ.get('BLENDER_EXE', 'F:/AI-PROJECTS/longform-explainer/tools/blender-4.5.15-windows-x64/blender.exe')
board = json.loads((EP / 'storyboard.json').read_text(encoding='utf-8'))['beats']
lengths = json.loads((EP / 'shot_lengths.json').read_text(encoding='utf-8'))
out = EP / 'qc/stills5'
out.mkdir(parents=True, exist_ok=True)
for name, b in board.items():
    shots = b.get('shots') or []
    if len(shots) != 3:
        continue
    L = float(lengths[name])
    starts = [float(s.get('start', 0)) for s in shots]
    ends = starts[1:] + [L]
    fr = [round((s + e) / 2 / L, 4) for s, e, sh in zip(starts, ends, shots) if 'to' not in sh]
    args = [a for f in fr for a in ('--still', str(f))]
    r = subprocess.run([BLENDER, '-b', '--factory-startup', '--python', 'tools/blender/storyboard_beats.py', '--',
                        '--episode', str(EP), '--beat', name, *args, '--out', str(out)], capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    print(name, 'ok' if r.returncode == 0 else 'FAILED', fr, flush=True)
