"""Word timings and captions, derived from the narration that was actually synthesised.

    python tools/captions.py --episode work/X                    # words.json, word_timing.json, captions.srt/.vtt
    python tools/captions.py --episode work/X --attach MASTER --out OUT [--burn]

Kokoro returns audio without word marks, so each word is placed inside its utterance by the length
of the word (plus a pause after punctuation), across the span where the utterance is actually
voiced (leading and trailing silence found from the waveform). It is an estimate, good to a few
tenths of a second, which is what captions and `word:` label times need.

Outputs, under `<episode>/vo/` unless noted:
  words.json          [{"uid", "word", "start", "end"}] in film seconds
  captions.srt/.vtt   cues of at most two lines of 42 characters, 1-6.5 s each
  ../word_timing.json {beat: [{"word", "start"}]} with start relative to the beat (storyboard_beats.py)
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LINE_CHARS = 42
MAX_CUE_S = 6.5
MIN_CUE_S = 1.0
PAUSE_AFTER = {",": 3.0, ";": 4.0, ":": 4.0, ".": 6.0, "!": 6.0, "?": 6.0, "—": 4.0, "-": 0.0}


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        rate, width, channels = w.getframerate(), w.getsampwidth(), w.getnchannels()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16 if width == 2 else np.uint8)
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return rate, data.astype(np.float64) / 32768.0


def voiced_span(samples, rate, floor_db=-45.0):
    """(start, end) seconds where the utterance is louder than `floor_db` under its own peak."""
    hop = max(1, rate // 100)
    n = len(samples) // hop
    if n == 0:
        return 0.0, len(samples) / rate
    rms = np.sqrt((samples[:n * hop].reshape(n, hop) ** 2).mean(axis=1))
    loud = np.nonzero(rms > rms.max() * 10 ** (floor_db / 20))[0]
    if len(loud) == 0:
        return 0.0, len(samples) / rate
    return loud[0] * hop / rate, min(len(samples), (loud[-1] + 1) * hop) / rate


def place_words(text, start, end):
    """[(word, start, end)] spreading `text` over [start, end] by word length and punctuation."""
    tokens = text.split()
    if not tokens:
        return []
    parts = []
    for token in tokens:
        core = len(re.sub(r"[^\w']", "", token)) + 1.0
        pause = PAUSE_AFTER.get(token[-1], 0.0)
        parts.append((core, pause))
    # no pause after the final word: the voiced span already ends there
    parts[-1] = (parts[-1][0], 0.0)
    unit = (end - start) / sum(core + pause for core, pause in parts)
    out, t = [], start
    for token, (core, pause) in zip(tokens, parts):
        out.append((token, t, t + core * unit))
        t += (core + pause) * unit
    return out


def word_timings(episode, manifest=None):
    episode = Path(episode)
    manifest = manifest or json.loads((episode / "vo" / "manifest.json").read_text(encoding="utf-8"))
    words = []
    for u in manifest["utterances"]:
        rate, samples = read_wav(episode / "vo" / u["file"])
        offset = u["startSample"] / manifest["sampleRate"]
        a, b = voiced_span(samples, rate)
        for word, s, e in place_words(u["text"], a, b):
            words.append({"uid": u["id"], "word": word, "start": round(offset + s, 3), "end": round(offset + e, 3)})
    return words


def beat_word_timing(episode, words):
    """{beat: [{"word", "start"}]} with starts relative to the first word of the beat's utterances."""
    shots = json.loads((Path(episode) / "shots.json").read_text(encoding="utf-8"))
    out, origin = {}, {}
    for w in words:
        name = shots[w["uid"]]["name"]
        origin.setdefault(name, w["start"])
        out.setdefault(name, []).append({"word": w["word"], "start": round(w["start"] - origin[name], 3)})
    return out


def wrap(text):
    """Split a cue into at most two balanced lines of LINE_CHARS."""
    if len(text) <= LINE_CHARS:
        return [text]
    best = None
    for m in re.finditer(" ", text):
        a, b = text[:m.start()], text[m.end():]
        if len(a) <= LINE_CHARS and len(b) <= LINE_CHARS:
            score = abs(len(a) - len(b))
            if best is None or score < best[0]:
                best = (score, [a, b])
    return best[1] if best else [text[:LINE_CHARS], text[LINE_CHARS:]]


