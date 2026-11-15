"""Compare EEVEE frame times between two render logs — the RX 580 rollout against the
Arc A380 rerun — so the card swap is judged on numbers rather than on how it feels.

Blender prints, per frame:

    Saved: 'F:\\...\\renders\\3d\\sls-launch\\frame-0001.png'
    Time: 00:00.42 (Saving: 00:00.06)

The `Saved:` path is the only unambiguous beat key: the `=== Beat N: Title ===` headers
carry display titles ("Free Return Corridor") that do not match the output directory, and
the mid-shot still renders straight into renders/3d without a directory of its own. Frame
time here is Time minus Saving, because writing PNGs is the same disk on both cards.

Usage:
    python tools/gpu_bench.py summary OLD.log [MORE.log ...]
    python tools/gpu_bench.py compare OLD.log NEW.log [--beat NAME] [--frames N]
"""
from __future__ import annotations

import argparse
import re
import statistics
from pathlib import Path

SAVED = re.compile(r"^Saved:\s+'(.+?)'")
TIME = re.compile(r"^Time:\s+(\d+):(\d\d\.\d+)\s+\(Saving:\s+(\d+):(\d\d\.\d+)\)")
BEAT_DIR = re.compile(r"[\\/]([\w-]+)[\\/]frame-\d+\.png$")


def mmss(minutes: str, seconds: str) -> float:
    return int(minutes) * 60 + float(seconds)


def parse(path: Path) -> dict[str, list[float]]:
    """Return {beat: [per-frame GPU seconds]}, stills excluded."""
    beats: dict[str, list[float]] = {}
    pending: str | None = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = SAVED.match(line)
        if m:
            d = BEAT_DIR.search(m.group(1))
            pending = d.group(1) if d else None
            continue
        m = TIME.match(line)
        if m and pending:
            total = mmss(m.group(1), m.group(2))
            saving = mmss(m.group(3), m.group(4))
            beats.setdefault(pending, []).append(max(total - saving, 0.001))
            pending = None
    return beats


def summarize(times: list[float], frames: int | None) -> dict:
    if not times:
        return {}
    # Frame 1 pays the shader compile, which is a warm-up artifact, not the GPU.
    body = (times if frames is None else times[:frames])
    if len(body) > 1:
        body = body[1:]
    return {"n": len(times), "used": len(body), "mean": statistics.fmean(body),
            "median": statistics.median(body), "total": sum(body), "first": times[0]}


def report(logs: list[Path], frames: int | None) -> None:
    for log in logs:
        print(f"\n{log.name}")
        beats = parse(log)
        all_body = []
        for key in sorted(beats):
            s = summarize(beats[key], frames)
            all_body += beats[key][1:][:s["used"]]
            print(f"  {key:22} {s['n']:>5} frames  mean {s['mean']:.3f}s "
                  f"({1/s['mean']:.2f} f/s)  first {s['first']:.2f}s  "
                  f"total {s['total']/60:.1f} min")
        if all_body:
            t = sum(all_body)
            print(f"  {'ALL BEATS':22} {len(all_body):>5} frames  mean {t/len(all_body):.3f}s "
                  f"({len(all_body)/t:.2f} f/s)  total {t/3600:.2f} h")


def compare(old: Path, new: Path, beat: str, frames: int | None) -> int:
    a_all, b_all = parse(old), parse(new)
    keys = [beat] if beat else sorted(set(a_all) & set(b_all))
    if not keys:
        print(f"no beat in common.\n  old: {sorted(a_all)}\n  new: {sorted(b_all)}")
        return 2
    print(f"{'beat':22} {'frames':>6} {'RX 580 f/s':>11} {'new f/s':>9} "
          f"{'speedup':>9} {'old mean':>9} {'new mean':>9}")
    ta = tb = na = nb = 0.0
    for key in keys:
        a = summarize(a_all.get(key, []), frames)
        b = summarize(b_all.get(key, []), frames)
        if not a or not b:
            print(f"{key:22} missing in {'old' if not a else 'new'}")
            continue
        ra, rb = 1 / a["mean"], 1 / b["mean"]
        print(f"{key:22} {min(a['used'], b['used']):>6} {ra:>11.2f} {rb:>9.2f} "
              f"{rb/ra:>8.2f}x {a['mean']:>8.3f}s {b['mean']:>8.3f}s")
        ta, tb = ta + a["total"], tb + b["total"]
        na, nb = na + a["used"], nb + b["used"]
    if ta and tb and na == nb:
        print(f"\n{na:.0f} comparable frames (frame 1 excluded, save time removed)")
        print(f"  RX 580 : {ta/60:6.1f} min   {na/ta:5.2f} f/s")
        print(f"  new GPU: {tb/60:6.1f} min   {nb/tb:5.2f} f/s")
        print(f"  speedup: {ta/tb:.2f}x   wall-clock saved: {(ta-tb)/60:.1f} min "
              f"for these frames")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["compare", "summary"])
    ap.add_argument("logs", nargs="+", type=Path)
    ap.add_argument("--beat", default=None)
    ap.add_argument("--frames", type=int, default=None,
                    help="use only the first N frames of each beat (paired runs)")
    args = ap.parse_args()
    if args.mode == "summary":
        report(args.logs, args.frames)
        return 0
    if len(args.logs) != 2:
        print("compare needs exactly two logs")
        return 2
    return compare(args.logs[0], args.logs[1], args.beat, args.frames)


if __name__ == "__main__":
    raise SystemExit(main())
