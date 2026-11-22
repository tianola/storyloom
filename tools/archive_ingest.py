# -*- coding: utf-8 -*-
"""The archival ingest: one source file in, one canvas-shaped clip out, every number read from the contract.

`workflow/archive.py` validates what a record *says*. This module is what a record *does* to a
file, and the gap between those two is where archival defects ship: a clip can declare
`motion_mode: "period_motion"` in perfect good faith and still be encoded as natural motion,
because nothing downstream reads the declaration again once the ffmpeg command is built. So every
filter here is assembled from `workflow/style.json` plus the record, and the two are checked
against each other rather than trusted.

Three rules are the reason this is a module rather than a one-line `ffmpeg` call:

* the archival frame keeps its own shape — 4:3 inside 16:9 is provenance, not a mistake to fix,
  and the bar colour is the contract's rather than whatever the encoder pads with;
* the frame's own audio never reaches the master (rule 17), so `-an` and no audio codec anywhere;
* a frame may be mirrored to agree with the 3D key only after OCR has actually looked at it and
  found nothing readable — reversing a plaque, a caption or an instrument panel is falsified
  evidence, and a scanner that did not run cannot report that it found nothing.

Usage from the assembler:

    from archive_ingest import ingest_clip
    result = ingest_clip(src, dst, record=rec, licence_row=row, contract=CONTRACT, root=ROOT,
                         card=True)
    result["duration_s"], result["flipped"], result["card"]

The probes (`probe_*`, `pixel`, `frame_diff`, `find_block_x`, `ocr_text`) are part of this module
because they are the only way to answer the rules an encode can silently ignore, and
`python/test_archive_ingest.py` is written against them.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from workflow.archive import key_side                      # noqa: E402
from workflow.capabilities import executable_for, resolve_path  # noqa: E402

OCR_CAPABILITY = "archive-analysis"   # the registry entry whose executable check carries tesseract
OCR_MIN_CONFIDENCE = 55.0             # measured: grain reads below this, a real caption above
WHITE_LEVEL = 200                     # luma floor for "this is the marker, not the set dressing"
MIN_WHITE_RUN = 12                    # uninterrupted white pixels; shorter is a glyph stroke or a highlight
TEXT_HEIGHT_FRACTION = 0.18           # fixture captions only: under ~0.15 tesseract stops reading a 320-wide frame
RATE_TOLERANCE = 0.05                 # how close a declared native rate has to be to count as the canvas rate

# The default for ingest_clip's `ocr` argument: "resolve the scanner yourself". Passing None means
# "there is no scanner on this machine", which is a different claim and must not be the default.
_AUTO = object()

_scratch_dir = None


def _scratch() -> Path:
    """One temp directory for the module's life, reused by every probe.

    Frames are pulled constantly — each pixel assertion, each OCR read — and a `mkdtemp` per call
    would leave hundreds of directories behind by the end of an episode run.
    """
    global _scratch_dir
    if _scratch_dir is None:
        _scratch_dir = Path(tempfile.mkdtemp(prefix="archive-ingest-"))
    return _scratch_dir


PROBE_TIMEOUT = 120.0        # one frame out of one file; anything slower is the machine, not the clip
ENCODE_CEILING_PER_SECOND = 60.0   # the slowest honest ingest measured here ran at 0.3x realtime
ENCODE_CEILING_FLOOR = 180.0


def encode_ceiling(source_seconds):
    """How long an ingest of this much footage is allowed to take before it is called broken.

    The multiplier is deliberately absurd — sixty times the wall clock the clip lasts — because
    the point is not to police slow encodes. It exists so an unbounded filtergraph fails with a
    message instead of running for five hours: a headless step that can only finish, never time
    out, is a step whose failure looks like a machine that is still working.
    """
    return max(ENCODE_CEILING_FLOOR, ENCODE_CEILING_PER_SECOND * float(source_seconds or 0.0))


def _run(cmd, *, stdin=None, timeout=PROBE_TIMEOUT):
    line = " ".join(str(c) for c in cmd)
    try:
        proc = subprocess.run([str(c) for c in cmd], input=stdin, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"{line}\nstill running after {timeout:g}s, so it was stopped rather than waited "
                    "out. For an ingest that means the filtergraph never reaches EOF — a looped "
                    "extra input without shortest=1 is the usual cause.") from None
    if proc.returncode != 0:
        raise RuntimeError(line + "\n" + proc.stderr.decode("utf-8", "replace")[-2000:])
    return proc.stdout


def _num(value):
    """ffmpeg reports rates as fractions and durations as decimals; tesseract reports confidences
    that are legitimately negative. Everything arrives as a string, and a probe that raised on a
    missing value would turn an empty file into a crash instead of an answer."""
    text = str(value).strip()
    if text in ("", "N/A", "n/a", "0/0", "inf", "nan"):
        return 0.0
    if "/" in text:
        head, tail = text.split("/", 1)
        return float(head) / float(tail) if float(tail) else 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _json_streams(path, kind=None):
    select = ["-select_streams", f"{kind}:0"] if kind else []
    blob = _run(["ffprobe", "-v", "error", *select, "-show_streams", "-of", "json", str(path)])
    return json.loads(blob.decode("utf-8", "replace") or "{}").get("streams", [])


def probe_streams(path, kind="a"):
    """Every stream of one media type, so that an absence can be asserted rather than inferred."""
    return [s for s in _json_streams(path) if s.get("codec_type") == kind]


def probe_duration(path):
    blob = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                 "default=nw=1:nk=1", str(path)])
    return _num(blob.decode("utf-8", "replace").strip())


def probe_fps(path):
    streams = _json_streams(path, "v")
    return _num(streams[0].get("avg_frame_rate")) if streams else 0.0


def probe_size(path):
    streams = _json_streams(path, "v")
    return (int(streams[0]["width"]), int(streams[0]["height"])) if streams else None


def probe_ratio(path):
    size = probe_size(path)
    return (size[0] / size[1]) if size else None


def canvas_of(contract):
    return (int(contract["canvas"]["width"]), int(contract["canvas"]["height"]))


def _fps(contract):
    return float(contract["canvas"]["fps"])


# --------------------------------------------------------------------- frame extraction

def _seek(path, t):
    """`-ss t` for a video; nothing for an image file. With `-ss` (even `-ss 0`) this ffmpeg
    decodes no frame at all from a jpg, so every still read through here came back empty."""
    return [] if Path(path).suffix.lower() in IMAGE_SUFFIXES else ["-ss", f"{float(t):.4f}"]


def grab_frame(path, t, *, canvas=None, scale_to=None, dst=None):
    """One frame as a PNG, optionally normalised to a known size.

    Every pixel rule is stated in canvas coordinates, so a probe that reads the file at its own
    size answers a different question than the rule asks. `scale_to` is how a *source* frame gets
    read on the same grid the master will be graded on.
    """
    target = scale_to or canvas
    src, out = Path(path), Path(dst) if dst else _scratch() / f"{Path(path).stem}-{float(t):.3f}.png"
    cmd = ["ffmpeg", "-v", "error"] + _seek(src, t) + ["-i", str(src), "-frames:v", "1"]
    if target:
        cmd += ["-vf", f"scale={int(target[0])}:{int(target[1])}"]
    _run(cmd + ["-y", str(out)])
    if not out.is_file():
        raise RuntimeError(f"{src} has no frame at t={t}")
    return out


def _raw_grey(path, t, size=None):
    # `gray`, not `grey`: ffmpeg 9's rawvideo encoder rejects the historic alias outright
    # ("Unknown pixel format requested: grey"), and the name is what a probe is written with.
    cmd = ["ffmpeg", "-nostdin", "-v", "error"] + _seek(path, t) + ["-i", str(path),
           "-frames:v", "1", "-pix_fmt", "gray"]
    if size:
        cmd += ["-vf", f"scale={int(size[0])}:{int(size[1])}"]
    blob = _run(cmd + ["-f", "rawvideo", "-"])
    if not blob:
        raise RuntimeError(f"{path} has no frame at t={t}")
    return blob


def _raw_rgb(png):
    """A PNG decoded to raw RGB through ffmpeg, so the probes need no imaging library of their own."""
    blob = _run(["ffmpeg", "-v", "error", "-i", str(png), "-pix_fmt", "rgb24", "-f", "rawvideo",
                 "-"])
    width, height = probe_size(png)
    return width, height, blob


def pixel(path, t, x, y, *, canvas=None):
    """(r, g, b) of one pixel, read off the encoded file rather than off the intent.

    A PNG path is already an extracted frame, so it is read directly; anything else is a video
    and gets one frame pulled out of it at `t`.
    """
    frame = path if Path(path).suffix.lower() in (".png", ".jpg", ".jpeg") \
        else grab_frame(path, t, canvas=canvas)
    width, _, data = _raw_rgb(frame)
    i = (int(y) * width + int(x)) * 3
    return tuple(data[i:i + 3])


def frame_diff(path, t0, t1, *, canvas=None):
    """Mean absolute luma difference between two frames: 0.0 is a frozen frame, 1.0 is noise.

    This is the archival form of the motion gate the cards are already failed on — a still that
    does not move has no screen time, it has a pause.
    """
    size = tuple(canvas) if canvas else None
    a, b = _raw_grey(path, t0, size), _raw_grey(path, t1, size)
    span = min(len(a), len(b))
    return sum(abs(x - y) for x, y in zip(a[:span], b[:span])) / (255.0 * span) if span else 0.0


def find_block_x(path, t, *, canvas=None):
    """The x of the fixture's marker square, by longest run of near-white rather than by brightness.

    A centroid is pulled by anything bright, and a caption is a field of bright glyph strokes.
    The mirror rule is the one this probe exists to falsify, so it has to key on the shape only
    the marker has — a wide uninterrupted white band — or the test reads its own fixture instead
    of the encode.
    """
    size = tuple(canvas) if canvas else None
    grey = _raw_grey(path, t, size)
    width = (size or probe_size(path))[0]
    best, best_x = 0, 0
    for start in range(0, len(grey), width):
        row, run = grey[start:start + width], 0
        for col, value in enumerate(row):
            if value >= WHITE_LEVEL:
                run = 1 if col == 0 or row[col - 1] < WHITE_LEVEL else run + 1
                if run > best:
                    best, best_x = run, col - run // 2
            else:
                run = 0
    if best < MIN_WHITE_RUN:
        raise ValueError(f"no near-white run at least {MIN_WHITE_RUN}px wide in {path} at t={t}: "
                         "this fixture has nothing asymmetric for the mirror rule to act on")
    return best_x


# --------------------------------------------------------------------- OCR

def resolve_ocr(root=ROOT):
    """The scanner this machine actually has, through the registry entry the gate also checks.

    `shutil.which("tesseract")` reports a working tool missing here — tesseract is installed and
    is not on PATH — and the ingest must never disagree with its own gate about whether the
    machine can read text, because that disagreement arrives as the one answer the mirror guard
    treats as permission.
    """
    return executable_for(Path(root), OCR_CAPABILITY)


def ocr_words(png, ocr):
    """[(word, confidence)] from one frame.

    A failing binary raises. Returning empty text instead would be read upstream as "no readable
    text found", which is the exact condition that licenses a mirror — a broken scanner must not
    become permission to flip evidence.
    """
    if not ocr:
        raise ValueError(f"no OCR executable to read with (capability {OCR_CAPABILITY})")
    blob = _run([str(ocr), str(png), "stdout", "tsv"])
    rows = []
    for line in blob.decode("utf-8", "replace").splitlines():
        if line.startswith("level\t"):
            continue        # the TSV header, whose "conf" column would otherwise read as a word
        fields = line.split("\t")
        if len(fields) < 12 or not fields[11].strip():
            continue
        rows.append((fields[11].strip(), _num(fields[10])))
    return rows


def ocr_text(png, ocr):
    """The readable text in a frame, or "" when there is nothing readable in it."""
    return " ".join(word for word, _ in ocr_words(png, ocr))


def has_readable_text(png, ocr):
    return any(conf >= OCR_MIN_CONFIDENCE for _, conf in ocr_words(png, ocr))


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}


def _readable_time(path):
    """A frame worth reading: the middle of what is there, or frame zero for a still image.

    ffprobe reports a jpg as one 0.04 s frame, so "the middle" of a still is 0.02 s, and
    `-ss 0.02` on an image decodes nothing: the mirror guard then died on every still whose
    light side disagreed with the key light. An image file is read at zero.
    """
    if Path(path).suffix.lower() in IMAGE_SUFFIXES:
        return 0.0
    duration = probe_duration(path)
    return duration / 2.0 if duration else 0.0


# --------------------------------------------------------------------- the rules, as filters

def _enum(record, field, allowed):
    value = record.get(field)
    if value not in allowed:
        raise ValueError(f"{field}={value!r} is not one of {list(allowed)}; the contract refuses "
                         f"an undeclared or invented {field} rather than picking one silently")
    return value


def retime_filter(record, contract):
    """Standard 8 played at 30 fps is the comic fast-walk tell; the record says which cure was chosen.

    `retime_to_natural` keeps the source's own wall clock: frame *i* really was exposed
    canvas/native frames after frame *i-1*, so `fps` alone repeats each one and the clip runs as
    long as it did. `period_motion` deliberately does the opposite — one source frame per canvas
    frame — and says so.
    """
    rules = contract["archive"]["archive_motion"]
    canvas_fps = _fps(contract)
    native = record.get("native_fps")
    declared = record.get("motion_mode")
    if declared is None:
        if native and abs(_num(native) - canvas_fps) <= RATE_TOLERANCE:
            return []     # already cut at the canvas rate: there is nothing to reinterpret
        raise ValueError(f"motion_mode is undeclared on {record.get('asset', 'the record')!r}; "
                         f"declare one of {list(rules['motion_mode_enum'])} — archival footage "
                         "played at the wrong rate is a choice somebody has to own")
    _enum({"motion_mode": declared}, "motion_mode", rules["motion_mode_enum"])
    if declared == "period_motion":
        return [f"setpts=N/{canvas_fps:g}/TB", f"fps={canvas_fps:g}"]
    return [f"fps={canvas_fps:g}"]


def _aspect_parts(record, contract, canvas):
    """(fit, closing filter, container overlay) — the same declaration `aspect_filter` prints."""
    rules = contract["archive"]["archive_aspect"]
    treatment = _enum(record, "aspect", rules["treatment_enum"])
    w, h = canvas
    if treatment == "designed_container":
        image, rect = record.get("container_image"), record.get("container_rect")
        missing = [name for name, value in (("container_image", image),
                                            ("container_rect", rect)) if not value]
        if missing:
            raise ValueError("designed_container is only a treatment when the record says what the "
                             f"container is; missing {', '.join(missing)} on "
                             f"{record.get('asset', 'the record')!r}. Without them this is the "
                             "accidental edge crop of the 4:3 frame that the contract rejects")
        x, y, rw, rh = (int(v) for v in rect)
        if x < 0 or y < 0 or x + rw > w or y + rh > h:
            raise ValueError(f"container_rect {list(rect)} reaches outside the {w}x{h} canvas, so "
                             "the encode rather than the record would be deciding what is visible")
        return [f"scale={rw}:{rh}"], f"overlay={x}:{y}:shortest=1", f"overlay={x}:{y}:shortest=1"
    pad = (f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color={rules['bar_colour']}")
    return [f"scale={w}:{h}:force_original_aspect_ratio=decrease"], pad, None


def aspect_filter(record, contract, canvas):
    """The aspect treatment as the two filters it is: fit the frame, then frame it or place it."""
    fit, closing, _ = _aspect_parts(record, contract, canvas)
    return list(fit) + [closing]


def _even(value):
    return max(2, int(round(value / 2.0)) * 2)


def fit_box(record, contract, canvas, source_ratio):
    """The picture's own box inside the canvas, which a still needs before it can size a move.

    A clip's fit needs no arithmetic — `force_original_aspect_ratio=decrease` does it — but a
    still's pan is normalised against the room its zoom leaves *in pixels*, so the box has to be
    settled before the filter is written. Deriving it here keeps the decision in one place and
    makes the pad that follows a placement rather than a resize.
    """
    if record["aspect"] == "designed_container":
        x, y, rw, rh = (int(v) for v in record["container_rect"])
        return _even(rw), _even(rh)
    w, h = canvas
    if not source_ratio:
        return w, h
    return (_even(h * source_ratio), h) if source_ratio < w / h else (w, _even(w / source_ratio))


def still_filter(record, contract, canvas, duration_s, *, fit=None, pad=None, hflip=False):
    """A still gets screen time by moving: a pan and a scale change together, terminating.

    The move is declared in degrees because the cap it is measured against
    (`camera.max_deg_per_second`) is in degrees, and degrees only become pixels through a field of
    view — the renderer's, which the contract carries. The crop window is then normalised against
    the room the zoom actually leaves, so the sweep can never reach past the picture's own edge
    and drag a bar across the shot.
    """
    seconds = float(duration_s) if duration_s else record.get("seconds")
    if not seconds:
        raise ValueError("a still needs its screen time in `seconds` (the record's, or the "
                         "duration the shot was cut to) before its move can be sized")
    move = record.get("still_move")
    if not isinstance(move, dict):
        raise ValueError(f"stills_never_dead: {record.get('asset', 'the still')!r} has no "
                         "still_move, so it would sit frozen and fail the same motion gate a card "
                         "is failed on")
    if move.get("cycle"):
        raise ValueError("still_move.cycle is refused: a move that returns to its opening framing "
                         "reads as a loop, and the contract asks for a terminating one")
    fov = float(contract["camera"]["horizontal_fov_deg"])
    limit = float(contract["camera"]["max_deg_per_second"])
    pan = float(move.get("pan_deg") or 0.0)
    rate = abs(pan) / seconds
    if rate > limit:
        raise ValueError(f"still_move pans {abs(pan):g} degrees over {seconds:g}s = "
                         f"{rate:.2f} deg/s, above camera.max_deg_per_second={limit:g}; a still "
                         "travelling faster than the 3D camera reads as a different programme")
    zf, zt = move.get("zoom_from"), move.get("zoom_to")
    if zf is None or zt is None:
        raise ValueError("still_move needs both zoom_from and zoom_to: still_move_requires names a "
                         "pan *and* a scale change, and a pure pan of a still is the "
                         "sliding-photo effect the motion gate already fails a card for")
    zf, zt = float(zf), float(zt)
    if zf < 1.0 or zt < 1.0:
        raise ValueError(f"still_move zoom {zf:g}→{zt:g} goes under 1.0, which would ask the "
                         "encoder to invent picture outside the frame")
    if round(zt - zf, 6) == 0.0:
        raise ValueError("still_move needs a zoom change, not a zoom: zoom_from == zoom_to leaves "
                         "the move a pan only")
    frames = int(round(seconds * _fps(contract)))
    span = max(1, frames - 1)
    slack = 1.0 - 1.0 / max(zf, zt)
    needed = abs(pan) / fov
    if needed > slack:
        raise ValueError(f"still_move.pan_deg={pan:g} sweeps {needed:.3f} of the frame while zoom "
                         f"{zf:g}→{zt:g} leaves {slack:.3f} of room to move in; raise zoom_to or "
                         "shorten the pan")
    norm = needed / slack
    start = 0.5 - (norm / 2.0 if pan >= 0 else -norm / 2.0)
    step = norm if pan >= 0 else -norm
    box = (int(fit[0]), int(fit[1])) if fit else canvas
    zoompan = ("zoompan=z='clip({zf:g}+({zt:g}-{zf:g})*on/{span},{zf:g},{zt:g})'"
               ":x='(iw-iw/zoom)*({start:g}+{step:g}*on/{span})'"
               ":y='(ih-ih/zoom)*0.5'"
               ":d={frames}:s={w}x{h}:fps={fps:g}").format(zf=zf, zt=zt, span=span, start=start,
                                                           step=step, frames=frames, w=box[0],
                                                           h=box[1], fps=_fps(contract))
    chain = (["select=eq(n\\,0)"]
             + ([f"scale={box[0]}:{box[1]}"] if fit else [])
             + (["hflip"] if hflip else [])
             + [zoompan])
    if pad:
        chain.append(pad)
    return chain


def mirror_decision(record, contract, *, text_found, ocr_available):
    """May this frame be flipped to agree with the 3D key, and on what grounds.

    The archive never controls its own light, so matching the key side is the cheapest cohesion
    lever in the blend and the only one the ingest can act on — but the guard is absolute, and it
    fails closed in both directions: readable text refuses the flip, and so does a scanner that
    could not run, because "no text" from a tool that did not look is not an answer.
    """
    side = record.get("light_side")
    key = key_side(contract)
    if not side:
        return False, (f"no light_side declared on {record.get('asset', 'the record')!r}, so there "
                       "is nothing to agree or disagree with; the frame stays as sourced")
    if side == key:
        return False, f"the frame is already lit from the {key}, like the 3D key"
    if text_found:
        return False, ("OCR found readable text in the frame; mirroring it would reverse the "
                       "writing, and an archival document with its own caption backwards is "
                       "falsified evidence rather than cohesive lighting")
    if not ocr_available:
        return False, (f"no OCR scanner is available (capability {OCR_CAPABILITY} in "
                       "workflow/capabilities.json), so 'no readable text' cannot be claimed and "
                       "the flip is refused rather than assumed")
    return True, (f"the sides disagree ({side} against the {key} key) and OCR found no readable "
                  "text, so the frame is mirrored to match the 3D light")


def card_text(row, contract):
    """What the on-screen credit says: the ledger's own credit line, and nothing borrowed."""
    rules = contract["archive"]["source_card"]
    field = rules["text_field"]
    text = str(row.get(field) or "").strip()
    if not text and row.get("rights_basis") in rules["text_required_for_bases"]:
        raise ValueError(f"{field} is blank on a {row.get('rights_basis')} row "
                         f"({row.get('id')}); a quotation's whole claim to be fair use is that it "
                         "is subordinate and attributed, so this refuses rather than drawing a "
                         "card from some other field")
    return text


