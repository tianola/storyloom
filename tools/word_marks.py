"""Exact word times, read from the voice model itself.

    python tools/word_marks.py --episode work/X        # writes vo/word_marks.json, prints the gain over the estimate

Kokoro predicts how many frames every phoneme lasts before it makes any sound; the export we use
just does not return that tensor. Here the graph is extended in memory (the model file is never
changed) with one more output, `duration`, which kokoro-onnx already knows how to turn into phoneme
times (`create_timed`). The narration on disk is not re-made: each line is synthesised again in the
same batches, and its marks are kept only if the audio comes out sample-identical to `vo/<id>.wav`,
so the marks describe exactly the sound in the film.

`create_timed` is not called directly: with timings available it also inserts a pause after every
punctuation mark, which would change the audio. The batches are made the way `create()` makes them
for a model without timings.

Words are matched to phonemes character by character, because espeak links words in context
("that it" is spoken as one phoneme word): every word is phonemised alone, the concatenation is
aligned with the phonemes actually spoken, and a word starts at the spoken phoneme its first
phoneme aligned to.

Needs the `onnx` package (to extend the graph). captions.py uses these marks when they match the
wav on disk and falls back to its estimate otherwise.
"""
import argparse
import difflib
import hashlib
import json
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DURATION_TENSOR = "/encoder/Cast_output_0"     # Round -> Clip -> Cast(int64): frames per token
DEFAULT_MODEL = ROOT.parent.parent.parent / "models" / "kokoro" / "kokoro-v1.0.onnx"


def wav_print(path):
    """Fingerprint of a wav's samples: marks are only valid for the exact audio they were read from."""
    with wave.open(str(path), "rb") as w:
        return hashlib.sha1(w.readframes(w.getnframes())).hexdigest()


def timed_engine(model_path, voices_path):
    """A kokoro-onnx engine whose session also returns per-token durations."""
    import onnx
    import onnxruntime as ort
    from kokoro_onnx import Kokoro

    model = onnx.load(str(model_path))
    names = {o for n in model.graph.node for o in n.output}
    if DURATION_TENSOR not in names:
        raise SystemExit(f"{model_path} has no {DURATION_TENSOR}; this export cannot report durations")
    model.graph.node.append(onnx.helper.make_node("Identity", [DURATION_TENSOR], ["duration"], name="expose_duration"))
    model.graph.output.append(onnx.helper.make_tensor_value_info("duration", onnx.TensorProto.INT64, None))
    session = ort.InferenceSession(model.SerializeToString(), providers=["CPUExecutionProvider"])
    engine = Kokoro(str(model_path), str(voices_path))   # from_session() insists on a model path
    engine.sess = session
    engine.has_timings = True
    return engine


def spoken_line(engine, text, voice, speed):
    """(int16 audio, [(phoneme_char, start_s, end_s)]) made exactly as `create()` makes the audio."""
    style, _, batches = engine._prepare(text, voice, speed, "en-us", False, 0.25, 0.1)
    audio, spoken = engine._create_batches(batches, style, speed, True)
    pcm = (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16)
    return pcm, [(s.phoneme, s.start, s.end) for s in spoken]


def word_marks(engine, text, spoken):
    """[(word, start_s, end_s)] for `text.split()`, from the phonemes actually spoken."""
    words = text.split()
    heard = [(p, a, b) for p, a, b in spoken if not p.isspace()]
    said = "".join(p for p, _, _ in heard)
    alone, starts = "", []
    for w in words:
        starts.append(len(alone))
        alone += "".join(engine.tokenizer.phonemize(w, "en-us").split())
    to_said = {}
    for block in difflib.SequenceMatcher(None, alone, said, autojunk=False).get_matching_blocks():
        for k in range(block.size):
            to_said[block.a + k] = block.b + k
    if not heard:
        return []
    marks = []
    for i, w in enumerate(words):
        lo, hi = starts[i], (starts[i + 1] if i + 1 < len(words) else len(alone))
        hits = [to_said[j] for j in range(lo, hi) if j in to_said]
        marks.append([w, hits[0] if hits else None, hits[-1] if hits else None])
    # a word none of whose phonemes aligned sits between its neighbours
    for i, m in enumerate(marks):
        if m[1] is None:
            prev = next((marks[j][2] for j in range(i - 1, -1, -1) if marks[j][2] is not None), 0)
            nxt = next((marks[j][1] for j in range(i + 1, len(marks)) if marks[j][1] is not None), len(heard) - 1)
            m[1], m[2] = prev, max(prev, nxt)
    out = []
    for i, (w, a, b) in enumerate(marks):
        start = heard[a][1]
        end = heard[b][2]
        if i + 1 < len(marks):
            end = min(end, heard[marks[i + 1][1]][1]) if marks[i + 1][1] > a else end
        out.append((w, round(start, 3), round(max(end, start + 0.02), 3)))
    return out


