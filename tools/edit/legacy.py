"""An episode cut before cut lists existed, read as a cut list.

`shots.json` puts one visual under each narration line. As a cut list that is one shot per line,
`[line start, line end)` on the film clock, every transition a cut. The in-point is the running sum
of the earlier lines' lengths on the same clip — exactly the cursor `build_segments` keeps — and a
card, drawn per sentence, always starts at zero. The shot times are *not* snapped to frames: the
old cutter rounds each boundary on the film clock when it slices, and `cutlist.render_plan` does
the same rounding, so the frame counts agree with what an old episode has always been cut to.
"""
from edit.cutlist import SCHEMA

PER_UTTERANCE = ("cards",)


def from_shots(shot_map, manifest, *, fps):
    """A resolved cut from `{uid: (kind, name, ...)}` and the narration manifest."""
    rate = int(manifest["sampleRate"])
    consumed, clock, shots = {}, 0, []
    for u in manifest["utterances"]:
        uid = u["id"]
        kind, name = shot_map[uid][:2]
        begin = u.get("startSample", clock)
        clock = u.get("endSample", begin + u["samples"])
        clip = f"card-{uid}" if kind in PER_UTTERANCE else name
        key = (kind, clip)
        start_in = consumed.get(key, 0.0)
        length = u["samples"] / rate
        consumed[key] = start_in + length
        shots.append({
            "id": uid, "start": begin / rate, "end": clock / rate,
            "source": {"kind": kind, "name": clip, "in": start_in, "out": start_in + length},
            "transition_in": {"type": "cut", "dur": 0.0}, "speed": 1.0, "overlays": [],
            "provenance": "legacy", "lines": [uid],
        })
    return {"schema": SCHEMA, "origin": "legacy shots.json", "fps": fps, "lead_frames": 0,
            "duration": clock / rate, "shots": shots}
