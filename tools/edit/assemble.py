"""Cut an episode from its cut list: frame-exact shots, centred transitions, overlays on top.

`assemble_episode.py` calls this when an episode has a `cut.json`; an episode without one is cut
by `build_segments` exactly as before. The steps:

1. **resolve** the authored cut against the voice on disk (`cutlist.resolve`), refuse it if
   `cutlist.validate` finds anything, and publish `cut.resolved.json` — the cut the film was made
   to, which the gate, the sound design and the voice finish then read;
2. **lengths**: publish `shot_lengths.json` from `cutlist.source_seconds_needed` (handles
   included) and write each 3D beat's shot timings into `storyboard.json`, so the renderer's camera
   changes land on the cut's frames;
3. **sources**: draw the generated layers at exactly the length the cut reads them — full-frame
   graphics, black, an archival still on its mat — and every overlay as an alpha clip;
4. **pieces**: one ffmpeg call per `render_plan` piece (segment or transition), each cached against
   a stamp of its own inputs, then a stream-copy concat.

Every function that runs ffmpeg takes the argv from `tools/compose`, so the graphs themselves are
tested there on fixtures, and this file only decides which graph each piece needs.
"""
import json
import math
import subprocess
from pathlib import Path

from edit import cutlist
from workflow.episode import (archive_sources, render_dir, resolved_cut_path, segments_dir,
                              shot_lengths_path, vo_dir)

GENERATED = ("graphic", "black")
STORYBOARD = "storyboard.json"


# --- resolve and publish -----------------------------------------------------------------------

def resolve_episode(episode, manifest, contract):
    """The authored cut placed on this voice, validated; raises with every finding if it is not clean."""
    authored = cutlist.load(Path(episode) / "cut.json")
    if int(authored["fps"]) != int(contract["canvas"]["fps"]):
        raise ValueError(f"cut.json is cut at {authored['fps']} fps, the contract delivers "
                         f"{contract['canvas']['fps']}")
    lines = cutlist.line_clock(manifest, vo_dir(episode))
    resolved = cutlist.resolve(authored, lines)
    findings = cutlist.validate(resolved, contract)
    if findings:
        raise ValueError("cut.json does not resolve cleanly against this voice:\n  "
                         + "\n  ".join(f"[{f['code']}] {f['shot'] or 'film'}: {f['message']}"
                                       for f in findings))
    return resolved


