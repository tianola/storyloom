"""storyboard.json for the story cut of work/ask-chatgpt (version 3, written to the story rules).

The film follows the word `cat` (a pixel token) with an explorer for company. Each stretch of narration is
a place the story stays in for several beats (`SEG`, keyed by its first line), not a new diagram per
sentence. Explanation beats are one continuous camera move (`cut: travel`, the builder default); the hook,
the race and the recap are quick montage. Text on screen is kept to a handful of labels.

Beats come from shots.json (plan_shots groups lines into beats); each beat takes the next spec of the
segment it starts in, and the last spec repeats. Times are fractions of the beat or `word:<w>`.
Run from the repository root.
"""
import copy
import json
from pathlib import Path

EP = Path('.').resolve() / 'work' / 'ask-chatgpt'


def cat(u=0.84, v=0.86, h=0.2, **kw):
    c = {"who": "token", "screen": [u, v], "height": h, "word": "cat", **kw}
    if "walk" not in kw:
        c["hop"] = True
    return c


def guide(u=0.14, v=0.86, h=0.28, **kw):
    return {"who": "explorer", "screen": [u, v], "height": h, **kw}


Q = "Why does my cat sound like a carburettor?"
# token pieces as a tokenizer would cut them: common words whole, a rarer one in fragments
A = "Cats| purr| by| tw|itching| the| muscles| of| the| voice| box|,| so| the| sound| comes| in| quick| pul|ses|."

