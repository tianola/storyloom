"""One ffmpeg pass that makes the assembled master read as footage instead of as a render.

Nothing upstream is dirty, and that is the problem: EEVEE gives flat black space, razor edges and
no lens. Real camera material halates at the highlights, carries grain, and loses light toward the
corners. This adds exactly those three things plus a contrast grade.

It runs on the *assembled* video, once, between the concat and the mux - not on the per-utterance
segments. The segments are a cache, so grading there would re-encode ~400 files, double-compress
every slice, and lengthen a rollout that is already hours long.

Every strength and every encode setting is read from `archive.cohesion.finish` in
`workflow/style.json`, and the run writes the report that block names. This pass is the single
transform that reaches the 3D beats, the Manim layer, the cards and the archival inserts alike, so
it is the mechanism the contract says carries cohesion between the two styles - which is why its
numbers are house data rather than this file's opinion, and why "the grade ran" is a claim the gate
checks against a recorded digest instead of a habit nobody can see.

Usage:
    python tools/look_pass.py IN.mp4 OUT.mp4 [--bloom 0.18 --grain 5 ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflow.config import style_contract  # noqa: E402

# The names a look-dev run may move. The values are the contract's; this tuple only says which of
# them the CLI exposes, so a strength added to the contract becomes overridable by name.
STRENGTHS = ("bloom", "bloom_sigma", "black_point", "contrast", "saturation",
             "sharpen", "grain", "vignette")
NEUTRAL = 1.0   # an eq multiplier that changes nothing
CHUNK_BYTES = 1024 * 1024


def finish(contract=None) -> dict:
    """The declared finishing block: strengths, encode settings, and the report's own path."""
    block = (contract or style_contract(ROOT))["archive"]["cohesion"]["finish"]
    missing = [name for name in STRENGTHS if name not in block.get("strengths", {})]
    if missing:
        raise ValueError(f"archive.cohesion.finish.strengths does not declare {missing}, so the "
                         "grade would be whatever this module happened to remember")
    return block


def strengths(contract=None, **overrides) -> dict:
    """The eight numbers this run grades with: the contract's, minus any a caller moved."""
    declared = {name: float(finish(contract)["strengths"][name]) for name in STRENGTHS}
    unknown = sorted(set(overrides) - set(STRENGTHS))
    if unknown:
        raise ValueError(f"{unknown} are not finishing strengths; the contract declares "
                         f"{list(STRENGTHS)}")
    declared.update({name: float(value) for name, value in overrides.items()})
    return declared


def graph_of(values: dict) -> str:
    """The filtergraph. Ordering is load-bearing: grade, bloom, sharpen, grain, vignette.

    Sharpen before grain, never after, or the unsharp mask lifts the noise it just made and the
    shot sparkles. Vignette last, because everything after it re-lights the corners it fell off.
    An element given 0 leaves the graph instead of sitting in it at zero strength.
    """
    bloom = values["bloom"]
    if bloom > 0:
        # format=gbrp is not decoration. blend composites plane by plane, and on the default
        # yuv420p that means the U and V planes - which sit centred at 128, not at zero - get
        # screened as if they were light. The result was a magenta wash over every grey surface
        # in the frame.
        head = (f"[0:v]format=gbrp,split=2[base][hl];"
                f"[hl]curves=master='0/0 {values['black_point']}/0 1/1',"
                f"gblur=sigma={values['bloom_sigma']}[bloom];"
                f"[base][bloom]blend=all_mode=screen:all_opacity={bloom}")
    else:
        head = "[0:v]"

    tail = []
    if values["contrast"] != NEUTRAL or values["saturation"] != NEUTRAL:
        tail.append(f"eq=contrast={values['contrast']}:saturation={values['saturation']}")
    if values["sharpen"]:
        tail.append(f"unsharp=5:5:{values['sharpen']}")
    if values["grain"]:
        # allf=t keeps the grain moving; without it the noise freezes into a screendoor.
        tail.append(f"noise=alls={values['grain']}:allf=t")
    if values["vignette"]:
        tail.append(f"vignette={values['vignette']}")
    return ",".join([head] + tail)


def build_vf(*, contract=None, **overrides) -> str:
    """The filtergraph for this contract, with any look-dev overrides applied."""
    return graph_of(strengths(contract, **overrides))


def digest_of(path) -> str:
    """sha256 of a file, streamed: a graded master is hundreds of megabytes."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_report(dst, *, used, moved, filtergraph, encode, contract=None) -> Path:
    """What this run did, where the contract says the evidence for it lives."""
    path = Path(dst).parent / finish(contract)["report_filename"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "tool": Path(__file__).resolve().relative_to(ROOT).as_posix(),
        "graded": str(Path(dst)),
        "graded_sha256": digest_of(dst),
        "strengths": used,
        "overrides": moved,
        "encode": encode,
        "filtergraph": filtergraph,
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, indent=2), encoding="utf-8")
    return path


def apply(src: Path, dst: Path, *, contract=None, **overrides) -> Path:
    """Grade src into dst in a single encode, and leave the evidence that it was this grade.

    The picture is never resized. A strength moved away from the contract still grades - look-dev
    needs that - but it is recorded as an override, so the gate can tell a house grade from a
    one-off somebody tried on a Tuesday.
    """
    block = finish(contract)
    declared = {name: float(block["strengths"][name]) for name in STRENGTHS}
    used = strengths(contract, **overrides)
    moved = {name: {"contract": declared[name], "used": used[name]}
             for name in STRENGTHS if used[name] != declared[name]}
    encode = block["encode"]
    filtergraph = graph_of(used)

    subprocess.run([
        "ffmpeg", "-y", "-i", str(src),
        "-vf", filtergraph,
        "-c:v", str(encode["codec"]), "-preset", str(encode["preset"]),
        "-crf", str(encode["crf"]), "-pix_fmt", str(encode["pixel_format"]),
        "-c:a", "copy",
        str(dst),
    ], capture_output=True, check=True)

    dst = Path(dst)
    if not dst.is_file():
        raise FileNotFoundError(
            f"ffmpeg reported success but wrote no {dst}, so there is no graded master to digest "
            "and no honest evidence to leave behind")
    write_report(dst, used=used, moved=moved, filtergraph=filtergraph, encode=encode,
                 contract=contract)
    return dst


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    for name in STRENGTHS:
        ap.add_argument(f"--{name.replace('_', '-')}", dest=name, type=float)
    args = ap.parse_args()
    overrides = {k: getattr(args, k) for k in STRENGTHS if getattr(args, k) is not None}
    print(f"  Graded: {apply(args.src, args.dst, **overrides)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
