"""Turn an old episode's shots.json into an authored cut.json, proved frame for frame.

Two edit paths live side by side: the old one (`shots.json`, one visual per narration line, cut by
`assemble_episode.build_segments`) and the cut list (`cut.json`, `tools/edit/`). Every reader keeps
a branch for each. This is the first step to one path: convert an episode, prove that the cut list
cuts it to the very frames the old cutter did, and only then let it switch.

    python tools/edit/to_cut.py --episode work/X             # writes work/X/cut.from-shots.json
    python tools/edit/to_cut.py --episode work/X --install   # writes work/X/cut.json (switches the episode)

The authored cut has one shot per line (`line:uNNN` anchors), each cut, with the source in-point
written out so a clip reused later in the film resumes where the old cutter's cursor was. Before
anything is written, the cut is resolved against the episode's own voice and its render plan is
compared with `edit.legacy` (which test_legacy proves equal to `build_segments`): any frame that
differs stops the conversion. Cards are refused: the cut-mode assembler has no card layer yet.
An existing cut.json is never overwritten.

The cut list also enforces house rules the old cutter never checked (an archival shot held past
its bound, a beat reused). Those findings are listed; `--install` refuses while any remain, because
the cut-mode assembler would refuse the episode anyway. Fix them in cut.from-shots.json, then install.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

from edit import cutlist, legacy  # noqa: E402

SUPPORTED = {"3d", "archive", "graphic", "black"}


def authored_from_shots(shot_map, manifest, *, fps):
    """The authored cut.json body for `{uid: (kind, name)}` on this narration."""
    resolved = legacy.from_shots(shot_map, manifest, fps=fps)
    unsupported = sorted({s["source"]["kind"] for s in resolved["shots"]} - SUPPORTED)
    if unsupported:
        raise ValueError(f"shots of kind {unsupported} have no layer in the cut-mode assembler yet; "
                         "this episode stays on shots.json")
    shots = []
    for s in resolved["shots"]:
        src = s["source"]
        shots.append({"id": s["id"], "start_anchor": f"line:{s['id']}",
                      "source": {"kind": src["kind"], "name": src["name"], "in": round(src["in"], 6)},
                      "transition_in": {"type": "cut", "dur": 0.0}, "overlays": [], "speed": 1.0,
                      "provenance": "legacy"})
    return {"schema": cutlist.SCHEMA, "fps": fps, "lead_frames": cutlist.DEFAULT_LEAD_FRAMES, "tail": 0.0,
            "note": "converted from shots.json by tools/edit/to_cut.py; frame-identical to the old cut",
            "shots": shots}


def plan_frames(plan):
    return [(p["shot"], tuple(p["frames"]), p["source"]["name"], round(p["seek"], 4)) for p in plan]


def differences(authored, shot_map, manifest, vo_dir):
    """[(what, old, new)] where the converted cut would not cut the film the old cutter did."""
    fps = int(authored["fps"])
    new = plan_frames(cutlist.render_plan(cutlist.resolve(authored, cutlist.line_clock(manifest, vo_dir))))
    old = plan_frames(cutlist.render_plan(legacy.from_shots(shot_map, manifest, fps=fps)))
    if len(new) != len(old):
        return [("pieces", len(old), len(new))]
    tolerance = 0.5 / fps + 1e-6
    out = []
    for a, b in zip(old, new):
        if a[:3] != b[:3] or abs(a[3] - b[3]) > tolerance:
            out.append((a[0], a, b))
    return out


def findings(authored, manifest, vo_dir, contract):
    return cutlist.validate(cutlist.resolve(authored, cutlist.line_clock(manifest, vo_dir)), contract)


def convert(episode, *, fps, install=False, contract=None):
    episode = Path(episode)
    if (episode / "cut.json").is_file():
        raise ValueError(f"{episode / 'cut.json'} exists: this episode is already cut from a cut list")
    table = json.loads((episode / "shots.json").read_text(encoding="utf-8"))
    shot_map = {uid: (r["kind"], r["name"]) for uid, r in table.items()}
    manifest = json.loads((episode / "vo" / "manifest.json").read_text(encoding="utf-8"))
    authored = authored_from_shots(shot_map, manifest, fps=fps)
    diff = differences(authored, shot_map, manifest, episode / "vo")
    if diff:
        raise ValueError("the converted cut differs from the old one; nothing written:\n  "
                         + "\n  ".join(f"{w}: old {a} new {b}" for w, a, b in diff[:20]))
    found = findings(authored, manifest, episode / "vo", contract) if contract else []
    if install and found:
        raise ValueError("frame-identical, but the old cut breaks rules the cut list enforces; not installed:\n  "
                         + "\n  ".join(f"[{f['code']}] {f['shot']}: {f['message']}" for f in found))
    out = episode / ("cut.json" if install else "cut.from-shots.json")
    out.write_text(json.dumps(authored, indent=1) + "\n", encoding="utf-8")
    return out, found


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--episode", type=Path, required=True)
    ap.add_argument("--install", action="store_true", help="write cut.json, which switches the episode to the cut list")
    args = ap.parse_args(argv)
    episode = args.episode if args.episode.is_absolute() else ROOT / args.episode
    from workflow.config import style_contract
    contract = style_contract(ROOT)
    try:
        out, found = convert(episode, fps=int(contract["canvas"]["fps"]), install=args.install, contract=contract)
    except (ValueError, OSError) as exc:
        print(f"to_cut: {exc}", file=sys.stderr)
        return 1
    print(f"frame-identical to the old cut; wrote {out}")
    for f in found:
        print(f"  to fix before --install: [{f['code']}] {f['shot']}: {f['message']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
