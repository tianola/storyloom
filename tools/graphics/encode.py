"""Stream frames into ffmpeg one at a time; never hold more than the frame in flight.

600 frames of 1920x1080 RGBA is 8.3 MB each, about 5 GB if a list of them is ever built. Every
function here takes an iterable and pulls it lazily, so a 20-second graphic costs one frame of
memory, not a minute of it.

The output is written to a temp file beside `out` and renamed on success, so a crash, a bad frame or
a killed ffmpeg leaves either the previous `out` or nothing, never half a video.
"""
from __future__ import annotations

import copy
import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image


def _codec_args(alpha, preset):
    if alpha:
        return ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"]
    return ["-c:v", "libx264", "-preset", preset, "-crf", "18", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart"]


def stream_to_mp4(frames, out, fps=30, canvas=(1920, 1080), alpha=False, *, preset="medium", _null=False):
    """Encode an iterable of RGBA PIL images; return the number of frames written.

    alpha=False writes H.264 yuv420p (crf 18) as .mp4; alpha=True writes ProRes 4444 with alpha as
    .mov. `_null=True` is a test hook: it pulls and pipes every frame but encodes to ffmpeg's null
    muxer and writes no file.
    """
    out = Path(out)
    w, h = int(canvas[0]), int(canvas[1])
    if alpha and out.suffix.lower() != ".mov":
        raise ValueError("alpha output is ProRes 4444 and must be a .mov path")
    if not alpha and out.suffix.lower() not in (".mp4", ".mov", ".mkv"):
        raise ValueError("opaque output should be an .mp4 path")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f".{out.stem}.partial-{os.getpid()}{out.suffix}")
    errlog = tempfile.TemporaryFile()
    target = ["-f", "null", "-"] if _null else [str(tmp)]
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}",
           "-r", str(fps), "-i", "-", "-an", *_codec_args(alpha, preset), *target]
    proc = None
    count = 0
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=errlog)
        for frame in frames:
            if not isinstance(frame, Image.Image):
                raise TypeError(f"frame {count} is {type(frame).__name__}, not a PIL image")
            if frame.size != (w, h):
                raise ValueError(f"frame {count} is {frame.size}, canvas is {(w, h)}")
            if frame.mode != "RGBA":
                frame = frame.convert("RGBA")
            proc.stdin.write(frame.tobytes())
            count += 1
            del frame
        proc.stdin.close()
        code = proc.wait()
        if code != 0:
            errlog.seek(0)
            raise RuntimeError(f"ffmpeg exited {code}: {errlog.read().decode(errors='replace')[-600:]}")
        if not _null:
            os.replace(tmp, out)
        return count
    except BaseException as exc:
        if proc is not None and proc.poll() is None:
            proc.kill()
        if proc is not None:
            try:
                proc.wait(timeout=10)
            except Exception:
                pass
            if proc.stdin and not proc.stdin.closed:
                try:
                    proc.stdin.close()
                except Exception:
                    pass
        if isinstance(exc, (BrokenPipeError, OSError)) and not isinstance(exc, (KeyboardInterrupt,)):
            errlog.seek(0)
            detail = errlog.read().decode(errors="replace")[-600:]
            if detail:
                try:
                    tmp.unlink()
                except FileNotFoundError:
                    pass
                raise RuntimeError(f"ffmpeg stopped reading frames: {detail}") from exc
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        raise
    finally:
        errlog.close()


def render_to_file(name_or_preset, spec, seconds, out, fps=30, canvas=(1920, 1080), alpha=None, **kw):
    """Render a primitive (or a named preset, whose spec `spec` may extend) straight to a file.

    alpha defaults to True for overlay primitives (.mov, ProRes 4444) and False for full-frame ones.
    """
    from . import PRIMITIVES, OVERLAY
    from .presets import PRESETS

    if name_or_preset in PRESETS:
        prim, base = PRESETS[name_or_preset]
        merged = copy.deepcopy(base)
        merged.update(spec or {})
        name, spec = prim, merged
    else:
        name = name_or_preset
    if name not in PRIMITIVES:
        raise KeyError(f"no graphics primitive or preset {name_or_preset!r}")
    if alpha is None:
        alpha = name in OVERLAY
    frames = PRIMITIVES[name].render(spec, seconds, canvas=canvas, fps=fps)
    return stream_to_mp4(frames, out, fps=fps, canvas=canvas, alpha=alpha, **kw)