def card_font_size(contract, canvas):
    return round(float(contract["archive"]["source_card"]["height_fraction"]) * canvas[1])


def card_position(canvas, card_size, position, contract):
    """Where a card of that size sits, from the contract's fractions rather than a pixel inset.

    Size and inset are both fractions of the canvas, so a format change moves the card where it
    belongs instead of leaving it in the previous format's corner.
    """
    margin = float(contract["archive"]["source_card"]["edge_margin_fraction"])
    w, h = canvas
    cw, ch = card_size
    left, right = round(margin * w), w - cw - round(margin * w)
    top, bottom = round(margin * h), h - ch - round(margin * h)
    corners = {"bottom-left": (left, bottom), "bottom-right": (right, bottom),
               "top-left": (left, top), "top-right": (right, top)}
    if position not in corners:
        raise ValueError(f"source_card.position={position!r} is not one of "
                         f"{', '.join(sorted(corners))}")
    return corners[position]


def _rgb(declared):
    text = str(declared).strip().lower()
    text = text[2:] if text.startswith("0x") else text
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))


def card_lines(text, fits):
    """The credit broken into lines that each pass `fits`, keeping its own phrases together.

    A credit line is written to be read whole, so it is only broken where it already pauses —
    after " / " (the source and the host), then after ", " — and only then between words. Found on
    the Semmelweis pilot: every one-line credit ran off the right edge ("… / Wikimedia Comm"), so
    the attribution the card exists to carry was the part that went missing. A single word wider
    than the canvas is left on its own line rather than cut, since a cut word is no credit either.
    """
    from tools.graphics.archive import card_lines as _card_lines  # the one implementation lives with the other archive graphics
    return _card_lines(text, fits)


