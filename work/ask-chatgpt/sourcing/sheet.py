"""Contact sheet of a video: one frame every STEP seconds, labelled with its time. Run from repo root.
python sheet.py <video> <out.png> <step> [start] [end]"""
import subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
src, out, step = sys.argv[1], sys.argv[2], float(sys.argv[3])
start = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', src], capture_output=True, text=True).stdout.strip())
end = float(sys.argv[5]) if len(sys.argv) > 5 else dur
tmp = Path(tempfile.mkdtemp())
subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(start), '-to', str(end), '-i', src, '-vf', f'fps=1/{step},scale=320:-2', str(tmp / 'f%04d.jpg')], check=True)
frames = sorted(tmp.glob('f*.jpg'))
cols = 6
w, h = Image.open(frames[0]).size
rows = (len(frames) + cols - 1) // cols
sheet = Image.new('RGB', (cols * w, rows * (h + 18)), (0, 0, 0))
d = ImageDraw.Draw(sheet)
font = ImageFont.truetype('arial.ttf', 14)
for i, f in enumerate(frames):
    x, y = (i % cols) * w, (i // cols) * (h + 18)
    sheet.paste(Image.open(f), (x, y + 18))
    t = start + i * step
    d.text((x + 4, y + 2), f'{int(t // 60)}:{t % 60:04.1f}', fill=(255, 255, 0), font=font)
sheet.save(out)
print(out, len(frames), 'frames')