def cues(words):
    """[(start, end, text)]: break after sentence ends and commas near a full line, never past two lines."""
    out, cur = [], []

    def flush():
        if cur:
            out.append([cur[0]["start"], cur[-1]["end"], " ".join(w["word"] for w in cur)])
            cur.clear()

    for w in words:
        trial = " ".join(x["word"] for x in cur + [w])
        if cur and (len(trial) > 2 * LINE_CHARS or w["end"] - cur[0]["start"] > MAX_CUE_S):
            flush()
        cur.append(w)
        text = " ".join(x["word"] for x in cur)
        if w["word"][-1] in ".!?" or (w["word"][-1] in ",;:" and len(text) > 0.6 * LINE_CHARS):
            flush()
    flush()
    for i, cue in enumerate(out):
        limit = out[i + 1][0] - 0.04 if i + 1 < len(out) else cue[1] + MIN_CUE_S
        cue[1] = max(cue[1], min(cue[0] + MIN_CUE_S, limit))
    return [tuple(c) for c in out]


def stamp(t, comma=True):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{',' if comma else '.'}{ms:03d}"


def write_srt(cue_list, path):
    body = "\n".join(f"{i}\n{stamp(a)} --> {stamp(b)}\n" + "\n".join(wrap(t)) + "\n"
                     for i, (a, b, t) in enumerate(cue_list, 1))
    Path(path).write_text(body, encoding="utf-8")


def write_vtt(cue_list, path):
    body = "WEBVTT\n\n" + "\n".join(f"{stamp(a, False)} --> {stamp(b, False)}\n" + "\n".join(wrap(t)) + "\n"
                                    for a, b, t in cue_list)
    Path(path).write_text(body, encoding="utf-8")


def write_all(episode, manifest=None):
    """Write every caption artefact for an episode; returns the .srt path."""
    episode = Path(episode)
    words = word_timings(episode, manifest)
    vo = episode / "vo"
    (vo / "words.json").write_text(json.dumps(words, indent=1), encoding="utf-8")
    if (episode / "shots.json").exists():
        (episode / "word_timing.json").write_text(json.dumps(beat_word_timing(episode, words), indent=1), encoding="utf-8")
    cue_list = cues(words)
    write_srt(cue_list, vo / "captions.srt")
    write_vtt(cue_list, vo / "captions.vtt")
    return vo / "captions.srt"


def attach(master, srt, output, burn=False):
    """Copy `master` to `output` with the captions as a soft stream, or burned into the picture."""
    master, srt, output = Path(master), Path(srt), Path(output)
    if burn:
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "c.srt"
            local.write_bytes(srt.read_bytes())
            style = "FontName=Arial,FontSize=22,Outline=2,Shadow=0,MarginV=48,Alignment=2"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(master.resolve()),
                            "-vf", f"subtitles=c.srt:force_style='{style}'", "-c:v", "libx264", "-crf", "18",
                            "-preset", "medium", "-c:a", "copy", "-movflags", "+faststart",
                            str(output.resolve())], check=True, cwd=tmp)
        return output
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(master), "-i", str(srt),
                    "-map", "0:v", "-map", "0:a", "-map", "1:0", "-c", "copy", "-c:s", "mov_text",
                    "-metadata:s:s:0", "language=eng", "-movflags", "+faststart", str(output)], check=True)
    return output


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", type=Path, required=True)
    ap.add_argument("--attach", type=Path, help="a master to copy with captions added")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--burn", action="store_true")
    args = ap.parse_args(argv)
    episode = args.episode if args.episode.is_absolute() else ROOT / args.episode
    srt = write_all(episode)
    print(f"captions -> {srt}")
    if args.attach:
        if not args.out:
            raise SystemExit("--attach needs --out")
        print(f"master with captions -> {attach(args.attach, srt, args.out, args.burn)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
