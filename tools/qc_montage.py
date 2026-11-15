"""One labelled frame per utterance, tiled — the episode-level look QC.

The look pass is judged on this sheet: a viewer reading it sees every sentence's picture in the
order the film plays them. Frames come from the midpoint of each utterance, so a cell shows what is
on screen *while* the sentence is spoken rather than a hand-picked instant that flatters a shot
which only looks right for its first frame.

This used to live in `work/episode-artemis-ii/qc/` and import that episode's directory, sample
rate and visual map from the assembler — so it could describe one film and no other. The two facts
it labels with are now read off the episode: which shot is on screen (`shots.json`) and how long
the narration over it runs (`vo/manifest.json` and the `sampleRate` the narration declares).

Usage:
    python tools/qc_montage.py --episode work/episode-artemis-ii
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PROJECT_ROOT))

from assemble_episode import load_manifest, narration_rate  # noqa: E402
from workflow.config import style_contract  # noqa: E402
from workflow.episode import (master, qc_dir, require_coverage,  # noqa: E402
                              resolve, shots)

CONTRACT = style_contract(PROJECT_ROOT)

# The cell is the canvas at 1/6 scale: 320x180 keeps the 16:9 aspect so a squashed frame can never
# be read as a framing defect, and stays large enough to judge grain and grading from the sheet.
CELL_W, CELL_H, PAD = 320, 180, 18
COLS = 4
BG = (16, 16, 18)
LABEL = (230, 230, 230)


def cells(manifest, shot_map, rate):
    """`(label, midpoint)` for every utterance, in the order the film plays them.

    The label is `kind:name` rather than the clip's title because the look question is which layer
    produced the frame: an archival still graded like a render and a render graded flat are the same
    defect described by the same two words, and a title would only tell the reader what the card
    already says on screen.
    """
    out = []
    t = 0.0
    for utterance in manifest["utterances"]:
        uid = utterance["id"]
        duration = utterance["samples"] / rate
        kind, name = shot_map[uid][:2]
        out.append((f"{uid} {kind}:{name} {t:.0f}-{t + duration:.0f}s", t + duration / 2))
        t += duration
    return out


def grab(film, when, png):
    """Decode the single frame at `when` seconds into `png`."""
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{when:.3f}", "-i", str(film),
                    "-frames:v", "1", str(png)], capture_output=True, check=True)


def sheet(cell_list, film, out):
    """Grab every midpoint, tile the frames over their labels, and write the one evidence PNG.

    Each frame is converted and resized inside the temp directory's lifetime: `convert` forces the
    pixel load, so the handle closes before ffmpeg overwrites the same path for the next cell —
    which on Windows is a `PermissionError` rather than a mix of two frames.
    """
    frames = []
    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / "f.png"
        for label, when in cell_list:
            grab(film, when, png)
            with Image.open(png) as frame:
                frames.append((label, frame.convert("RGB").resize((CELL_W, CELL_H))))

    rows = (len(frames) + COLS - 1) // COLS
    page = Image.new("RGB", (COLS * CELL_W, rows * (CELL_H + PAD)), BG)
    draw = ImageDraw.Draw(page)
    for i, (label, frame) in enumerate(frames):
        x, y = (i % COLS) * CELL_W, (i // COLS) * (CELL_H + PAD)
        page.paste(frame, (x, y))
        draw.text((x + 4, y + CELL_H + 3), label, fill=LABEL)
    out.parent.mkdir(parents=True, exist_ok=True)
    page.save(out)
    return page


def main(argv=None, root=PROJECT_ROOT):
    parser = argparse.ArgumentParser(
        description="Tile one labelled frame per utterance — the episode look QC.")
    parser.add_argument("--episode", required=True,
                        help="episode directory or slug under work/ (required: this tool has no "
                             "current episode of its own)")
    args = parser.parse_args(argv)

    episode = resolve(root, args.episode)
    manifest = load_manifest(episode)
    shot_map = shots(episode, CONTRACT)
    # A montage over a hole in the timeline is a frame standing in for a sentence that has no shot,
    # and it looks like a picture. Refuse, the way the assembler does.
    require_coverage(episode, shot_map, [u["id"] for u in manifest["utterances"]])

    film, out = master(episode), qc_dir(episode) / "montage.png"
    page = sheet(cells(manifest, shot_map, narration_rate(manifest)), film, out)
    print(f"{len(manifest['utterances'])} cells -> {out} {page.size[0]}x{page.size[1]}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
