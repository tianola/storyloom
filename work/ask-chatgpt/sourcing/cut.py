"""Cut the archive clips from the Commons 1080p transcodes (or the original when there is none). Run from repo root.
Each cut: H.264, no audio, 1920x1080 canvas-fit, at the source's own frame rate."""
import json, subprocess, sys
from pathlib import Path
ROOT = Path('.').resolve(); sys.path.insert(0, str(ROOT))
from tools.sourcing import transport
contract = json.loads((ROOT / 'workflow/style.json').read_text(encoding='utf-8'))
UA = transport.headers(contract)['User-Agent']
EP = ROOT / 'work/ask-chatgpt'
info = json.loads((EP / 'sourcing/info.json').read_text(encoding='utf-8'))
LOGO = "crop=iw*0.86:ih*0.86:iw*0.14:ih*0.14"   # removes the channel logo in the top-left corner
# name: (source key, in s, length s, speed, extra filter)
CUTS = {
    'typing': ('typing', 0.5, 5.3, 1, None), 'typing-b': ('typing', 10.0, 4.0, 1, None),
    'dc-cables': ('dc-tour', 980.0, 6.0, 1, None), 'dc-rows': ('dc-tour', 515.5, 6.6, 1, None),
    'dc-chillers': ('dc-tour', 575.0, 7.4, 1, None), 'cell-tower': ('cell-tower', 1.0, 5.4, 1, None),
    'dc-fiber2': ('dc-tour', 725.5, 7.4, 1, None), 'laser-water': ('fiber-eg', 64.6, 6.6, 1, None),
    'spad-pulse': ('spad-pulse', 0.0, 4.8, 1, None), 'dc-hall': ('dc-tour', 38.0, 7.4, 1, None),
    'nvb-hgx': ('nv-booth', 24.5, 4.0, 1, LOGO), 'gh-server': ('supermicro-gh', 95.0, 7.0, 1, None),
    'nvb-tray': ('nv-booth', 65.4, 2.25, 0.5, LOGO), 'qct-gh': ('qct-gh', 8.8, 5.0, 1, None),
    'nvb-server': ('nv-booth', 69.2, 3.5, 0.9, LOGO), 'smuc-anim': ('supermuc', 35.0, 7.0, 1, None),
    'dc-pumps': ('dc-tour', 500.0, 3.5, 1, None), 'tower-showers': ('tower-showers', 0.0, 5.47, 1, None),
    'tower-inside': ('tower-inside', 0.0, 7.0, 1, None), 'dc-roof': ('dc-tour', 557.5, 2.45, 0.9, None),
    'smuc-racks': ('supermuc', 175.5, 4.0, 1, None), 'dc-chillers2': ('dc-tour', 618.0, 9.0, 1, None),
    'spad-b': ('spad-pulse', 8.0, 3.0, 1, None), 'dc-fiber': ('dc-tour', 677.0, 4.0, 1, None),
}
want = sys.argv[1:] or list(CUTS)
out = {}
for name in want:
    key, t0, ln, speed, extra = CUTS[name]
    v = info[key]
    ders = {d['transcodekey']: d['src'] for d in v['derivatives']}
    url = ders.get('1080p.vp9.webm') or v['url'].split('?')[0]
    dest = EP / 'assets/archive' / f'{name}.mp4'
    vf = [extra] if extra else []
    if speed != 1:
        vf.append(f"setpts=PTS/{speed}")
    vf.append("scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1")
    cmd = ['ffmpeg', '-v', 'error', '-y', '-user_agent', UA, '-ss', f'{t0:.3f}', '-t', f'{ln:.3f}', '-i', url,
           '-vf', ','.join(vf), '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', str(dest)]
    subprocess.run(cmd, check=True)
    fps = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', str(dest)], capture_output=True, text=True).stdout.strip()
    d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(dest)], capture_output=True, text=True).stdout)
    n, dd = fps.split('/')
    out[name] = {"source": key, "in": t0, "length": ln, "speed": speed, "logo_crop": bool(extra), "fps": round(int(n) / int(dd), 3), "duration": round(d, 3), "from": url}
    print(name, out[name]['fps'], out[name]['duration'], flush=True)
p = EP / 'sourcing/cuts.json'
old = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
old.update(out)
p.write_text(json.dumps(old, indent=1), encoding='utf-8')
