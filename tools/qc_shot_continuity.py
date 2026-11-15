"""Check that consecutive segments over one beat are consecutive slices, not replays.

The episode read as motion graphics because every utterance took its beat from frame 0: a 5 s clip
looped under a 15 s sentence, so the camera move restarted mid-word. The fix lives in two places
(beat length, then per-utterance offsets) and neither is visible to the existing QC gates — total
duration, loudness and caption sync all stay correct while the rewind keeps happening. This script
tests the signature directly, on decoded pixels.

    python tools/qc_shot_continuity.py --episode work/episode-artemis-ii
    python tools/qc_shot_continuity.py --episode work/episode-artemis-ii \
        --segments work/episode-artemis-ii/qc/stale-segments-r14

Passing the archived pre-fix segments is the calibration: those first frames should score as
replays, and the freshly built ones should not. Which film is being judged, and which beats it
cuts between, come from that episode's own `shots.json` — this tool used to import the assembler's
hardcoded visual map, so it could only ever describe the one episode that map was written for.
"""

import argparse
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PROJECT_ROOT))

from assemble_episode import CONTRACT, load_manifest, probe_duration  # noqa: E402
from workflow.episode import (require_coverage, resolve, segments_dir,  # noqa: E402
                              shots)

# Two different defects, two different signatures, measured against the archived pre-fix build:
#
#   replay   - every segment of a beat opens on the beat's own frame 0, so the first frames are
#              identical to each other. This is the looped-5 s-beat bug the episode actually had
#              (stale-segments-r14 scores 0.00-0.02 here).
#   cut      - a slice that does not continue where the previous one ended. Pre-fix that number is
#              large by construction (5.9-54.6 on the same archive), because the camera had already
#              moved; post-fix it should sit near one utterance of motion. CONTINUITY_MAX is a first
#              guess and the fresh run's printed deltas are the calibration - a verdict within an
#              order of magnitude of the bound means "recalibrate", not "pass".
CONTINUITY_MAX = 4.0
REPLAY_EPS = 0.05
TAIL_OFFSET = 0.1


def frame(path, when):
    """One decoded frame as a greyscale float array, grabbed at `when` seconds into the clip."""
    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / "f.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error",
                        "-ss", f"{max(0.0, when):.3f}", "-i", str(path),
                        "-frames:v", "1", str(png)], capture_output=True, check=True)
        return np.asarray(Image.open(png).convert("L"), dtype=np.float64)


def first_frame(path):
    return frame(path, 0.0)


def last_frame(path):
    return frame(path, probe_duration(path) - TAIL_OFFSET)


def mean_abs(a, b):
    return float(np.mean(np.abs(a - b)))


def groups(shot_map):
    """Utterance ids per moving visual, in narration order, keeping multi-utterance beats only.

    Cards are excluded: they are drawn to the exact length of one utterance, so a card can never
    be a beat replayed under two sentences, and including them would report a defect the layer
    cannot have.
    """
    by_visual = defaultdict(list)
    for uid, entry in shot_map.items():
        if entry[0] == "cards":
            continue
        by_visual[entry[1]].append(uid)
    ordered = {k: sorted(v) for k, v in by_visual.items()}
    return {k: v for k, v in ordered.items() if len(v) > 1}


def check(shot_map, seg_dir):
    """Return (failures, notes) over every beat that carries more than one utterance."""
    failures, notes = [], []
    for visual, uids in sorted(groups(shot_map).items()):
        paths = [seg_dir / f"{uid}.mp4" for uid in uids]
        missing = [p.name for p in paths if not p.exists()]
        if missing:
            notes.append(f"{visual}: skipped, missing {missing}")
            continue
        firsts = [first_frame(p) for p in paths]
        lasts = [last_frame(p) for p in paths[:-1]]
        replays = [mean_abs(firsts[0], f) for f in firsts[1:]]
        deltas = [mean_abs(l, f) for l, f in zip(lasts, firsts[1:])]
        for uid, delta in zip(uids[1:], replays):
            if delta < REPLAY_EPS:
                failures.append(f"{visual}: {uid} opens on the same frame as {uids[0]} "
                                f"({delta:.3f}) -- the beat was replayed, not sliced")
        for uid, delta in zip(uids[1:], deltas):
            if delta > CONTINUITY_MAX:
                failures.append(f"{visual}: {uid} opens {delta:.2f} away from the previous "
                                f"segment's end -- discontinuous cut")
        print(f"  {visual}: {len(uids)} slices, replay deltas {[round(d, 2) for d in replays]}, "
              f"cut deltas {[round(d, 2) for d in deltas]}", flush=True)
    return failures, notes


def main(argv=None, root=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    root = PROJECT_ROOT if root is None else Path(root)
    parser = argparse.ArgumentParser(
        description="Check that consecutive segments over one beat are consecutive slices.")
    parser.add_argument("--episode", required=True,
                        help="episode directory or slug under work/ (required: this tool has no "
                             "current episode of its own)")
    parser.add_argument("--segments", default=None,
                        help="a segment directory other than the episode's live one, e.g. an "
                             "archived pre-fix build used to calibrate the bounds")
    args = parser.parse_args(argv)

    episode = resolve(root, args.episode)
    seg_dir = Path(args.segments).resolve() if args.segments else segments_dir(episode)
    manifest = load_manifest(episode)
    shot_map = shots(episode, CONTRACT)
    # The groups this tool judges are utterances that share a beat, so a shot table describing a
    # different narration timeline than the manifest is not a warning here — it is a different film.
    require_coverage(episode, shot_map, [u["id"] for u in manifest["utterances"]])
    print(f"=== Shot continuity QC ({seg_dir}) ===\n", flush=True)
    failures, notes = check(shot_map, seg_dir)
    for n in notes:
        print(f"  note: {n}", flush=True)
    if failures:
        print(f"\nFAIL ({len(failures)})", flush=True)
        for f in failures:
            print(f"  - {f}", flush=True)
        return 1
    print("\nPASS: every multi-utterance beat is sliced continuously.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