SEG = [
    # the stutter: the answer types itself; the guess the viewer is handed is the busy tower of
    # maths (the idle factory is held back until the reversal at u050, so the picture does not
    # give the answer away)
    ("u001", [
        # cold open (the hook): one held pull-back from a single tray to the whole rack, which
        # lights up as the weight and the power are said; the cat at its foot gives the scale
        {"scene": "gpu-rack", "shots": [{"view": "tray", "to": "wide"}],
         "actions": [{"name": "slice", "at": "word:tonne"}, {"name": "cool", "at": "word:power"}],
         # placed where the floor beside the rack shows in the opening close-up (bottom right)
         "cast": [cat(0.93, 0.94, 0.09)]},
        {"scene": "token-stream", "cut": "montage", "params": {"prompt": Q, "answer": A},
         "actions": [{"name": "type", "at": 0.0}, {"name": "stream", "at": 0.06}], "cast": [cat(0.84, 0.86, 0.2)]},
        {"scene": "model-layers", "shots": [{"view": "wide", "to": "layer"}], "actions": [{"name": "pass", "at": 0.2}],
         "cast": [guide(0.1, 0.9, 0.26, walk=[0.15, 0.0]), cat(0.2, 0.92, 0.18)]},
        {"scene": "token-stream", "params": {"prompt": Q, "answer": A}, "shots": [{"view": "wide", "to": "close"}],
         "actions": [{"name": "stream", "at": 0.0}], "cast": [cat(0.86, 0.88, 0.2), guide(0.1, 0.88, 0.26)]},
    ]),
    # the trip through glass
    ("u008", [
        {"scene": "fiber-trip", "shots": [{"view": "phone", "to": "wide"}], "actions": [{"name": "send", "at": 0.15}],
         "cast": [cat(0.12, 0.84, 0.18, walk=[0.25, 0.0])]},
    ]),
    ("u012", [
        {"scene": "fiber-trip", "shots": [{"view": "fibre", "to": "wide"}], "actions": [{"name": "send", "at": 0.05}],
         "cast": [cat(0.86, 0.86, 0.18)]},
    ]),
    ("u015", [
        {"scene": "fiber-trip", "params": {"markers": True}, "shots": [{"view": "fibre", "to": "building"}],
         "actions": [{"name": "send", "at": 0.0}, {"name": "reply", "at": 0.6}], "cast": [guide(0.1, 0.88, 0.26)]},
    ]),
    # the warehouse in Abilene; the chips cannot read
    ("u019", [
        {"scene": "server-racks", "params": {"count": 5}, "shots": [{"view": "wide", "to": "drawer"}],
         "actions": [{"name": "open", "at": "word:read"}],
         "cast": [guide(0.1, 0.9, 0.26, walk=[0.2, 0.0]), cat(0.22, 0.92, 0.18)]},
    ]),
    # Philip Gage's 1994 article: merge the most common pair, again and again
    ("u022", [
        {"scene": "document", "params": {"title": "A New Algorithm for Data Compression", "lines": 14, "mark": 5},
         "shots": [{"view": "wide", "to": "mark"}], "actions": [{"name": "mark", "at": "word:pair"}],
         "cast": [guide(0.12, 0.88, 0.26)]},
    ]),
    ("u026", [
        {"scene": "tokenizer", "shots": [{"view": "wide", "to": "tokens"}],
         "actions": [{"name": "split", "at": 0.15}, {"name": "number", "at": "word:nine"}],
         "labels": [{"text": "cat = 9059", "anchor": "id", "at": "word:nine"}], "cast": [cat(0.88, 0.88, 0.2)]},
    ]),
    ("u029", [
        {"scene": "tokenizer", "shots": [{"view": "tokens", "to": "vector"}], "actions": [{"name": "embed", "at": 0.1}],
         "cast": [cat(0.86, 0.88, 0.18)]},
        {"scene": "embedding-space", "shots": [{"view": "flat", "to": "animals"}],
         "actions": [{"name": "lift", "at": 0.2}, {"name": "dims", "at": 0.5}, {"name": "point", "at": "word:dog"}],
         "cast": [guide(0.88, 0.88, 0.24)]},
    ]),
    # the climb
    ("u033", [
        {"scene": "model-layers", "shots": [{"view": "wide", "to": "layer"}], "actions": [{"name": "pass", "at": 0.3}],
         "cast": [cat(0.14, 0.88, 0.18), guide(0.86, 0.9, 0.24)]},
        {"scene": "model-layers", "shots": [{"view": "layer", "to": "attention"}], "actions": [{"name": "attend", "at": "word:attention"}],
         "cast": [cat(0.12, 0.86, 0.16)]},
    ]),
    ("u041", [
        {"scene": "experts", "shots": [{"view": "wide", "to": "router"}], "actions": [{"name": "route", "at": "word:router"}],
         "cast": [cat(0.12, 0.86, 0.16)]},
    ]),
    ("u045", [
        # the picked piece joins the answer, and the climb starts again (no invented probabilities on screen)
        {"scene": "token-stream", "params": {"prompt": Q, "answer": A}, "shots": [{"view": "close", "to": "wide"}],
         "actions": [{"name": "stream", "at": 0.1}], "cast": [guide(0.1, 0.9, 0.24)]},
        {"scene": "model-layers", "shots": [{"view": "layer", "to": "wide"}], "actions": [{"name": "pass", "at": 0.05}],
         "cast": [cat(0.12, 0.88, 0.16)]},
    ]),
    # the truck
    ("u049", [
        {"scene": "chip-factory", "params": {"truck_x": -6.4}, "shots": [{"view": "workers", "to": "wide"}],
         "cast": [guide(0.1, 0.9, 0.26), cat(0.2, 0.92, 0.18)]},
        {"scene": "chip-factory", "params": {"truck_x": -6.4}, "shots": [{"view": "wide", "to": "road"}],
         "actions": [{"name": "deliver", "at": 0.3}], "cast": [cat(0.84, 0.9, 0.18)]},
    ]),
    ("u056", [
        {"scene": "chip-factory", "cut": "montage", "params": {"truck_x": -6.6},
         "actions": [{"name": "deliver", "at": "word:delivery"}],
         "labels": [{"text": "4 µs of work", "anchor": "desk", "at": "word:four"},
                    {"text": "600 µs on the road", "anchor": "truck", "at": "word:six"}],
         "cast": [guide(0.1, 0.9, 0.24)]},
        # the truck crawls in while the workers wait: road first, then the idle desks
        {"scene": "chip-factory", "params": {"truck_x": -6.4}, "shots": [{"view": "road", "to": "workers"}],
         "actions": [{"name": "deliver", "at": 0.15}], "cast": [cat(0.86, 0.9, 0.18)]},
    ]),
    # the memory wall, 1994
    ("u062", [
        {"scene": "document", "params": {"title": "Hitting the Memory Wall", "lines": 10, "mark": 3},
         "shots": [{"view": "wide", "to": "mark"}], "actions": [{"name": "mark", "at": "word:widening"}],
         "cast": [guide(0.12, 0.88, 0.26)]},
    ]),
    ("u067", [
        {"scene": "wire-trip", "shots": [{"view": "wide", "to": "wire"}],
         "actions": [{"name": "send", "at": 0.1}, {"name": "local", "at": 0.6}], "cast": [cat(0.16, 0.9, 0.18, walk=[0.4, 0.0])]},
    ]),
    # trick one: move the warehouse (Bryan Black, AMD)
    ("u071", [
        {"scene": "chip-factory", "params": {"truck_x": -6.0}, "shots": [{"view": "road", "to": "wide"}],
         "cast": [guide(0.1, 0.9, 0.24)]},
        {"scene": "hbm-stack", "shots": [{"view": "wide", "to": "stack"}], "actions": [{"name": "explode", "at": 0.15}],
         "labels": [{"text": "memory chips, stacked", "anchor": "dram", "at": "word:stacked"}],
         "cast": [cat(0.86, 0.9, 0.16)]},
        {"scene": "hbm-stack", "shots": [{"view": "tsv", "to": "gpu"}], "actions": [{"name": "signal", "at": 0.1}]},
    ]),
    ("u080", [
        {"scene": "chip-factory", "params": {"truck_x": -2.8}, "shots": [{"view": "road", "to": "workers"}],
         "actions": [{"name": "deliver", "at": 0.2}], "cast": [guide(0.1, 0.9, 0.24), cat(0.84, 0.9, 0.18)]},
    ]),
    # trick two: share the truck; then the scratchpad problem
    ("u082", [
        {"scene": "batching", "params": {"mode": "batch", "users": 10}, "shots": [{"view": "wide", "to": "users"}],
         "actions": [{"name": "share", "at": 0.2}], "cast": [cat(0.86, 0.9, 0.16)]},
        {"scene": "chip-factory", "params": {"busy": True, "truck_x": -3.0}, "shots": [{"view": "wide", "to": "workers"}],
         "actions": [{"name": "deliver", "at": 0.1}], "cast": [guide(0.1, 0.9, 0.24)]},
        {"scene": "batching", "params": {"mode": "cache", "users": 10}, "shots": [{"view": "users", "to": "cache"}],
         "actions": [{"name": "share", "at": 0.1}], "cast": [cat(0.86, 0.9, 0.16)]},
    ]),
    ("u090", [
        {"scene": "batching", "params": {"mode": "cache", "users": 6}, "shots": [{"view": "cache", "to": "wide"}],
         "actions": [{"name": "share", "at": 0.2}], "cast": [guide(0.1, 0.9, 0.24)]},
        {"scene": "batching", "params": {"mode": "cache", "users": 12}, "shots": [{"view": "users", "to": "wide"}],
         "actions": [{"name": "share", "at": 0.1}], "cast": [cat(0.86, 0.9, 0.16)]},
    ]),
    ("u094", [
        {"scene": "model-layers", "shots": [{"view": "attention", "to": "layer"}], "actions": [{"name": "attend", "at": 0.2}],
         "cast": [cat(0.12, 0.88, 0.16)]},
    ]),
    # trick three: lighter cargo
    ("u096", [
        {"scene": "bit-width", "shots": [{"view": "number", "to": "lanes"}],
         "actions": [{"name": "shrink", "at": "word:four"}, {"name": "flow", "at": 0.6}], "cast": [guide(0.1, 0.9, 0.24)]},
    ]),
    # seventy two chips as one
    ("u099", [
        {"scene": "gpu-rack", "shots": [{"view": "wide", "to": "front"}], "actions": [{"name": "link", "at": 0.4}],
         "cast": [guide(0.1, 0.9, 0.3), cat(0.2, 0.92, 0.16)]},
    ]),
    ("u103", [
        {"scene": "gpu-rack", "shots": [{"view": "back", "to": "wide"}],
         "actions": [{"name": "link", "at": 0.05}, {"name": "slice", "at": "word:slices"}], "cast": [cat(0.86, 0.9, 0.16)]},
    ]),
    # the bill
    ("u106", [
        {"scene": "gpu-rack", "shots": [{"view": "tray", "to": "wide"}], "actions": [{"name": "cool", "at": 0.3}],
         "cast": [guide(0.1, 0.9, 0.28)]},
        {"scene": "heat-loop", "shots": [{"view": "rack", "to": "tower"}],
         "actions": [{"name": "flow", "at": 0.05}, {"name": "evaporate", "at": "word:evaporate"}], "cast": [cat(0.86, 0.9, 0.14)]},
    ]),
    ("u113", [
        {"scene": "token-stream", "params": {"prompt": Q, "answer": A}, "shots": [{"view": "close", "to": "wide"}],
         "actions": [{"name": "stream", "at": 0.0}], "cast": [cat(0.86, 0.88, 0.2)]},
        {"scene": "scale-compare", "params": {"many": 100}, "shots": [{"view": "wide", "to": "many"}],
         "actions": [{"name": "fill", "at": 0.15}], "cast": [guide(0.1, 0.9, 0.24)]},
    ]),
    # back to cat: the whole trip again, fast
    ("u118", [
        {"scene": "fiber-trip", "cut": "montage", "actions": [{"name": "send", "at": 0.0}], "cast": [cat(0.86, 0.86, 0.18)]},
        {"scene": "model-layers", "cut": "montage", "actions": [{"name": "pass", "at": 0.0}], "cast": [cat(0.12, 0.88, 0.16)]},
        {"scene": "chip-factory", "cut": "montage", "params": {"truck_x": -5.0},
         "actions": [{"name": "deliver", "at": 0.1}], "cast": [guide(0.1, 0.9, 0.24)]},
    ]),
    ("u125", [
        # end pulled back on the whole window, the answer still stuttering in
        {"scene": "token-stream", "params": {"prompt": Q, "answer": A}, "shots": [{"view": "close", "to": "wide"}],
         "actions": [{"name": "stream", "at": 0.0}], "cast": [cat(0.86, 0.88, 0.22), guide(0.12, 0.88, 0.26)]},
    ]),
]

