"""Mouth shapes for characters who speak on screen, timed to the voice.

    python tools/lip_sync.py --episode work/X      # writes mouth_timing.json

A beat's render starts where its first line's wav starts (the assembler slices the beat from the
first utterance's startSample), lead-in silence included. So every time here is measured from that
point, not from the first spoken word the way word_timing.json is: a mouth timed from the first
word would open early by the silence before it.

Shapes come from the phonemes Kokoro actually spoke (vo/word_marks.json `phones`, exact for the wav
on disk). A line without exact marks falls back to opening and closing once per word across the
voiced span, and the output says which lines did. Inner-voice lines (`[name:thought]`) are listed
with mode "thought" and no shapes: the character is shown thinking, not talking. Untagged lines
belong to "narrator" (the guide, who is on screen in some beats).

Shapes: rest (lips together, relaxed), closed (m b p), half, open (a-like vowels), wide (shouting is
chosen by the storyboard, not here). Each shape is held at least `MIN_FRAMES` frames, which is what
reads at pixel-art size; shorter runs are folded into their neighbour.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

FPS = 30
MIN_FRAMES = 2
PAUSE_S = 0.12                 # a gap between phonemes longer than this rests the mouth
CLOSED = set("mbp")
OPEN = set("aɑæɐɔʌɒɜ")
VOWELS = OPEN | set("eɛiɪoʊuəɚɝyøœɘɵɤɯ")
MARKS = set("ˈˌːˑ̩̃ ")


def shape_of(phoneme):
    """The mouth shape for one spoken phoneme character, or None for stress and length marks."""
    if phoneme in MARKS or phoneme.isspace():
        return None
    if phoneme in CLOSED:
        return "closed"
    if phoneme in OPEN:
        return "open"
    return "half"


def frames_from_phones(phones, fps=FPS):
    """[shape per frame] over the line, from [(phoneme, start, end)] in line seconds."""
    spans = [(shape_of(p), a, b) for p, a, b in phones]
    spans = [s for s in spans if s[0]]
    if not spans:
        return []
    n = int(round(spans[-1][2] * fps)) + 1
    out = ["rest"] * n
    for k, (shape, a, b) in enumerate(spans):
        f0, f1 = int(round(a * fps)), max(int(round(a * fps)) + 1, int(round(b * fps)))
        for f in range(f0, min(f1, n)):
            out[f] = shape
        # a short gap to the next phoneme carries the shape over; a pause rests the mouth
        if k + 1 < len(spans) and spans[k + 1][1] - b <= PAUSE_S:
            for f in range(min(f1, n), min(int(round(spans[k + 1][1] * fps)), n)):
                out[f] = shape
    return out


def frames_from_words(words, fps=FPS):
    """Fallback without phonemes: each word opens to half, then open, and closes at its end."""
    if not words:
        return []
    n = int(round(words[-1][2] * fps)) + 1
    out = ["rest"] * n
    for _, a, b in words:
        f0, f1 = int(round(a * fps)), int(round(b * fps))
        mid = (f0 + f1) // 2
        for f in range(f0, min(f1, n)):
            out[f] = "half" if f < mid or f >= f1 - 1 else "open"
    return out


def runs(frames, min_frames=MIN_FRAMES):
    """[(shape, first_frame, end_frame)] with every run at least `min_frames` long (a run shorter
    than that takes its predecessor's shape; a short first run takes the next one's)."""
    out = []
    for f, shape in enumerate(frames):
        if out and out[-1][0] == shape:
            out[-1][2] = f + 1
        else:
            out.append([shape, f, f + 1])
    merged = []
    for r in out:
        if merged and (r[2] - r[1] < min_frames or merged[-1][0] == r[0]):
            merged[-1][2] = r[2]
        else:
            merged.append(r)
    if len(merged) > 1 and merged[0][2] - merged[0][1] < min_frames:
        merged[1][1] = merged[0][1]
        merged.pop(0)
    return [tuple(r) for r in merged]


def line_visemes(frames, offset, fps=FPS):
    """[[shape, t0, t1]] in beat seconds for a line starting `offset` s into its beat."""
    return [[s, round(offset + a / fps, 3), round(offset + b / fps, 3)] for s, a, b in runs(frames)]


def build(episode, log=print):
    episode = Path(episode)
    import captions
    manifest = json.loads((episode / "vo" / "manifest.json").read_text(encoding="utf-8"))
    from edit import cutlist
    cut = cutlist.episode_cut(episode)
    shots = None if cut else json.loads((episode / "shots.json").read_text(encoding="utf-8"))
    marks_path = episode / "vo" / "word_marks.json"
    marks = json.loads(marks_path.read_text(encoding="utf-8")) if marks_path.exists() else {}
    rate = manifest["sampleRate"]
    out, origin, estimated = {}, {}, []
    placements = []                    # (beat, utterance, seconds into the beat)
    if cut:
        # a line can play across several beats; each beat it is on screen in gets its mouth
        starts = {l["id"]: l["start"] for l in cutlist.line_clock(manifest, episode / "vo")}
        spans = cutlist.beat_spans(cut)
        for u in manifest["utterances"]:
            for beat, span in spans.items():
                if u["id"] in span["lines"]:
                    placements.append((beat, u, starts[u["id"]] - span["origin"]))
    else:
        for u in manifest["utterances"]:
            beat = shots[u["id"]]["name"]
            origin.setdefault(beat, u["startSample"])
            placements.append((beat, u, (u["startSample"] - origin[beat]) / rate))
    for beat, u, offset in placements:
        # untagged lines are the narrator's: the guide talks on screen too
        entry = {"uid": u["id"], "speaker": u.get("speaker", "narrator"), "mode": u.get("mode", "say"),
                 "start": round(offset, 3), "end": round(offset + u["samples"] / rate, 3), "visemes": []}
        if entry["mode"] == "say":
            exact = captions.exact_marks(episode, u)
            phones = (marks.get(u["id"]) or {}).get("phones") if exact is not None else None
            if phones:
                frames = frames_from_phones(phones)
            else:
                estimated.append(u["id"])
                placed = exact
                if placed is None:
                    r, samples = captions.read_wav(episode / "vo" / u["file"])
                    a, b = captions.voiced_span(samples, r)
                    placed = captions.place_words(u["text"], a, b)
                frames = frames_from_words(placed)
            entry["visemes"] = line_visemes(frames, offset)
        out.setdefault(beat, []).append(entry)
    path = episode / "mouth_timing.json"
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    spoken = sum(len(v) for v in out.values())
    log(f"mouth timing for {spoken} character lines -> {path}"
        + (f"; estimated from word spans (no exact phonemes): {estimated}" if estimated else ""))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", type=Path, required=True)
    args = ap.parse_args(argv)
    build(args.episode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
