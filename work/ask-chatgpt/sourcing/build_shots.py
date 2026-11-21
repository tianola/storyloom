"""shots.json for work/ask-chatgpt: archive lines from script/shots-hint.json, every other line on a named 3D beat."""
import json
from pathlib import Path
EP = Path('.').resolve() / 'work' / 'ask-chatgpt'
hints = json.loads((EP / 'script/shots-hint.json').read_text(encoding='utf-8'))
BEATS = [
    ('b01-stream', [2]), ('b02-waiting', [5, 6, 7, 8]), ('b03-fact', [10, 11]), ('b04-users', [12]),
    ('b05-latency', [18, 19]), ('b06-tokens', range(23, 27)), ('b07-space', range(27, 34)), ('b08-weights', range(34, 40)),
    ('b09-attention', range(40, 44)), ('b10-experts', range(44, 49)), ('b11-scores', range(49, 53)), ('b12-loop', range(53, 57)),
    ('b13-prefill', range(57, 61)), ('b14-fetch', range(61, 65)), ('b15-race', range(66, 71)), ('b16-idle', range(71, 74)),
    ('b17-energy', [74, 75]), ('b18-wire', [76, 77]), ('b19-close', [78]), ('b20-tsv', [81, 82]), ('b21-dies', [84]),
    ('b22-euv', [85]), ('b23-capacity', [86]), ('b24-batch', range(87, 92)), ('b25-cache', range(92, 96)),
    ('b26-bits', range(96, 100)), ('b27-rack', [100]), ('b28-trays', [103, 104]), ('b29-spine', [105, 106, 107]),
    ('b30-slices', [108, 109]), ('b31-heat', [110]), ('b32-homes', [112]), ('b33-query', range(119, 123)),
    ('b34-compare', range(123, 126)), ('b35-load', [126, 127]), ('b36-share', [129]), ('b37-recap-tokens', [132]),
    ('b38-recap-fetch', [133]), ('b39-recap-rack', [134]), ('b40-recap-fact', [135]), ('b41-stutter', [136, 137, 138]),
]
shots = {}
for uid, name in hints.items():
    shots[uid] = {"kind": "archive", "name": name, "title": "", "subtitle": ""}
for name, lines in BEATS:
    for n in lines:
        uid = f"u{n:03d}"
        assert uid not in shots, uid
        shots[uid] = {"kind": "3d", "name": name, "title": "", "subtitle": ""}
missing = [f"u{n:03d}" for n in range(1, 139) if f"u{n:03d}" not in shots]
assert not missing, missing
(EP / 'shots.json').write_text(json.dumps({k: shots[k] for k in sorted(shots)}, indent=2), encoding='utf-8')
print(len(shots), 'lines;', len(BEATS), '3D beats')
