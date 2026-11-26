"""Builds ffmpeg argument lists for segments, transition pieces, concat and split screens.

Every function is pure: it returns an argv list (strings, starting with "ffmpeg") or text.
Frame-exactness is the contract: a segment of N frames has exactly N frames.
"""
import math
from collections import namedtuple

Canvas = namedtuple("Canvas", "width height fps")
Overlay = namedtuple("Overlay", "path start_frame end_frame x y", defaults=(0, 0))
Mat = namedtuple("Mat", "colour border_px", defaults=("0x0b0b0e", 0))

_ENCODE = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", "-crf", "23"]
_XFADE = {"dissolve": "fade", "match": "fade"}
# xfade's built-in fadeblack is lopsided (its black point sits at ~0.3 of the piece, not 0.5), so
# "dip" uses a symmetric custom expression: A fades to black over the first half, B rises from
# black over the second. (In ffmpeg 9 xfade's P runs 1 -> 0 over the piece, verified by pixels.) Black is 16 on luma and 128 on chroma (limited-range yuv420p).
_K = "if(eq(PLANE,0),16,128)"
_DIP = f"custom:expr='if(gt(P,0.5),(A-{_K})*(2*P-1)+{_K},(B-{_K})*(1-2*P)+{_K})'"


def frame_of(t, fps):
    """Frame index of time t. Rounds .5 up, always.

    Python's round() is banker's rounding (round(2.5) == 2, round(3.5) == 4), so two cuts at
    the same fractional position would land on different sides depending on parity. Floor of
    x + 0.5 rounds every half the same way, which keeps a shot's end and the next shot's
    start on the same frame boundary.
    """
    return int(math.floor(t * fps + 0.5))


def _num(x):
    return f"{x:.6f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


def _fit(canvas, mat=None, w=None, h=None):
    """scale+pad chain fitting the source into w x h (default the canvas)."""
    w = canvas.width if w is None else w
    h = canvas.height if h is None else h
    colour = ""
    iw, ih = w, h
    if mat is not None:
        iw, ih = max(2, w - 2 * mat.border_px), max(2, h - 2 * mat.border_px)
        colour = f":color={mat.colour}"
    return (f"scale={iw}:{ih}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2{colour},setsar=1")


def _input(source, src_in, still=False, loop=False, fps=None):
    args = []
    if still:
        args += ["-loop", "1"]
        if fps:
            args += ["-framerate", str(fps)]
    elif loop:
        args += ["-stream_loop", "-1"]
    if src_in:
        args += ["-ss", _num(float(src_in))]
    return args + ["-i", str(source)]


def segment_args(source, src_in, frames, canvas, out, *, still=False, loop=False,
                 overlays=(), mat=None):
    fps = canvas.fps
    args = ["ffmpeg", "-y", *_input(source, 0 if still else src_in, still, loop, fps)]
    base = f"fps={fps},{_fit(canvas, mat)}"
    if not overlays:
        args += ["-frames:v", str(frames), "-vf", base]
    else:
        parts = [f"[0:v]{base}[v0]"]
        for i, ov in enumerate(overlays, start=1):
            args += ["-loop", "1", "-framerate", str(fps)] if str(ov.path).lower().endswith(
                (".png", ".jpg", ".jpeg")) else []
            args += ["-i", str(ov.path)]
            parts.append(f"[{i}:v]format=rgba,setpts=PTS+{ov.start_frame}/({fps}*TB)[o{i}]")
            parts.append(f"[v{i-1}][o{i}]overlay={ov.x}:{ov.y}:eof_action=pass:"
                         f"enable='between(t,{(ov.start_frame - 0.5) / fps:.6f},{(ov.end_frame - 0.5) / fps:.6f})'[v{i}]")
        last = len(overlays)
        parts.append(f"[v{last}]format=yuv420p[vout]")
        args += ["-filter_complex", ";".join(parts), "-map", "[vout]", "-frames:v", str(frames)]
    return args + [*_ENCODE, "-r", str(fps), "-an", str(out)]


def transition_args(out_source, out_in, in_source, in_in, frames, kind, canvas, out, *,
                    out_loop=False, in_loop=False):
    if kind == "cut":
        raise ValueError("a cut needs no transition piece")
    if kind not in _XFADE and kind != "dip":
        raise ValueError(f"unknown transition kind {kind!r}")
    fps = canvas.fps
    dip = kind == "dip"
    norm = (f"fps={fps},{_fit(canvas)},trim=end_frame={frames},setpts=PTS-STARTPTS"
           )
    effect = _DIP if dip else f"transition={_XFADE[kind]}"
    graph = (f"[0:v]{norm}[a];[1:v]{norm}[b];"
             f"[a][b]xfade={effect}:duration={frames / fps:.6f}:offset=0,"
             f"trim=end_frame={frames},setpts=PTS-STARTPTS,format=yuv420p[vout]")
    return ["ffmpeg", "-y",
            *_input(out_source, out_in, loop=out_loop),
            *_input(in_source, in_in, loop=in_loop),
            "-filter_complex", graph, "-map", "[vout]", "-frames:v", str(frames),
            *_ENCODE, "-r", str(fps), "-an", str(out)]


def concat_list(paths):
    """Text of a concat demuxer list. Forward slashes (valid on Windows, no escape trouble);
    single quotes escaped as '\''. Write it as UTF-8 and use `-safe 0`."""
    lines = []
    for p in paths:
        s = str(p).replace("\\", "/").replace("'", "'\\''")
        lines.append(f"file '{s}'")
    return "\n".join(lines) + "\n"


def concat_args(list_file, out):
    return ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c", "copy", str(out)]


def _default_rects(n, canvas, gap):
    W, H = canvas.width, canvas.height
    if n == 2:
        w = (W - gap) // 2
        return [(0, 0, w, H), (w + gap, 0, w, H)]
    if n == 3:
        w = (W - 2 * gap) // 3
        return [(i * (w + gap), 0, w, H) for i in range(3)]
    if n == 4:
        w, h = (W - gap) // 2, (H - gap) // 2
        return [(c * (w + gap), r * (h + gap), w, h) for r in range(2) for c in range(2)]
    raise ValueError("split screens take 2 to 4 sources")


def split_args(sources_with_in, frames, canvas, out, *, gap=8, rects=None):
    """sources_with_in: [(source, src_in) or (source, src_in, loop)]. Panes are placed with
    xstack on a black canvas (the gap shows black)."""
    n = len(sources_with_in)
    rects = list(rects) if rects else _default_rects(n, canvas, gap)
    if len(rects) != n:
        raise ValueError("one rect per source")
    fps = canvas.fps
    args = ["ffmpeg", "-y"]
    parts = []
    for i, item in enumerate(sources_with_in):
        src, src_in = item[0], item[1]
        loop = item[2] if len(item) > 2 else False
        args += _input(src, src_in, loop=loop)
        x, y, w, h = rects[i]
        parts.append(f"[{i}:v]fps={fps},{_fit(canvas, None, w, h)}[p{i}]")
    layout = "|".join(f"{x}_{y}" for x, y, _, _ in rects)
    ins = "".join(f"[p{i}]" for i in range(n))
    parts.append(f"{ins}xstack=inputs={n}:layout={layout}:fill=black,"
                 f"pad={canvas.width}:{canvas.height}:0:0:black,format=yuv420p[vout]")
    args += ["-filter_complex", ";".join(parts), "-map", "[vout]", "-frames:v", str(frames),
             *_ENCODE, "-r", str(fps), "-an", str(out)]
    return args