# Quick cutaways onto details (anchors) that cut into or out of each held move. Measured on the master, a
# film of one move per beat had a median shot of 5.4 s; the references sit at 1.5-3.3 s with long holds in
# between. The details are the things the narration is about in that scene, not random angles.
# Curated from review stills (qc/stills4): only details that show something whenever they are cut to.
# Dropped: anchors whose object appears later in the beat (plume, many, chip, user, cache, vector) and
# anchors that frame a bland block (the factory's memory box, the fibre's building).
DETAILS = {
    "token-stream": ["at:cursor", "at:prompt"], "chip-factory": ["at:desk", "at:workers", "at:truck"],
    "fiber-trip": ["at:mast", "at:phone"], "server-racks": ["at:drawer", "wide"],
    "document": ["at:title", "at:mark"], "tokenizer": ["at:sentence", "at:token"],
    "model-layers": ["at:weights", "layer"], "experts": ["at:router", "at:expert"],
    "wire-trip": ["at:multiplier", "at:memory"], "hbm-stack": ["at:interposer", "at:gpu", "at:tsv"],
    "batching": ["at:weights", "wide"], "bit-width": ["number", "lanes"],
    "gpu-rack": ["at:coldplate", "at:gpu", "at:switch"], "heat-loop": ["at:pipes", "rack"],
    "scale-compare": ["at:one", "wide"],
}
HOLD = {"beat-13"}          # the longest explanation stays one unbroken move (the film needs a hold >= 20 s)
CUT_A, CUT_B = 1.2, 1.9     # cutaway lengths, s: a quick insert, then a readable detail