def write_card_png(path, text, contract, canvas, *, root=ROOT, font=None):
    """The credit as outlined text on a full-canvas transparent plate.

    Outlined rather than boxed: the stroke is what keeps it legible over a frame we do not
    control, and a full-canvas plate means the overlay never has to know where the picture is
    inside it. A credit wider than the canvas between its two margins is set on more lines
    (`card_lines`) rather than drawn off the edge or shrunk below the contract's size.
    """
    from PIL import Image, ImageDraw, ImageFont

    rules = contract["archive"]["source_card"]
    path = Path(path)
    size = card_font_size(contract, canvas)
    face = ImageFont.truetype(str(font or resolve_path(Path(root), rules["font_file"])), size)
    plate = Image.new("RGBA", canvas, (0, 0, 0, 0))
    draw = ImageDraw.Draw(plate)
    stroke = max(1, round(size * float(rules["text_stroke_fraction"])))
    room = canvas[0] - 2 * round(float(rules["edge_margin_fraction"]) * canvas[0])

    def width(line):
        box = draw.textbbox((0, 0), line, font=face, stroke_width=stroke)
        return box[2] - box[0]

    body = "\n".join(card_lines(text, lambda line: width(line) <= room))
    align = "right" if rules["position"].endswith("right") else "left"
    box = draw.multiline_textbbox((0, 0), body, font=face, stroke_width=stroke, align=align)
    x, y = card_position(canvas, (box[2] - box[0], box[3] - box[1]), rules["position"], contract)
    draw.multiline_text((x - box[0], y - box[1]), body, font=face,
                        fill=_rgb(rules["fill_colour"]) + (255,), align=align,
                        stroke_width=stroke, stroke_fill=_rgb(rules["stroke_colour"]) + (255,))
    plate.save(path)
    return path


