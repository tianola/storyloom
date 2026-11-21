"""storyboard.json for work/ask-chatgpt, version 2: the story cut.

The film follows one word of the question, `cat`, with an explorer for company; the chip is shown as a
factory whose workers doze while a truck brings the weights. Pixel-art characters stand in the 3D sets
(`cast`), the bar charts that only compared two numbers became scenes, and on-screen text is cut to the
numbers that matter.

Times: a plain number is seconds into the beat as it ran in the first cut (as in version 1), converted
here to a fraction of that cut's length (sourcing/shot_lengths.v1.json) so it lands on the same words
after the narration was re-recorded; F(x) is already a fraction of the beat; `word:<w>` is exact.
"""
import json
from pathlib import Path

EP = Path('.').resolve() / 'work' / 'ask-chatgpt'
W, C = "warm", "cool"


class F(float):
    """A time that is already a fraction of the beat."""


def guide(u=0.13, v=0.87, h=0.3, shot=0, **kw):
    return {"who": "explorer", "screen": [u, v], "height": h, "shot": shot, **kw}


def cat(u=0.86, v=0.88, h=0.22, shot=0, hop=True, **kw):
    c = {"who": "token", "screen": [u, v], "height": h, "shot": shot, **kw}
    if hop and "walk" not in kw:
        c["hop"] = True
    return c