def punctuate(name, spec, sec, n):
    shots = spec.get("shots") or []
    if name in HOLD or spec.get("cut") == "montage" or len(shots) != 1 or "to" not in shots[0] or sec < 9:
        return spec
    move = dict(shots[0])
    cut_in = n % 2 == 0
    full = DETAILS.get(spec["scene"], [])
    if len(full) < 2:
        return spec
    a, b = full[n % len(full)], full[(n + 1) % len(full)]
    # the detail that meets the move must not be the view the move starts (cut in) or ends (cut out) on,
    # or that cut is invisible; swap the pair, and give up on the beat if both would touch
    touching = move["view"] if cut_in else move["to"]
    near, far = (b, a) if cut_in else (a, b)
    if near == touching:
        near, far = far, near
    if near == touching:
        return spec
    a, b = (far, near) if cut_in else (near, far)
    if cut_in:          # cut in: two details, then the move
        move["start"] = CUT_A + CUT_B
        spec["shots"] = [{"view": a, "start": 0.0}, {"view": b, "start": CUT_A}, move]
    else:               # cut out: the move, then two details lead into the next beat
        t = round(sec - CUT_A - CUT_B, 2)
        spec["shots"] = [move, {"view": a, "start": t}, {"view": b, "start": round(t + CUT_A, 2)}]
    return spec


