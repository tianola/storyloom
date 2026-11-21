"""Sheet of the cut clips: four frames each (start, 1/3, 2/3, end). Run from repo root: python cutsheet.py [names...]"""
import subprocess, json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
EP = Path('work/ask-chatgpt'); cuts = json.loads((EP/'sourcing/cuts.json').read_text())
names = sys.argv[1:] or list(cuts)
f = ImageFont.truetype('arial.ttf', 16); TW = 240
tiles = []
for name in names:
    row = []
    for frac in (0.01, 0.34, 0.67, 0.985):
        out = EP/'sourcing/tmp.jpg'
        subprocess.run(['ffmpeg','-v','error','-y','-ss',str(cuts[name]['duration']*frac),'-i',str(EP/'assets/archive'/f'{name}.mp4'),'-frames:v','1','-vf',f'scale={TW}:-2',str(out)],check=True)
        row.append(Image.open(out).copy())
    tiles.append((name,row))
W=TW*4; H=135+20
sheet = Image.new('RGB',(W*2, H*((len(tiles)+1)//2)))
d = ImageDraw.Draw(sheet)
for i,(n,row) in enumerate(tiles):
    x=(i%2)*W; y=(i//2)*H
    for j,im in enumerate(row): sheet.paste(im,(x+j*TW,y+20))
    d.text((x+4,y+2),n,fill=(255,255,0),font=f)
sheet.save(EP/'sourcing/sheets/cuts.png'); print('ok')
