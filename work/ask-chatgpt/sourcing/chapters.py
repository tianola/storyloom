"""Chapter times for the YouTube description: each chapter's first line, found in vo/captions.srt (the captions
are timed on the master's own clock, so this does not drift the way summing per-line lengths does)."""
import json
import re
from pathlib import Path

EP = Path('.').resolve() / 'work' / 'ask-chatgpt'
lines = (EP / 'script/narration.md').read_text(encoding='utf-8').splitlines()
chapters = json.loads((EP / 'script/chapters.json').read_text(encoding='utf-8'))['chapters']
srt = (EP / 'vo/captions.srt').read_text(encoding='utf-8')
cues = []
for block in srt.strip().split('\n\n'):
    parts = block.splitlines()
    m = re.match(r'(\d+):(\d+):(\d+),(\d+)', parts[1])
    t = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + int(m[4]) / 1000
    cues.append((t, ' '.join(parts[2:])))


def norm(s):
    return re.sub(r'[^a-z ]', '', s.lower()).split()


for ch in chapters:
    first = norm(lines[int(ch['from'][1:]) - 1])[:4]
    hit = next((t for t, txt in cues if norm(txt)[:4] == first), None)
    if hit is None:
        hit = next((t for t, txt in cues if ' '.join(first) in ' '.join(norm(txt))), None)
    t = 0 if ch['from'] == 'u001' else int(hit)
    print(f"{t // 60}:{t % 60:02d} {ch['title']}")