def build(episode, model_path, voices_path, log=print):
    """Write vo/word_marks.json for every line whose re-synthesis matches its wav."""
    episode = Path(episode)
    request = json.loads((episode / "script" / "narration-request.json").read_text(encoding="utf-8"))
    voice, speed = request["voice"], request.get("speed", 1.0)
    engine = None
    marks, skipped = {}, []
    for u in request["utterances"]:
        wav = episode / "vo" / f"{u['id']}.wav"
        if not wav.exists():
            skipped.append(u["id"])
            continue
        # an ElevenLabs line carries its own character timing from the synthesis itself
        align = episode / "vo" / f"{u['id']}.align.json"
        if (u.get("voice") or voice).startswith("eleven:"):
            a = json.loads(align.read_text(encoding="utf-8")) if align.exists() else None
            if not a or a.get("text") != u["text"]:
                skipped.append(u["id"])
                continue
            sys.path.insert(0, str(ROOT / "python"))
            import eleven
            marks[u["id"]] = {"wav": wav_print(wav), "text": u["text"],
                              "words": [list(w) for w in eleven.word_marks(u["text"], a["alignment"])],
                              "phones": [list(c) for c in eleven.phones(a["alignment"])]}
            continue
        if engine is None:
            engine = timed_engine(model_path, voices_path)
        # each line in its own voice, from the text actually synthesised (a respelling keeps the word count)
        said_text = u.get("spoken") or u["text"]
        pcm, spoken = spoken_line(engine, said_text, u.get("voice") or voice, speed)
        with wave.open(str(wav), "rb") as w:
            disk = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        if len(pcm) != len(disk) or int(np.abs(pcm.astype(np.int32) - disk.astype(np.int32)).max()) > 1:
            skipped.append(u["id"])
            continue
        words = [[w, a, b] for w, (_, a, b) in zip(u["text"].split(), word_marks(engine, said_text, spoken))]
        phones = [[p, round(a, 3), round(b, 3)] for p, a, b in spoken]
        marks[u["id"]] = {"wav": wav_print(wav), "text": u["text"], "words": words, "phones": phones}
    out = episode / "vo" / "word_marks.json"
    out.write_text(json.dumps(marks, indent=0, ensure_ascii=False), encoding="utf-8")
    log(f"word marks for {len(marks)} lines -> {out}" + (f"; not identical, left to the estimate: {skipped}" if skipped else ""))
    return marks


def compare(episode, marks):
    """Median and 90th-percentile |exact - estimate| of word starts, against captions.place_words."""
    sys.path.insert(0, str(ROOT / "tools"))
    import captions
    errs = []
    for uid, m in marks.items():
        rate, samples = captions.read_wav(Path(episode) / "vo" / f"{uid}.wav")
        a, b = captions.voiced_span(samples, rate)
        est = captions.place_words(m["text"], a, b)
        errs += [abs(e[1] - x[1]) for e, x in zip(est, m["words"])]
    errs = np.array(errs)
    return {"words": len(errs), "median_s": round(float(np.median(errs)), 3),
            "p90_s": round(float(np.percentile(errs, 90)), 3), "max_s": round(float(errs.max()), 3)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", type=Path, required=True)
    ap.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--voices", type=Path, default=None)
    args = ap.parse_args(argv)
    voices = args.voices or args.model.with_name("voices-v1.0.bin")
    try:
        import onnx  # noqa: F401
    except ImportError:
        print("word_marks: the onnx package is not installed; captions keep their estimated word times")
        return 0
    marks = build(args.episode, args.model, voices)
    if marks:
        print("estimate error:", compare(args.episode, marks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