def write_fixture_frame(path, *, size, block, text, font, colour=None):
    """A stand-in for archival material that the rules can actually be proved against.

    Flat period colour, a few tonal bands, two mid-tone shapes, and the marker. The texture is
    not decoration: `frame_diff` measures luma change, so a fixture that is one flat field stays
    numerically identical while the window moves across it and a frozen frame would pass the
    motion rule. The marker is what makes the mirror rule falsifiable — a symmetric pattern
    cannot tell a flip from no flip — and the caption is deliberately sized above the threshold
    the OCR floor can see, because a guard whose fixture cannot fail it proves nothing.
    """
    from PIL import Image, ImageDraw, ImageFont

    base = tuple(colour) if colour else (92, 84, 66)
    img = Image.new("RGB", size, base)
    draw = ImageDraw.Draw(img)

    def shade(amount):
        return tuple(max(0, min(255, channel + amount)) for channel in base)

    band = max(1, size[1] // 6)
    for index, amount in enumerate((-18, 10, -6, 14)):
        top = index * band * 2
        draw.rectangle([0, top, size[0], top + band], fill=shade(amount))
    for (fx, fy, fw, fh), amount in (((0.18, 0.55, 0.12, 0.30), -26),
                                     ((0.55, 0.20, 0.20, 0.16), 22)):
        draw.rectangle([fx * size[0], fy * size[1], (fx + fw) * size[0], (fy + fh) * size[1]],
                       fill=shade(amount))
    if block:
        side = max(2, size[0] // 10)
        draw.rectangle([block[0], block[1], block[0] + side, block[1] + side],
                       fill=(246, 246, 244))
    if text:
        face = ImageFont.truetype(str(font), max(6, round(TEXT_HEIGHT_FRACTION * size[1])))
        box = draw.textbbox((0, 0), text, font=face)
        draw.text(((size[0] - box[2] + box[0]) / 2 - box[0], size[1] / 8 - box[1]), text,
                  font=face, fill=(238, 236, 230))
    img.save(path)
    return path


def card_enable(contract):
    """The overlay that shows the plate for its declared window and then stops showing it.

    `enable` is what makes the card leave on its own; a second encode or a trimmed plate would
    both be a way for the card's length to stop matching the contract's.

    `shortest=1` is what makes the shot end at all. The plate arrives as `-loop 1`, an unbounded
    second input, and the composite then never reaches EOF: measured on this build, the chain
    without it was killed at 90 s with no moov atom written, and a stranded instance of it had
    burned 265 CPU-seconds inside five hours of wall clock while still producing frames at about
    one percent of a core. With `shortest=1` the same chain finishes in 1.9 s at exactly 180
    frames — the footage's own length, which is the length the record asked for.
    """
    seconds = float(contract["archive"]["source_card"]["seconds"])
    return f"overlay=0:0:shortest=1:enable='between(t,0,{seconds:g})'"


def card_filter(png, contract, canvas):
    """Hold the credit plate from the in-point for the declared seconds.

    An overlay of a full-canvas transparent PNG at 0:0, so nothing about the frame underneath has
    to be known — which is also why the plate is drawn canvas-sized rather than cropped to its
    text. The size check is on our own drawing: a plate the wrong shape is a card with a shifted
    caption, and the shift is invisible to every other gate in the pipeline.
    """
    if png and Path(png).is_file():
        size = probe_size(png)
        if size != tuple(canvas):
            raise ValueError(f"source card plate {png} is {size[0]}x{size[1]}, not the canvas "
                             f"{canvas[0]}x{canvas[1]}")
    return [card_enable(contract)]


def encode_args(src, dst, chain, contract, *, inputs=(), graph=None):
    """The command line, with the contract's canvas and the contract's encode knobs.

    `-an` and no `-c:a` anywhere: rule 17 strips the stock's embedded library music rather than
    mixing it down, and an audio codec option is the shape a later edit would read as permission
    to keep a stream.

    `-nostdin` because an ingest runs inside an unattended queue: ffmpeg's interactive key reader
    otherwise sits on whatever stdin the parent process handed it, which is a way for a step to be
    waiting on a keyboard nobody is at.
    """
    canvas, fps = canvas_of(contract), _fps(contract)
    enc = contract["archive"]["ingest_encode"]
    args = ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(src)]
    for extra in inputs:
        args += ["-loop", "1", "-framerate", f"{fps:g}", "-i", str(extra)]
    if graph is not None:
        args += ["-filter_complex", graph, "-map", "[vout]"]
    elif chain:
        args += ["-vf", ",".join(chain)]
    return args + ["-c:v", enc["codec"], "-preset", enc["preset"], "-crf", str(enc["crf"]),
                   "-pix_fmt", enc["pixel_format"], "-an",
                   "-r", f"{fps:g}", "-s", f"{canvas[0]}x{canvas[1]}", str(dst)]


def _graph(footage, container, card_overlay, container_index=None, card_index=None):
    """Label plumbing for the two shapes that need a second input.

    A designed container puts the footage *onto* the matte, so the matte is the overlay's main
    input and the running stream is its second — the opposite order to the card, which sits over
    the footage. Getting these the wrong way round is what an infinite looped matte does to a
    container: `shortest=1` is already in the filter string the aspect rule emits.
    """
    parts, label = [], "[0:v]"
    if footage:
        parts.append(f"{label}{','.join(footage)}[foot]")
        label = "[foot]"
    if container:
        parts.append(f"[{container_index}:v]{label}{container}[proj]")
        label = "[proj]"
    if card_overlay:
        parts.append(f"{label}[{card_index}:v]{card_overlay}[vout]")
        return ";".join(parts)
    if parts:
        # Cut by the label that was just written, not at the last "]": a filtergraph is full of
        # brackets, and slicing at the final one keeps the "[" of the label it means to replace —
        # which shipped `overlay=...[proj[vout]` to the encoder and died as "label does not exist".
        parts[-1] = parts[-1][:-len(label)] + "[vout]"
    return ";".join(parts)


def ingest_clip(src, dst, *, record, licence_row, contract, root=ROOT, card=False, ocr=_AUTO):
    """One archival source to one canvas-shaped intermediate, plus a record of what was decided.

    Returns the file with the duration that actually came out of the encoder, whether the frame
    was mirrored and on what grounds, and whether a card was drawn and why not if it was not. The
    reasons travel with the result because the QC gate and whoever reads the ledger need the
    ingest's reasoning, not only its output.
    """
    src, dst, root = Path(src), Path(dst), Path(root)
    canvas = canvas_of(contract)
    scanner = resolve_ocr(root) if ocr is _AUTO else ocr
    form = _enum(record, "form", contract["archive"]["archive_motion"]["form_enum"])
    fit, closing, container = _aspect_parts(record, contract, canvas)
    is_container = record["aspect"] == "designed_container"

    # The mirror question is settled before any filter is written, so that the chain is built
    # once with the decision already in it rather than spliced afterwards — a hflip that lands
    # after the pad mirrors the black bars with the picture, and reads as a frame that shifted.
    side, text_found = record.get("light_side"), None
    if side:
        if side != key_side(contract) and scanner:
            # Only a frame whose sides disagree is worth a scanner run: the OCR is the guard's
            # whole cost, and paying it where it cannot change the answer slows every ingest.
            text_found = has_readable_text(grab_frame(src, _readable_time(src),
                                                      scale_to=canvas), scanner)
    flipped, flip_reason = mirror_decision(record, contract, text_found=text_found,
                                           ocr_available=bool(scanner))

    if form == "still":
        box = fit_box(record, contract, canvas, probe_ratio(src))
        footage = still_filter(record, contract, canvas, record.get("seconds"), fit=box,
                               pad=None if is_container else closing, hflip=flipped)
    else:
        footage = (retime_filter(record, contract) + fit
                   + (["hflip"] if flipped else [])
                   + ([] if is_container else [closing]))

    extra_inputs, container_index, plate = [], None, None
    card_index = None
    if container:
        declared = record["container_image"]
        matte = Path(declared) if Path(declared).is_absolute() else resolve_path(root, declared)
        size = probe_size(matte)
        if size != canvas:
            raise ValueError(f"container_image {declared} is {size[0]}x{size[1]}, not the canvas "
                             f"{canvas[0]}x{canvas[1]} — the footage would land somewhere other "
                             "than the rectangle the record declared, and the offset would be the "
                             "matte's own rather than ours")
        extra_inputs.append(matte)
        container_index = len(extra_inputs)      # input 0 is the footage, so the first extra is 1

    card_drawn, card_reason = False, ""
    rules = contract["archive"]["source_card"]
    if card and not rules.get("on_screen", True):
        card_reason = "source_card.on_screen is false in the contract"
    elif card:
        text = card_text(licence_row, contract)
        if not text:
            card_reason = (f"the ledger row carries no {rules['text_field']} to show, so no card "
                           "is drawn rather than a blank plate over the frame")
        else:
            plate = write_card_png(_scratch() / f"{src.stem}-card.png", text, contract, canvas,
                                   root=root)
            extra_inputs.append(plate)
            card_index = len(extra_inputs)
            card_drawn = True
            card_reason = f"credit line held for {float(rules['seconds']):g}s from the in-point"

    if extra_inputs:
        graph = _graph(footage, container,
                       card_filter(plate, contract, canvas)[0] if card_drawn else None,
                       container_index, card_index)
        args = encode_args(src, dst, [], contract, inputs=extra_inputs, graph=graph)
    else:
        args = encode_args(src, dst, footage, contract)
    footage_seconds = float(record.get("seconds") or 0.0) if form == "still" \
        else probe_duration(src)
    _run(args, timeout=encode_ceiling(footage_seconds))
    return {"path": dst, "duration_s": probe_duration(dst), "flipped": flipped,
            "flip_reason": flip_reason, "card": card_drawn, "card_reason": card_reason}