def publish(episode, resolved):
    path = resolved_cut_path(episode)
    path.write_text(json.dumps(resolved, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def write_lengths(episode, resolved):
    """shot_lengths.json (whole seconds, rounded up, handles in) and the beats' shot timings."""
    need = cutlist.source_seconds_needed(resolved)
    kinds = {s["source"]["name"]: s["source"]["kind"] for s in resolved["shots"]}
    lengths = {name: int(math.ceil(sec - 1e-6)) for name, sec in need.items()
               if kinds[name] not in GENERATED}
    shot_lengths_path(episode).write_text(json.dumps(lengths, indent=1), encoding="utf-8")
    sync_storyboard(episode, resolved)
    return lengths


def sync_storyboard(episode, resolved):
    """Write the cut's shot timings into each 3D beat of storyboard.json, keeping everything else.

    The renderer reads its camera changes off the beat's `shots`; the cut owns when they happen.
    A beat the cut names but the storyboard lacks is an error: the renderer has nothing to build.
    """
    path = Path(episode) / STORYBOARD
    board = json.loads(path.read_text(encoding="utf-8"))
    beats = cutlist.beat_shots(resolved)
    missing = sorted(set(beats) - set(board.get("beats", {})))
    if missing:
        raise ValueError(f"{path.name} has no beat for {missing}, which the cut puts on screen")
    for name, shots in beats.items():
        spec = board["beats"][name]
        old = spec.get("shots") or []
        merged = []
        for i, s in enumerate(shots):
            keep = {k: v for k, v in (old[i] if i < len(old) else {}).items()
                    if k not in ("view", "start", "to", "move")}
            # seconds written as "<n>s": a bare number <= 1 would be read as a fraction of the beat
            merged.append({**keep, **s, "start": 0.0 if i == 0 else f"{s['start']:.6f}s"})
        spec["shots"] = merged
    for name, params in cutlist.beat_params(resolved).items():
        spec = board["beats"][name]
        spec.setdefault("params", {}).update({k: f"{v:.3f}s" for k, v in params.items()})
    path.write_text(json.dumps(board, indent=1, ensure_ascii=False), encoding="utf-8")
    return beats


# --- sources -----------------------------------------------------------------------------------

def probe_seconds(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def _stamp(*parts):
    bits = []
    for p in parts:
        if isinstance(p, Path) and p.exists():
            st = p.stat()
            bits.append(f"{p.resolve()}|{st.st_size}|{st.st_mtime_ns}")
        else:
            bits.append(json.dumps(p, sort_keys=True, default=str))
    return "\n".join(bits)


class Cache:
    """Stamps of what each generated file was made from; a file is reused only on an equal stamp."""

    def __init__(self, path):
        self.path = Path(path)
        try:
            self.stamps = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.stamps = {}

    def fresh(self, out, stamp):
        return Path(out).is_file() and self.stamps.get(str(out)) == stamp

    def mark(self, out, stamp):
        self.stamps[str(out)] = stamp
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.stamps, indent=0), encoding="utf-8")


def _frames_iter(module, spec, t0, n, fps, canvas, tokens):
    for i in range(n):
        yield module.frame_at(spec, t0 + i / fps, canvas=canvas, tokens=tokens)


def draw_graphic(name, spec, seconds, out, *, fps, canvas, alpha, t0=0.0, cache=None):
    """One graphic, preset or primitive, streamed to a clip of `round(seconds*fps)` frames from local time t0."""
    import graphics
    from graphics import encode, presets
    from graphics.tokens import load_tokens
    if name in presets.PRESETS:
        prim, base = presets.PRESETS[name]
        spec = {**base, **(spec or {})}
    else:
        prim = name
    module = graphics.get(prim)
    n = int(round(seconds * fps))
    stamp = _stamp("graphic/1", prim, spec, t0, n, fps, list(canvas), alpha)
    if cache and cache.fresh(out, stamp):
        return Path(out)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    tokens = load_tokens()
    encode.stream_to_mp4(_frames_iter(module, spec, t0, n, fps, canvas, tokens), out, fps=fps,
                         canvas=canvas, alpha=alpha)
    if cache:
        cache.mark(out, stamp)
    return Path(out)


def black_clip(out, seconds, *, fps, canvas, cache=None):
    n = int(round(seconds * fps))
    stamp = _stamp("black/1", n, fps, list(canvas))
    if cache and cache.fresh(out, stamp):
        return Path(out)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    f"color=c=black:s={canvas[0]}x{canvas[1]}:r={fps}", "-frames:v", str(n),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", "-crf", "23",
                    str(out)], check=True)
    if cache:
        cache.mark(out, stamp)
    return Path(out)


def credit_text(entry, contract):
    field = contract["archive"]["source_card"]["text_field"]
    for row in (entry.get("licence") or {}, entry.get("record") or {}):
        if row.get(field):
            return row[field]
    raise ValueError(f"the archive record for {entry['source'].name} has no {field!r} to credit")


def archive_on_mat(entry, seconds, out, *, fps, canvas, contract, cache=None):
    """An archival still on the house mat, its credit on the mat, a slow push sized to `seconds`."""
    spec = {"image": str(entry["source"]), "credit": credit_text(entry, contract)}
    highlight = (entry.get("record") or {}).get("highlight")
    if highlight:
        spec["highlight"] = highlight
    return draw_graphic("archive_mat", spec, seconds, out, fps=fps, canvas=canvas, alpha=False,
                        cache=cache)


def prepare_sources(episode, resolved, contract, *, root=None):
    """`{source name: Path}` for every source the cut reads, drawing the generated ones now.

    3D beats must already be rendered (the render stage, sized by `write_lengths`); archival
    stills marked `frame: archive_mat` are drawn on the mat here, at the length the cut reads them;
    other archival sources come from the ingest; graphics and black are drawn at their needed length.
    """
    fps = int(resolved["fps"])
    canvas = (int(contract["canvas"]["width"]), int(contract["canvas"]["height"]))
    need = cutlist.source_seconds_needed(resolved)
    cache = Cache(segments_dir(episode) / "cut" / "sources.json")
    archives = None
    paths, problems = {}, []
    seen = {}
    for s in resolved["shots"]:
        seen.setdefault(s["source"]["name"], s["source"])
    for name, src in seen.items():
        kind = src["kind"]
        seconds = need.get(name, 0.0) + 1.0 / fps
        if kind == "3d":
            p = render_dir(episode, "3d", contract) / f"{name}.mp4"
            if not p.is_file():
                problems.append(f"3D beat {name} is not rendered ({p})")
            paths[name] = p
        elif kind == "graphic":
            paths[name] = draw_graphic(name, src.get("spec"), seconds,
                                       Path(episode) / "renders" / "graphic" / f"{name}.mp4",
                                       fps=fps, canvas=canvas, alpha=False, cache=cache)
        elif kind == "black":
            paths[name] = black_clip(Path(episode) / "renders" / "black" / f"{name}.mp4", seconds,
                                     fps=fps, canvas=canvas, cache=cache)
        elif kind == "archive":
            if archives is None:
                archives = archive_sources(episode, contract)
            entry = archives[name]
            if src.get("frame") == "archive_mat":
                paths[name] = archive_on_mat(entry, seconds,
                                             render_dir(episode, "archive", contract) / f"{name}.mat.mp4",
                                             fps=fps, canvas=canvas, contract=contract, cache=cache)
            else:
                if not entry["clip"].is_file():
                    problems.append(f"archival clip {name} is not ingested ({entry['clip']})")
                paths[name] = entry["clip"]
        else:
            problems.append(f"{name}: no source layer {kind!r}")
    if problems:
        raise ValueError("the cut reads sources that are not ready: " + "; ".join(problems))
    return paths