B = {
 "b01-stream": {"scene": "token-stream", "shots": [{"view": "wide"}],
   "actions": [{"name": "type", "at": 0.02}, {"name": "stream", "at": 0.08}],
   "cast": [cat(0.8, 0.86, 0.22)]},
 # the chip, met first as a factory floor of dozing workers
 "b02-waiting": {"scene": "chip-factory", "params": {"truck_x": -5.6},
   "shots": [{"view": "workers"}, {"view": "wide", "start": "word:waiting"}],
   "hud": [{"text": "about 10 billion multiplications per word", "screen": [0.5, 0.1], "at": F(0.12), "until": F(0.42), "color": W}],
   "cast": [guide(0.12, 0.88, 0.28, shot=1), cat(0.22, 0.9, 0.2, shot=1)]},
 "b03-fact": {"scene": "wire-trip", "shots": [{"view": "wide"}, {"view": "wire", "start": 4.6}],
   "actions": [{"name": "send", "at": 0.6}, {"name": "local", "at": 7.2}],
   "labels": [{"text": "Memory", "anchor": "memory", "at": 1.1, "until": 4.5}, {"text": "Multiplier", "anchor": "multiplier", "at": 2.0, "until": 4.5}],
   "cast": [guide(0.12, 0.9, 0.3, shot=1), cat(0.22, 0.9, 0.22, shot=1, hop=False, walk=[0.5, 0.0])]},
 "b04-users": {"scene": "fiber-trip", "shots": [{"view": "wide"}], "actions": [{"name": "send", "at": 0.3}],
   "counter": {"template": "{:,} people a week", "from": 1000000, "to": 900000000, "screen": [0.5, 0.86], "start": 0.5, "end": 4.6, "color": W},
   "cast": [cat(0.08, 0.8, 0.18, hop=False, walk=[0.3, 0.0])]},
 "b05-latency": {"scene": "fiber-trip", "params": {"markers": True}, "shots": [{"view": "fibre"}, {"view": "wide", "start": 4.2}],
   "actions": [{"name": "send", "at": 0.1}, {"name": "reply", "at": 5.0}],
   "hud": [{"text": "1,000 km of glass: about 5 milliseconds", "screen": [0.5, 0.86], "at": 1.6, "color": C}],
   "cast": [cat(0.86, 0.84, 0.2, shot=1)]},
 "b06-tokens": {"scene": "tokenizer", "shots": [{"view": "wide"}, {"view": "tokens", "start": 7.4}, {"view": "wide", "start": 14.5}],
   "actions": [{"name": "split", "at": 3.8}, {"name": "number", "at": 15.0}, {"name": "embed", "at": 19.4}],
   "labels": [{"text": "Fragments of a rare word", "anchor": "rare", "at": 10.6, "until": 14.4},
              {"text": "cat is token 9059", "anchor": "id", "at": "word:nine"}],
   "hud": [{"text": "OpenAI's tokenizer: about 200,000 pieces", "screen": [0.5, 0.9], "at": 15.0, "until": "word:cat", "color": C}],
   "cast": [cat(0.88, 0.9, 0.24, shot=0), guide(0.1, 0.9, 0.28, shot=2)]},
 "b07-space": {"scene": "embedding-space",
   "shots": [{"view": "flat"}, {"view": "wide", "start": 7.5}, {"view": "animals", "start": 19.8}, {"view": "wide", "start": 26.5}],
   "actions": [{"name": "lift", "at": 7.8}, {"name": "dims", "at": 10.2}, {"name": "point", "at": 13.4}],
   "labels": [{"text": "Cat near dog", "anchor": "dog", "at": 24.9, "until": 26.4}, {"text": "Far: carburettor", "anchor": "carburettor", "at": 26.8}],
   "hud": [{"text": "2,880 numbers per token", "screen": [0.5, 0.9], "at": 14.6, "until": 19.7, "color": W}],
   "cast": [guide(0.88, 0.9, 0.28, shot=1)]},
 "b08-weights": {"scene": "model-layers", "shots": [{"view": "wide"}, {"view": "layer", "start": 15.0}, {"view": "wide", "start": 19.3}],
   "actions": [{"name": "pass", "at": 0.4}, {"name": "attend", "at": 24.0}],
   "labels": [{"text": "Weights", "anchor": "weights", "at": 15.6}],
   "counter": {"template": "{:,} weights", "from": 1000000, "to": 117000000000, "screen": [0.5, 0.88], "start": 15.0, "end": 18.8, "curve": "exp", "color": W},
   "cast": [guide(0.13, 0.9, 0.3, shot=0), guide(0.12, 0.9, 0.3, shot=2)]},
 "b09-attention": {"scene": "model-layers", "shots": [{"view": "wide"}, {"view": "attention", "start": 7.3}],
   "actions": [{"name": "pass", "at": 2.3}, {"name": "attend", "at": 8.4}],
   "labels": [{"text": "36 layers", "anchor": "stack", "at": 0.3, "until": 7.0}, {"text": "Attention", "anchor": "attention", "at": 9.2}],
   "cast": [cat(0.16, 0.9, 0.2, shot=0)]},
 "b10-experts": {"scene": "experts", "params": {"tokens": 6},
   "shots": [{"view": "wide"}, {"view": "router", "start": 9.0}, {"view": "grid", "start": 17.9}],
   "actions": [{"name": "route", "at": 5.8}],
   "labels": [{"text": "128 experts", "anchor": "grid", "at": 6.4, "until": 9.0}, {"text": "Router picks 4", "anchor": "router", "at": 9.4}],
   "hud": [{"text": "about 10 billion operations per token", "screen": [0.5, 0.9], "at": 21.6, "color": W}],
   "cast": [cat(0.87, 0.9, 0.22, shot=1)]},
 "b11-scores": {"scene": "next-token", "shots": [{"view": "bars"}, {"view": "wide", "start": 9.2}],
   "actions": [{"name": "score", "at": 3.0}, {"name": "pick", "at": 10.5}, {"name": "loop", "at": 18.9}],
   "labels": [{"text": "Illustrative scores", "anchor": "bars", "at": 4.6, "until": 9.0}, {"text": "Picked", "anchor": "chosen", "at": 11.0}]},
 "b12-loop": {"scene": "model-layers", "shots": [{"view": "wide"}, {"view": "layer", "start": 8.0}],
   "actions": [{"name": "pass", "at": 0.2}, {"name": "attend", "at": 15.5}],
   "hud": [{"text": "one full trip per token", "screen": [0.5, 0.9], "at": 5.2, "color": W}],
   "cast": [cat(0.84, 0.88, 0.2, shot=0)]},
 # reading the question: every desk busy
 "b13-prefill": {"scene": "chip-factory", "params": {"busy": True, "truck_x": -5.6},
   "shots": [{"view": "wide"}, {"view": "workers", "start": 6.8}],
   "hud": [{"text": "Reading your question: all at once", "screen": [0.5, 0.9], "at": 1.6, "until": 9.2, "color": C}],
   "cast": [guide(0.12, 0.88, 0.28, shot=0)]},
 # the trouble: the weights come by truck
 "b14-fetch": {"scene": "chip-factory", "shots": [{"view": "road"}, {"view": "wide", "start": F(0.62)}],
   "actions": [{"name": "deliver", "at": F(0.08)}],
   "labels": [{"text": "5 GB of weights per token", "anchor": "truck", "at": "word:five"}],
   "cast": [guide(0.86, 0.9, 0.32, shot=0)]},
 "b15-race": {"scene": "chip-factory", "params": {"truck_x": -6.6},
   "shots": [{"view": "workers"}, {"view": "road", "start": "word:memory"}, {"view": "wide", "start": "word:truck"}],
   "actions": [{"name": "deliver", "at": "word:six"}],
   "labels": [{"text": "4 µs of work", "anchor": "desk", "at": "word:four"}, {"text": "600 µs on the road", "anchor": "truck", "at": "word:six"}],
   "hud": [{"text": "about 2,500 trillion operations a second", "screen": [0.5, 0.1], "at": F(0.06), "until": "word:ten", "color": W},
           {"text": "over 100x longer to fetch than to use", "screen": [0.5, 0.12], "at": "word:truck", "color": W}],
   "cast": [guide(0.86, 0.9, 0.3, shot=1), cat(0.88, 0.9, 0.2, shot=2)]},
 "b16-idle": {"scene": "chip-factory", "shots": [{"view": "workers"}, {"view": "wide", "start": 6.4}],
   "hud": [{"text": "Idle more than 99% of the time", "screen": [0.5, 0.1], "at": 2.8, "until": 6.3, "color": W},
           {"text": "Memory bound", "screen": [0.5, 0.9], "at": 6.6, "color": C}]},
 "b17-energy": {"scene": "compare", "params": {"items": "Multiply two 32-bit numbers:3.7:3.7 picojoules|Read 32 bits from a DRAM chip:640:640 picojoules", "mode": "grow"},
   "shots": [{"view": "wide"}], "actions": [{"name": "run", "at": 3.2}],
   "hud": [{"text": "Horowitz, ISSCC 2014 (45 nm)", "screen": [0.5, 0.1], "at": 3.4, "color": C}],
   "cast": [{"who": "shocked", "screen": [0.92, 0.93], "height": 0.25}]},
 "b18-wire": {"scene": "wire-trip", "shots": [{"view": "wire"}, {"view": "wide", "start": 6.7}],
   "actions": [{"name": "send", "at": 0.5}, {"name": "local", "at": 9.5}],
   "labels": [{"text": "Short trip", "anchor": "register", "at": 10.0}],
   "cast": [cat(0.1, 0.86, 0.2, shot=1, hop=False, walk=[0.35, 0.0])]},
 "b19-close": {"scene": "hbm-stack", "shots": [{"view": "wide"}], "actions": [{"name": "explode", "at": 3.6}, {"name": "signal", "at": 3.8}],
   "cast": [guide(0.85, 0.9, 0.3)]},
 "b20-tsv": {"scene": "hbm-stack", "shots": [{"view": "tsv"}, {"view": "wires", "start": 6.3}],
   "actions": [{"name": "explode", "at": 0.05}, {"name": "signal", "at": 0.6}],
   "labels": [{"text": "Through silicon vias", "anchor": "tsv", "at": 2.4, "until": 6.2}, {"text": "1,024 wires per stack", "anchor": "wires", "at": 6.8}]},
 "b21-dies": {"scene": "hbm-stack", "shots": [{"view": "gpu"}], "actions": [{"name": "signal", "at": 0.1}, {"name": "explode", "at": 0.5}],
   "labels": [{"text": "Two dies, one GPU", "anchor": "joint", "at": 1.1}],
   "hud": [{"text": "208 billion transistors", "screen": [0.5, 0.88], "at": 2.6, "color": W}],
   "cast": [cat(0.12, 0.9, 0.2)]},
 "b22-euv": {"scene": "tin-source", "shots": [{"view": "wide"}], "actions": [{"name": "flatten", "at": 0.05}, {"name": "ignite", "at": 0.2}],
   "hud": [{"text": "Printed with EUV light", "screen": [0.5, 0.88], "at": 1.1, "color": C}]},
 "b23-capacity": {"scene": "accelerator", "params": {"mode": "batch"}, "shots": [{"view": "wide"}], "actions": [{"name": "compute", "at": 0.2}],
   "labels": [{"text": "8 stacks", "anchor": "memory", "at": 0.8}],
   "hud": [{"text": "about 186 GB per package", "screen": [0.5, 0.88], "at": 1.4, "color": C}],
   "cast": [guide(0.88, 0.9, 0.26)]},
 "b24-batch": {"scene": "batching", "params": {"mode": "batch", "cycles": 7},
   "shots": [{"view": "weights"}, {"view": "wide", "start": 5.1}, {"view": "users", "start": 16.0}],
   "actions": [{"name": "share", "at": 6.0}],
   "labels": [{"text": "Same weights for everyone", "anchor": "weights", "at": 2.2, "until": 5.0}, {"text": "One delivery", "anchor": "memory", "at": 11.4, "until": 15.8}],
   "hud": [{"text": "Batching", "screen": [0.5, 0.9], "at": 16.2, "color": W}],
   "cast": [guide(0.1, 0.9, 0.28, shot=1), cat(0.88, 0.9, 0.2, shot=2)]},
 "b25-cache": {"scene": "batching", "params": {"mode": "cache", "cycles": 9},
   "shots": [{"view": "users"}, {"view": "cache", "start": 10.9}, {"view": "wide", "start": 17.1}],
   "actions": [{"name": "share", "at": 2.0}],
   "labels": [{"text": "KV cache", "anchor": "cache", "at": 11.6}, {"text": "Memory limit", "anchor": "capacity", "at": 18.0}],
   "cast": [cat(0.88, 0.9, 0.2, shot=0)]},
 "b26-bits": {"scene": "bit-width", "shots": [{"view": "number"}, {"view": "wide", "start": 9.2}],
   "actions": [{"name": "shrink", "at": 4.2}, {"name": "flow", "at": 9.4}],
   "hud": [{"text": "117 billion weights fit in 80 GB", "screen": [0.5, 0.9], "at": 12.2, "color": C}],
   "cast": [{"who": "truck", "screen": [0.56, 0.9], "height": 0.13, "shot": 1, "walk": [0.36, 0.0]}]},
 "b27-rack": {"scene": "gpu-rack", "shots": [{"view": "wide"}], "actions": [{"name": "cool", "at": 0.1}, {"name": "link", "at": 5.3}],
   "cast": [guide(0.28, 0.92, 0.22)]},
 "b28-trays": {"scene": "gpu-rack", "shots": [{"view": "front"}, {"view": "wide", "start": 5.5}],
   "actions": [{"name": "slice", "at": 0.6}, {"name": "pull", "at": 7.0}],
   "labels": [{"text": "18 compute trays", "anchor": "compute", "at": 5.8}, {"text": "9 switch trays", "anchor": "switch", "at": 7.2}],
   "hud": [{"text": "72 GPUs + 36 CPUs", "screen": [0.2, 0.86], "at": 1.0, "until": 5.4, "color": W}]},
 "b29-spine": {"scene": "gpu-rack", "shots": [{"view": "back"}, {"view": "wide", "start": 10.8}],
   "actions": [{"name": "link", "at": 0.6}, {"name": "cool", "at": 0.3}],
   "labels": [{"text": "Copper spine, over 3 km", "anchor": "spine", "at": 1.2, "until": 6.2}],
   "hud": [{"text": "1.8 TB/s per GPU", "screen": [0.5, 0.9], "at": 6.6, "until": 10.6, "color": W},
           {"text": "\"a single, massive GPU\" (NVIDIA)", "screen": [0.5, 0.9], "at": 11.2, "color": C}],
   "cast": [cat(0.88, 0.9, 0.2, shot=1)]},
 "b30-slices": {"scene": "gpu-rack", "shots": [{"view": "front"}], "actions": [{"name": "slice", "at": 0.5}, {"name": "link", "at": 0.3}],
   "hud": [{"text": "576 TB/s of memory bandwidth", "screen": [0.24, 0.86], "at": 6.6, "color": W}]},
 "b31-heat": {"scene": "heat-loop", "shots": [{"view": "wide"}], "actions": [{"name": "flow", "at": 0.1}, {"name": "evaporate", "at": 0.3}],
   "cast": [guide(0.12, 0.9, 0.26)]},
 "b32-homes": {"scene": "scale-compare", "params": {"many": 100}, "shots": [{"view": "wide"}], "actions": [{"name": "fill", "at": 0.3}],
   "labels": [{"text": "One rack: ~120 kW", "anchor": "one", "at": 0.5}, {"text": "~100 average US homes", "anchor": "many", "at": 2.6}]},
 "b33-query": {"scene": "compare", "params": {"items": "Average ChatGPT query, per OpenAI:0.34:about 0.34 watt hours", "mode": "grow"},
   "shots": [{"view": "wide"}], "actions": [{"name": "run", "at": 3.4}],
   "hud": [{"text": "an oven for a little over one second", "screen": [0.5, 0.86], "at": 9.4, "until": 12.7, "color": W},
           {"text": "water: about 1/15 of a teaspoon", "screen": [0.5, 0.86], "at": 12.9, "color": C}],
   "cast": [guide(0.15, 0.93, 0.26), cat(0.88, 0.92, 0.2)]},
 "b34-compare": {"scene": "compare", "params": {"items": "ChatGPT query, per OpenAI:0.34:0.34 Wh|Median Gemini prompt, per Google:0.24:0.24 Wh, 0.26 mL", "mode": "grow"},
   "shots": [{"view": "wide"}], "actions": [{"name": "run", "at": 0.5}],
   "hud": [{"text": "not independently verified", "screen": [0.5, 0.12], "at": 7.5, "color": C}]},
 "b35-load": {"scene": "fiber-trip", "shots": [{"view": "building"}, {"view": "wide", "start": 7.4}], "actions": [{"name": "send", "at": 0.2}],
   "counter": {"template": "{:,} kWh a day", "from": 1000, "to": 850000, "screen": [0.5, 0.88], "start": 0.6, "end": 5.6, "curve": "exp", "color": W},
   "hud": [{"text": "a steady ~35 megawatts", "screen": [0.5, 0.12], "at": 5.0, "until": 7.3, "color": W},
           {"text": "~30,000 average US homes", "screen": [0.5, 0.12], "at": 7.6, "color": W}],
   "cast": [cat(0.82, 0.9, 0.2, shot=1)]},
 "b36-share": {"scene": "compare", "params": {"items": "US data centres, 2023:4.4:4.4% of US electricity|Projection for 2028:6.7-12:6.7 to 12%", "mode": "grow"},
   "shots": [{"view": "wide"}], "actions": [{"name": "run", "at": 0.3}],
   "hud": [{"text": "Berkeley Lab report for the US DOE", "screen": [0.5, 0.1], "at": 1.1, "color": C}]},
 "b37-recap-tokens": {"scene": "tokenizer", "shots": [{"view": "wide"}],
   "actions": [{"name": "split", "at": 0.2}, {"name": "number", "at": 1.6}, {"name": "embed", "at": 3.0}],
   "cast": [cat(0.88, 0.9, 0.24)]},
 "b38-recap-fetch": {"scene": "chip-factory", "params": {"truck_x": -6.6}, "shots": [{"view": "road"}, {"view": "workers", "start": F(0.55)}],
   "actions": [{"name": "deliver", "at": F(0.05)}]},
 "b39-recap-rack": {"scene": "gpu-rack", "shots": [{"view": "wide"}], "actions": [{"name": "link", "at": 1.4}, {"name": "cool", "at": 3.6}, {"name": "slice", "at": 0.1}],
   "cast": [guide(0.28, 0.92, 0.22)]},
 "b40-recap-fact": {"scene": "wire-trip", "shots": [{"view": "wide"}], "actions": [{"name": "send", "at": 0.2}, {"name": "local", "at": 3.6}],
   "cast": [cat(0.12, 0.86, 0.2, hop=False, walk=[0.3, 0.0])]},
 "b41-stutter": {"scene": "token-stream", "params": {"fetch": True}, "shots": [{"view": "wide"}, {"view": "low", "start": 4.6}],
   "actions": [{"name": "type", "at": 0.02}, {"name": "stream", "at": 0.1}],
   "cast": [guide(0.1, 0.95, 0.22, shot=0), cat(0.18, 0.96, 0.16, shot=0)]},
}

old = json.loads((EP / 'sourcing' / 'shot_lengths.v1.json').read_text(encoding='utf-8'))


def frac(v, L):
    """Seconds of the first cut -> a fraction of the beat; F fractions and word cues pass through."""
    if isinstance(v, F):
        return float(v)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return round(min(v / L, 0.97), 4)
    return v


for name, beat in B.items():
    L = old[name]
    for key in ("labels", "actions", "hud"):
        for item in beat.get(key, []):
            for t in ("at", "until"):
                if t in item:
                    item[t] = frac(item[t], L)
    for shot in beat.get("shots", []):
        if "start" in shot:
            shot["start"] = frac(shot["start"], L)
    c = beat.get("counter")
    if c:
        for t in ("start", "end"):
            c[t] = frac(c[t], L)
(EP / 'storyboard.json').write_text(json.dumps({"beats": B}, indent=1, ensure_ascii=False), encoding='utf-8')
print(len(B), 'beats')
