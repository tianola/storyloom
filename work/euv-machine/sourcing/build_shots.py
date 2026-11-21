"""shots.json for work/euv-machine, by hand: every idea gets its own beat, archive lines from shots-hint.json."""
import json
from pathlib import Path

EP = Path('.').resolve() / 'work' / 'euv-machine'
hints = json.loads((EP / 'script/shots-hint.json').read_text(encoding='utf-8'))
M = json.loads((EP / 'vo/manifest.json').read_text(encoding='utf-8'))
ids = [u['id'] for u in M['utterances']]

# beat name -> first..last line (inclusive); archive lines inside a range are skipped (they are cutaways)
BEATS = [
    ('b01-droplet', 1, 4), ('b02-again', 6, 6), ('b04-machine', 10, 10),
    ('b06-projector', 15, 18), ('b07-gap', 20, 23), ('b08-grating', 24, 28), ('b09-miss', 29, 31), ('b10-formula', 32, 38),
    ('b11-wavelength-knob', 39, 39), ('b12-lasers', 41, 42), ('b13-other-knobs', 44, 44), ('b14-patterning', 46, 47),
    ('b15-euv', 48, 50), ('b16-problem-one', 52, 54), ('b17-tin', 55, 57), ('b18-pulses', 60, 64), ('b19-collector', 65, 68),
    ('b20-absorbed', 70, 73), ('b21-bragg', 74, 77), ('b22-why-13', 79, 81), ('b23-follow', 85, 85), ('b24-mask', 88, 89),
    ('b25-bounces', 91, 94), ('b26-slit', 95, 95), ('b27-scan', 97, 100), ('b28-photons', 102, 103), ('b29-energy', 104, 105),
    ('b30-shot-noise', 107, 112), ('b31-high-na', 113, 117), ('b32-look-back', 120, 121), ('b33-mirrors', 122, 122),
    ('b34-scanning', 123, 123), ('b35-power', 124, 124), ('b36-wave', 125, 125), ('b37-star', 127, 127),
]
shots = {}
for uid in ids:
    if uid in hints:
        shots[uid] = {"kind": "archive", "name": hints[uid], "title": "", "subtitle": ""}
for name, a, b in BEATS:
    for k in range(a, b + 1):
        uid = f"u{k:03d}"
        if uid in hints:
            continue
        assert uid not in shots, uid
        shots[uid] = {"kind": "3d", "name": name, "title": "", "subtitle": ""}
missing = [u for u in ids if u not in shots]
assert not missing, missing
ordered = {u: shots[u] for u in ids}
(EP / 'shots.json').write_text(json.dumps(ordered, indent=2), encoding='utf-8')
rate = M['sampleRate']
dur = {u['id']: u['samples'] / rate for u in M['utterances']}
share = sum(dur[u] for u, s in ordered.items() if s['kind'] == 'archive') / sum(dur.values())
print(len(ordered), 'lines', len(BEATS), 'beats; archive share', round(share, 3))