shots = json.loads((EP / 'shots.json').read_text(encoding='utf-8'))
# the narrated span of each beat (shot_lengths.json is rounded up; the tail past the last word is never seen)
_m = json.loads((EP / 'vo/manifest.json').read_text(encoding='utf-8'))
lengths = {}
for _u in _m['utterances']:
    _n = shots[_u['id']]['name']
    lengths[_n] = lengths.get(_n, 0.0) + _u['samples'] / _m['sampleRate']
order = list(shots)
starts = [order.index(s) for s, _ in SEG]
assert starts == sorted(starts), "segments out of order"
board, used, seen = {}, {}, []
for uid in order:
    shot = shots[uid]
    if shot["kind"] != "3d" or shot["name"] in seen:
        continue
    seen.append(shot["name"])
    seg = max((k for k, (s, _) in enumerate(SEG) if order.index(s) <= order.index(uid)), default=0)
    k = used.get(seg, 0)
    used[seg] = k + 1
    specs = SEG[seg][1]
    spec = copy.deepcopy(specs[min(k, len(specs) - 1)])
    if k >= len(specs) and len(spec.get("shots", [])) == 1 and "to" in spec["shots"][0]:
        # a repeated spec travels the other way, so two beats in a row are not the same move
        sh = spec["shots"][0]
        sh["view"], sh["to"] = sh["to"], sh["view"]
    # the cold open (beat-00) came last; counting from beat-01 keeps every later beat's cutaways
    # (cut in/out and which details) exactly as they were reviewed in stills
    board[shot["name"]] = punctuate(shot["name"], spec, float(lengths[shot["name"]]),
                                    len(board) - ("beat-00" in board))
    board[shot["name"]]["note"] = f"from {uid}"
unused = [SEG[k][0] for k in range(len(SEG)) if k not in used]
(EP / 'storyboard.json').write_text(json.dumps({"beats": board}, indent=1, ensure_ascii=False), encoding='utf-8')
print(len(board), 'beats;', 'segments with no beat:', unused)
