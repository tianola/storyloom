"""Scratch check: does the local TTS narration actually say the intended words?

Transcribes each utterance wav with faster-whisper (CPU, int8) and reports the
word error rate against the text the script asked for. base.en is a small model, so
a low WER here is a floor on intelligibility, not a measurement of it.

Spelled-out numbers are not counted as errors: the script text is what the TTS must
*speak* ("eight point eight million") and Whisper writes what it *hears* as digits
("8.8 million"), so `normalise` collapses each run of numeric material to one token on
both sides. A figure the narrator skipped still shows up as a missing run; whether a
figure is arithmetically right is the claims ledger's job, not this tool's.

Run: python tools/asr_wer.py work/episode-artemis-ii [--limit 6]
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"F:/AI-PROJECTS/longform-explainer")
WORDS = re.compile(r"[a-z0-9]+")
NUMBER_WORDS = frozenset(
    """
    zero one two three four five six seven eight nine ten eleven twelve thirteen
    fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty
    sixty seventy eighty ninety hundred thousand million billion trillion point
    """.split()
)


def pcm(path: Path):
    """Decode with ffmpeg; this venv's PyAV rejects the keyword faster-whisper passes."""
    import numpy as np

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-acodec", "pcm_f32le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True,
        check=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32)


def words(text: str) -> list[str]:
    return WORDS.findall(text.lower())


def normalise(text: str) -> list[str]:
    """Tokens with each maximal run of numeric material replaced by a single `N`.

    The tokenizer drops punctuation, so a run spans commas and decimals: "1, 2026" and
    "twenty twenty-six" are both one `N`, and `point` plus the scale words join the run
    so "8.8 million" and "eight point eight million" collapse identically.
    """
    tokens: list[str] = []
    in_run = False
    for token in words(text):
        if token.isdigit() or token in NUMBER_WORDS:
            if not in_run:
                tokens.append("N")
            in_run = True
        else:
            in_run = False
            tokens.append(token)
    return tokens


def wer(reference: list[str], hypothesis: list[str]) -> float:
    rows = len(reference) + 1
    cols = len(hypothesis) + 1
    prev = list(range(cols))
    for i in range(1, rows):
        cur = [i] + [0] * (cols - 1)
        for j in range(1, cols):
            cost = 0 if reference[i - 1] == hypothesis[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[-1] / max(1, len(reference))


def narration_dir(job: Path) -> Path | None:
    """The utterance directory, including the pre-music-bed name it used to have."""
    return next((job / d for d in ("vo", "narration") if (job / d).is_dir()), None)


def main(argv: list[str]) -> int:
    from faster_whisper import WhisperModel

    args = [a for a in argv if not a.startswith("--")]
    job = Path(args[0]) if args else ROOT / "work/episode-artemis-ii"
    narration = narration_dir(job)
    if narration is None:
        sys.exit(f"no vo/ or narration/ directory under {job}")
    manifest = json.loads((narration / "manifest.json").read_text(encoding="utf-8"))
    items = manifest["utterances"]
    if "--limit" in argv:
        items = items[:int(argv[argv.index("--limit") + 1])]

    model = WhisperModel("base.en", device="cpu", compute_type="int8", local_files_only=True)
    total_ref = 0
    total_dist = 0.0
    print(f"{'id':6} {'sec':>6} {'wer':>6}  hypothesis")
    for item in items:
        segments, _ = model.transcribe(pcm(narration / item["file"]), language="en", beam_size=1)
        heard = " ".join(seg.text for seg in segments)
        ref, hyp = normalise(item["text"]), normalise(heard)
        distance = wer(ref, hyp)
        total_ref += len(ref)
        total_dist += distance * len(ref)
        print(f"{item['id']:6} {item['samples'] / manifest['sampleRate']:6.2f} {distance:6.3f}  {heard}")

    print(f"\noverall WER = {total_dist / max(1, total_ref):.3f} over {total_ref} reference tokens")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
