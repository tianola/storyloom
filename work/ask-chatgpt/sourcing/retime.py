"""Slow three already-cut clips so each covers the line that names it (no new download). Run from repo root once.
The original cut is kept beside it as <name>.orig.mp4; cuts.json records the combined speed and new duration."""
import json, shutil, subprocess
from pathlib import Path
EP = Path('work/ask-chatgpt')
SLOW = {'spad-pulse': 0.85, 'nvb-hgx': 0.95, 'qct-gh': 0.95}
p = EP / 'sourcing/cuts.json'
cuts = json.loads(p.read_text(encoding='utf-8'))
for name, s in SLOW.items():
    dest = EP / 'assets/archive' / f'{name}.mp4'
    orig = EP / 'sourcing/orig' / f'{name}.orig.mp4'
    if not orig.exists():
        shutil.copy2(dest, orig)
    c = cuts[name]
    fps = c['fps']
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(orig), '-vf', f'setpts=PTS/{s}', '-r', str(fps), '-an',
                    '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', str(dest)], check=True)
    d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(dest)],
                             capture_output=True, text=True).stdout)
    c['speed'] = round(c['speed'] * s, 3)
    c['duration'] = round(d, 3)
    print(name, c['speed'], c['duration'])
p.write_text(json.dumps(cuts, indent=1), encoding='utf-8')