def draw_overlays(episode, resolved, plan, contract):
    """`{(shot id, overlay index): Path}` — each overlay drawn for the frames its segment shows."""
    fps = int(resolved["fps"])
    canvas = (int(contract["canvas"]["width"]), int(contract["canvas"]["height"]))
    cache = Cache(segments_dir(episode) / "cut" / "overlays.json")
    out = {}
    for p in plan:
        if p["kind"] != "segment":
            continue
        for i, o in enumerate(p["overlays"]):
            a, b = o["frames"]
            first_film, shown_from = o["local"]
            t0 = (shown_from - first_film) / fps
            path = segments_dir(episode) / "cut" / "overlays" / f"{p['shot']}-{i}.mov"
            out[(p["shot"], i)] = draw_graphic(o["graphic"], o.get("spec"), (b - a) / fps, path,
                                               fps=fps, canvas=canvas, alpha=True, t0=t0, cache=cache)
    return out


# --- pieces ------------------------------------------------------------------------------------

def _still(path):
    return Path(path).suffix.lower() in (".png", ".jpg", ".jpeg")


def build_pieces(episode, resolved, contract, sources, *, log=print):
    """Render every piece of the plan and concat them into video-only.mp4."""
    import compose
    fps = int(resolved["fps"])
    canvas = compose.Canvas(int(contract["canvas"]["width"]), int(contract["canvas"]["height"]), fps)
    plan = cutlist.render_plan(resolved)
    overlays = draw_overlays(episode, resolved, plan, contract)
    piece_dir = segments_dir(episode) / "cut"
    piece_dir.mkdir(parents=True, exist_ok=True)
    cache = Cache(piece_dir / "pieces.json")
    lengths = {}

    def length(name):
        if name not in lengths:
            lengths[name] = None if _still(sources[name]) else probe_seconds(sources[name])
        return lengths[name]

    def loops(name, seek, frames):
        have = length(name)
        return have is not None and seek + frames / fps > have + 0.5 / fps

    made = []
    for k, p in enumerate(plan):
        frames = p["frames"][1] - p["frames"][0]
        out = piece_dir / f"p{k:03d}.mp4"
        if p["kind"] == "segment":
            name = p["source"]["name"]
            ovs = [compose.Overlay(overlays[(p["shot"], i)], o["frames"][0], o["frames"][1])
                   for i, o in enumerate(p["overlays"])]
            args = compose.segment_args(sources[name], max(0.0, p["seek"]), frames, canvas, out,
                                        still=_still(sources[name]),
                                        loop=loops(name, p["seek"], frames), overlays=ovs)
            inputs = [sources[name], *[o.path for o in ovs]]
        else:
            o, i = p["out"], p["in"]
            args = compose.transition_args(sources[o["name"]], max(0.0, o["seek"]),
                                           sources[i["name"]], max(0.0, i["seek"]), frames,
                                           p["type"], canvas, out,
                                           out_loop=loops(o["name"], o["seek"], frames),
                                           in_loop=loops(i["name"], i["seek"], frames))
            inputs = [sources[o["name"]], sources[i["name"]]]
        stamp = _stamp("piece/1", args[:-1], *[Path(x) for x in inputs])
        if not cache.fresh(out, stamp):
            subprocess.run(args, capture_output=True, check=True)
            cache.mark(out, stamp)
        made.append(out)
    log(f"  Built {len(made)} pieces ({sum(p['kind'] == 'transition' for p in plan)} transitions)")

    list_file = piece_dir / "pieces.txt"
    list_file.write_text(compose.concat_list(made), encoding="utf-8")
    video_only = Path(episode) / "video-only.mp4"
    subprocess.run(compose.concat_args(list_file, video_only), capture_output=True, check=True)
    total = sum(p["frames"][1] - p["frames"][0] for p in plan)
    log(f"  Video: {video_only} ({total} frames, {total / fps:.2f}s)")
    return video_only
