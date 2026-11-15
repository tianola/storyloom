"""Assemble one episode from its rendered visuals and its narration audio.

The film is named by `--episode`, the way `qc_episode.py` has always named it: nothing in this
file knows which episode exists. What is on screen comes from the episode's own `shots.json`, and
where each layer's clips live comes from `workflow/episode.py`, so the next episode — archival
shots included — is assembled by pointing this at its directory rather than by editing this file.
An episode that owed an edit to `tools/` to get its own shots is an episode that quietly inherited
the previous film's, because the person running the build is rarely the person who wrote the map.

Usage:
    python tools/assemble_episode.py --episode work/episode-artemis-ii
    python tools/assemble_episode.py --episode work/episode-artemis-ii --shot-lengths-only
"""
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import archive_ingest
import look_pass
import loudness
import music_bed
import audio_finish
import captions

import archive_ingest
import look_pass
import loudness
import music_bed
import audio_finish
import captions

from workflow.capabilities import REFUSED, stage_report  # noqa: E402
from workflow.config import style_contract  # noqa: E402
from workflow.episode import (  # noqa: E402
    archive_sources, graded_path, master, music_bed_path, render_dir, require_coverage, resolve,
    segments_dir, shot_lengths_path, shots, vo_dir,
)

# The delivery spec is the contract's, not this file's: qc_episode.py judges the master against
# the same numbers, so the mux and the gate cannot disagree about what "finished" means.
CONTRACT = style_contract(PROJECT_ROOT)
AUDIO = CONTRACT["audio"]

# How far past the last word the bed runs. The narration is the clock the visuals are cut to, so
# the bed has to overrun it — see add_music_bed.
BED_TAIL_S = 5.0

# The canvas is the contract's too, for the same reason the audio spec is: the beats are rendered
# by a different process, and if this file typed its own number the two would drift and the
# scale+pad below would quietly downscale the expensive layer. `DESIGN_WIDTH` is the one literal
# that stays here — it is the width the card geometry was drawn against, not a delivery size.
CANVAS = CONTRACT["canvas"]
DESIGN_WIDTH = 640
FPS = CANVAS["fps"]
WIDTH = CANVAS["width"]
HEIGHT = CANVAS["height"]
SCALE = WIDTH / DESIGN_WIDTH
BG_COLOR = (6, 8, 26)
GOLD = (212, 168, 67)
AMBER = (255, 179, 71)
CYAN = (95, 212, 255)
WHITE = (255, 255, 255)

# Two ways a layer's clips can be named: after the *shot* they belong to, which is what the
# renderers and the archive ingest are handed a length for, or after the single *utterance* they are
# drawn for, which is what a card is — one clip per sentence, timed in this run by that sentence's
# own samples. The exemption in `write_shot_lengths` and the filename in `visual_for` used to be two
# separate `== "cards"` tests, which is how a layer could end up cut by one rule and timed by
# another: an archival shot sliced per beat but left out of the length table renders a black frame,
# and a card aggregated into it hands the rhythm gate a beat that no camera move ever was.
PER_UTTERANCE_CLIPS = ("cards",)


def clip_stem(kind, uid, name):
    """The base name of the clip one utterance is cut from, without the extension."""
    return f"card-{uid}" if kind in PER_UTTERANCE_CLIPS else name


def narration_seconds(manifest, shot_map):
    """Seconds of narration sitting on each beat name, in the order the film speaks them.

    The one computation behind two answers: `shot_lengths.json` publishes it as whole seconds for
    the renderers, and the archive ingest needs the same number as a still's screen time. Measured
    on the manifest's own `sampleRate` for the reason `narration_rate` documents.
    """
    rate = narration_rate(manifest)
    seconds = {}
    for u in manifest["utterances"]:
        entry = shot_map.get(u["id"])
        if not entry or entry[0] in PER_UTTERANCE_CLIPS:
            continue
        seconds[entry[1]] = seconds.get(entry[1], 0.0) + u["samples"] / rate
    return seconds


def load_manifest(episode):
    with open(vo_dir(episode) / "manifest.json", encoding="utf-8") as f:
        return json.load(f)


def narration_rate(manifest) -> int:
    """Samples per second of the narration this episode ships — the divisor of every cut.

    `qc_episode.py` already reads `sampleRate` off the manifest; this file carried its own 24000,
    so the assembler and the gate held two answers to one question. Narration produced at any other
    rate would then land every beat long while the gate, using the manifest, still called the
    master clean. The rate is a fact about the audio, not about the tool.
    """
    return int(manifest["sampleRate"])


def concat_audio(episode, manifest):
    """Concatenate all utterance WAVs into one file."""
    print("Concatenating audio...", flush=True)
    audio_dir = vo_dir(episode)
    audio_path = audio_dir / "full-audio.wav"
    if audio_path.exists():
        return audio_path

    list_file = audio_dir / "concat-list.txt"
    with open(list_file, "w") as f:
        for u in manifest["utterances"]:
            f.write(f"file '{audio_dir / u['file']}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(audio_path),
    ], capture_output=True, check=True)
    print(f"  Audio: {audio_path}", flush=True)
    return audio_path


def add_music_bed(voice_path, bed_path, mixed_path):
    """Lay the generated bed under the narration and hand back the track for the mux.

    The bed is synthesised rather than sourced: anything that ships inside the master has to be
    Apache-2.0, and the free music libraries are not (see tools/music_bed.py). It is written
    `BED_TAIL_S` past the last word so no part of the narration is uncovered, and its outro closes
    at the last word rather than at the end of that file — a fade parked in the discarded tail is
    a fade nobody hears, and the episode would stop the music at full level.

    The mix is then cut back to the narration, because `loudnorm` integrates over the whole file:
    a music-only tail inside the audio `mux_final` measures drags that measurement down (~2 LU on
    a short fixture) and the delivery gain gets built for a length the master never reaches.
    """
    print("Adding the music bed...", flush=True)
    voice_duration = probe_duration(voice_path)
    music_bed.write_bed(bed_path, voice_duration + BED_TAIL_S, fade_end_s=voice_duration)
    uncut = Path(mixed_path).with_name(f"{Path(mixed_path).stem}-uncut.wav")
    music_bed.mix_under(voice_path, bed_path, uncut)
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-i", str(uncut),
        "-t", f"{voice_duration:.3f}",
        "-c:a", "pcm_s16le",
        str(mixed_path),
    ], check=True)
    uncut.unlink()
    print(f"  Bed: {bed_path} at {voice_duration + BED_TAIL_S:.1f}s under a "
          f"{voice_duration:.1f}s narration", flush=True)
    print(f"  Mixed audio: {mixed_path}", flush=True)
    return Path(mixed_path)


def _fade(colour, a):
    """Blend a card colour in from the background, for staged reveals."""
    a = max(0.0, min(1.0, a))
    return tuple(int(round(bg + (c - bg) * a)) for c, bg in zip(colour, BG_COLOR))


def _ramp(t, start, end):
    if end <= start:
        return 1.0 if t >= end else 0.0
    return max(0.0, min(1.0, (t - start) / (end - start)))


def _scan_band(axis, lo, hi, colour, peak_alpha):
    """A translucent light band across the frame, brightest in the middle of the travel.

    The house motion device for flat artwork: a still card or a sparse diagram has nothing to
    dolly or zoom, and a move that only shifts thin strokes measures as a photograph. A wide
    soft band crossing the frame changes a lot of area per second, which is what the gate's
    motion score actually responds to. manim gets the same idea as `scan_sweep`
    (tools/manim/artemis_manim.py).
    """
    span = hi - lo
    if span <= 1:
        return None
    pos = np.arange(WIDTH if axis == "x" else HEIGHT, dtype=np.float64)
    inside = (pos > lo) & (pos < hi)
    d = np.clip((pos - lo) / span, 0.0, 1.0)
    profile = np.where(inside, np.cos((d - 0.5) * math.pi) ** 2, 0.0)
    alpha = (profile * peak_alpha).astype(np.uint8)
    arr = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = colour
    if axis == "x":
        arr[..., 3] = alpha[None, :]
    else:
        arr[..., 3] = alpha[:, None]
    return Image.fromarray(arr, "RGBA")


def _overlay(img, band):
    if band is None:
        return img
    return Image.alpha_composite(img.convert("RGBA"), band).convert("RGB")


def card_frame(entry, t, duration_s):
    """One frame of an animated card.

    A card that is a still image is a photograph with narration over it, and the episode gate
    measures it as one (0.62-0.67 on Artemis II, against a grain floor of 0.62). Two devices
    keep it alive: content arrives in stages, and one soft band of light crosses the frame over
    the shot — the same scan sweep the manim diagrams use
    (tools/manim/artemis_manim.py: scan_sweep). Motion a viewer registers needs *area*
    changing, and a card is mostly empty background, so a zoom or a pan would not do it.

    The band travels one band-height past the frame on each side, so it enters and leaves
    instead of parking against an edge. Both ends of that travel are the score's weak points:
    a band clamped flat against the bottom has one moving edge instead of two and measured
    1.20 against the 1.3 still bound. The last 2.5-3.0 s are a deliberate settle, well inside
    the 10 s static limit the rule is actually about.
    """
    kind = entry[1]
    title = entry[2] if len(entry) > 2 else ""
    subtitle = entry[3] if len(entry) > 3 else ""
    if kind not in ("bar-chart", "process"):
        raise ValueError(f"no animated card for kind {kind!r}; a still card fails the gate")

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    def s(px):
        # Every number below is a proportion of the 640x360 canvas the cards were
        # designed on, not an absolute pixel count.
        return int(round(px * SCALE))

    try:
        font_title = ImageFont.truetype("arial.ttf", s(28))
        font_sub = ImageFont.truetype("arial.ttf", s(18))
    except OSError:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    y_center = HEIGHT // 2
    border = s(40)
    edge = CYAN if kind == "process" else GOLD
    head = CYAN if kind == "process" else AMBER
    a_frame = _ramp(t, 0.0, 1.0)
    draw.rectangle([(border, border), (WIDTH - border, HEIGHT - border)],
                   outline=_fade(edge, a_frame), width=max(1, s(2)))
    sweep_end = duration_s - (2.5 if kind == "bar-chart" else 3.0)

    if kind == "bar-chart":
        bbox = draw.textbbox((0, 0), title, font=font_title)
        tw = bbox[2] - bbox[0]
        draw.text(((WIDTH - tw) // 2, s(60)), title, fill=_fade(head, a_frame),
                  font=font_title)
        if subtitle:
            parts = subtitle.split(" | ")
            bar_y = y_center - s(10)
            bar_w = (WIDTH - s(160)) // max(len(parts), 1)
            grow_end = max(sweep_end, 3.0)
            for i, part in enumerate(parts):
                x = s(80) + i * bar_w
                full_h = s(40) + (len(parts) - i) * s(15)
                p = _ramp(t, 1.0 + i * 0.9, grow_end)
                h = int(full_h * p)
                if h > 0:
                    draw.rectangle([(x, bar_y - h), (x + bar_w - s(10), bar_y)], fill=GOLD)
                la = _ramp(p, 0.7, 1.0)
                if la > 0:
                    bbox2 = draw.textbbox((0, 0), part, font=font_sub)
                    pw = bbox2[2] - bbox2[0]
                    draw.text((x + (bar_w - s(10) - pw) // 2, bar_y + s(5)), part,
                              fill=_fade(WHITE, la), font=font_sub)
        p = _ramp(t, 0.5, sweep_end)
        if p > 0:
            half = s(90)
            cx = int(-half + p * (WIDTH + 2 * half))
            img = _overlay(img, _scan_band("x", cx - half, cx + half,
                                           (255, 255, 255), 48))

    else:  # process: a validation pass reads the card top to bottom
        bbox = draw.textbbox((0, 0), title, font=font_title)
        tw = bbox[2] - bbox[0]
        draw.text(((WIDTH - tw) // 2, y_center - s(50)), title, fill=_fade(head, a_frame),
                  font=font_title)
        sa = _ramp(t, 1.2, 2.0)
        if subtitle and sa > 0:
            for i, part in enumerate(subtitle.split(" | ")):
                bbox2 = draw.textbbox((0, 0), part, font=font_sub)
                sw = bbox2[2] - bbox2[0]
                draw.text(((WIDTH - sw) // 2, y_center + s(5) + i * s(28)), part,
                          fill=_fade(WHITE, sa), font=font_sub)
        p = _ramp(t, 1.0, sweep_end)
        if p > 0:
            # The pass leaves a faint validated tint behind it and a soft light band at its
            # leading edge. The band travels one band-height past the card's bottom so the
            # settled frame is clean; stopping it at the border clamps the band flat and
            # leaves one moving edge instead of two, which measured 1.20 against the 1.3 bound.
            half = s(90)
            cy = int(-half + p * (HEIGHT + 2 * half))
            fill = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            y1 = max(border, min(HEIGHT - border, cy))
            if y1 > border:
                ImageDraw.Draw(fill).rectangle(
                    [(border, border), (WIDTH - border, y1)], fill=(95, 212, 255, 22))
            img = _overlay(_overlay(img, fill),
                           _scan_band("y", cy - half, cy + half, (255, 255, 255), 60))

    return img


def make_scene_card_clip(entry, output_path, duration_s):
    """Render an animated card straight into an mp4, one raw frame per tick."""
    frames = int(round(duration_s * FPS))
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20",
         str(output_path)],
        stdin=subprocess.PIPE)
    for f in range(frames):
        proc.stdin.write(card_frame(entry, f / FPS, duration_s).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed while encoding {output_path}")
    return output_path


def make_scene_card(entry, output_path, duration_s=10.0):
    """The card's settled final frame, for anything that wants a still of it."""
    card_frame(entry, duration_s, duration_s).save(str(output_path))
    return output_path


def generate_cards(episode, manifest, shot_map):
    """Render every card as a clip sized to the utterance it plays under."""
    print("Generating scene cards...", flush=True)
    cards_dir = render_dir(episode, "cards", CONTRACT)
    cards_dir.mkdir(parents=True, exist_ok=True)
    rate = narration_rate(manifest)

    seen = set()
    for u in manifest["utterances"]:
        uid = u["id"]
        entry = shot_map.get(uid)
        if entry and entry[0] == "cards":
            clip_name = f"{clip_stem(entry[0], uid, entry[1])}.mp4"
            if clip_name not in seen:
                make_scene_card_clip(entry, cards_dir / clip_name, u["samples"] / rate)
                seen.add(clip_name)

    print(f"  Generated {len(seen)} animated scene cards", flush=True)


def ingest_archive(episode, manifest, shot_map, contract, root=PROJECT_ROOT):
    """Produce every archival shot's canvas-shaped clip before anything is cut from it.

    Called next to `generate_cards`, so that all four layers exist before `build_segments` starts
    slicing: that function refuses a shot with no source rather than printing a warning, which is
    decision D-043, so an ingest left to be remembered by the operator turns a whole episode build
    into a crash at the ninety-minute mark instead of a refusal at the ninth.

    **What screen time an archival clip gets, and why.** Two different questions, and the contract
    answers each somewhere else:

      *form: clip* — the ingest is given none. `archive_ingest.ingest_clip` has no duration
      parameter for a clip on purpose: `retime_to_natural` and `period_motion` decide how source
      frames map onto canvas seconds, so trimming the output by a wall-clock number would leave the
      finished quotation no longer the `in_timecode → out_timecode` span the rights row documents,
      and `rights.quotation_ceiling_rule` measures the fair-use ceiling on exactly that span. The
      source file under `assets/archive/` is the quotation, already cut to it when it was fetched.

      *form: still* — the ingest is given the narration over the shot. A still has no length of its
      own, and `still_filter` refuses to guess one because the pan's rate is capped against
      `camera.max_deg_per_second` per second of screen time. The number the cut will actually spend
      is `narration_seconds()`, the same computation that publishes `shot_lengths.json`, so the move
      is sized for the shot it plays in: a still shorter than its sentence freezes on its last frame
      — the dead still `archive_motion.stills_never_dead` names — while a longer one is sliced back
      by the segment build. The record's own `seconds` therefore does not win, and the file on disk
      is left as its author wrote it.

    Nothing here enforces `archive_rhythm.max_archival_shot_seconds`: the gate measures that on
    `shot_lengths.json` (#148), and a second enforcement point in the cutter is one more place for
    the bound to disagree with itself. Clips already on disk are not re-ingested — caching is how
    this pipeline survives a re-run — and the return value is the list of what was made now.
    """
    sources = archive_sources(episode, contract)
    if not sources:
        return []
    seconds = narration_seconds(manifest, shot_map)
    missing = [name for name, entry in sources.items() if not entry["clip"].is_file()]
    if not missing:
        print(f"Ingesting the archive: {len(sources)} clips already on disk, nothing to do",
              flush=True)
        return []

    print(f"Ingesting {len(missing)} archival shot(s) of {len(sources)}...", flush=True)
    made = []
    for name in sorted(missing):
        entry = sources[name]
        record = dict(entry["record"])
        if record.get("form") == "still":
            record["seconds"] = seconds[name]
        entry["clip"].parent.mkdir(parents=True, exist_ok=True)
        archive_ingest.ingest_clip(entry["source"], entry["clip"], record=record,
                                   licence_row=entry["licence"], contract=contract, root=root,
                                   card=True)
        print(f"  {name}: {entry['source'].name} -> {entry['clip']}", flush=True)
        made.append(entry["clip"])
    return made


def visual_for(episode, uid, entry, contract):
    """The source clip an utterance is cut from, or a refusal naming the shot that has none.

    Each layer keeps its own directory, and the archival layer's is contract data rather than a
    literal here — a rename in `style.json` moves the render, the ingest and this reader together.
    The name inside it comes from `clip_stem`: cards are per-utterance (`card-uNNN`) because the
    clip is drawn for one sentence, every other layer per shot name because the clip is one beat
    sliced across the sentences that play over it. A card whose animation is still a still image
    falls back to the PNG so the old artwork keeps assembling; the archival layer gets no such
    fallback, because `ingest_clip` turns even a `form: still` source into a moving mp4 and one
    code path over the layer is what keeps the segment builder from needing to know which kinds
    came from a photograph.
    """
    kind, name = entry[0], entry[1]
    directory = render_dir(episode, kind, contract)
    clip = directory / f"{clip_stem(kind, uid, name)}.mp4"
    if clip.is_file():
        return clip
    if kind in PER_UTTERANCE_CLIPS:
        still = directory / f"{clip_stem(kind, uid, name)}.png"
        if still.is_file():
            return still
    raise ValueError(
        f"{uid} is cut onto {kind} shot {name!r}, but {directory} holds no clip for it; "
        "render it (python tools/rollout_render.py) or reassign the shot before assembling")


def write_shot_lengths(episode, manifest, shot_map):
    """Publish how much narration sits on each beat, for the renderers to size to.

    A beat is one continuous camera move, so it has to run as long as every utterance that
    plays over it summed together; a 5 s beat under a 15 s sentence gets looped and the move
    restarts mid-word. The Blender script cannot import this module (its Python has no PIL),
    so the numbers travel as a file rather than as a call.

    The layers that owe an entry are `layers(contract)` minus `PER_UTTERANCE_CLIPS`, and that is
    the whole rule rather than a list of exemptions grown one `if` at a time: a layer whose clips
    come from something outside this run — a Blender beat, a manim scene, forty seconds of Apollo
    footage — has to be told how long to be, and it is the film's beat timing here that tells it,
    the same table the rhythm gate measures `max_archival_shot_seconds` against. Only a layer drawn
    inside this run at the exact length of its own sentence already knows, and an aggregated number
    for it would describe a beat that never existed. And this writes only the lengths — `shots.json`
    is the authoring the assembler reads, so publishing a copy of the read back over it would let a
    run overwrite somebody's shot list with its own reading of it.
    """
    seconds = narration_seconds(manifest, shot_map)
    path = shot_lengths_path(episode)
    path.write_text(json.dumps({k: int(np.ceil(v)) for k, v in seconds.items()},
                               indent=1), encoding="utf-8")
    print(f"  Wrote {len(seconds)} shot lengths to {path}", flush=True)
    return path


def build_segments(episode, manifest, shot_map):
    """Build individual video segments for each utterance."""
    print("Building video segments...", flush=True)
    seg_dir = segments_dir(episode)
    seg_dir.mkdir(parents=True, exist_ok=True)
    consumed = {}
    rate = narration_rate(manifest)

    for u in manifest["utterances"]:
        uid = u["id"]
        duration_s = u["samples"] / rate
        visual_path = visual_for(episode, uid, shot_map[uid], CONTRACT)
        seg_path = seg_dir / f"{uid}.mp4"

        # The cursor advances whether or not this segment is already cached: a cached slice
        # still occupies its span of the beat, and skipping the bookkeeping would hand every
        # later utterance the first slice again — a half-populated segments/ directory would
        # then assemble a rewindy episode that looks like the fix did nothing.
        start = None
        if visual_path.suffix.lower() == ".mp4":
            start = consumed.get(str(visual_path), 0.0)
            consumed[str(visual_path)] = start + duration_s

        if seg_path.exists():
            continue

        ext = visual_path.suffix.lower()
        if ext == ".png":
            subprocess.run([
                "ffmpeg", "-y",
                "-loop", "1", "-i", str(visual_path),
                "-t", str(duration_s),
                "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "ultrafast", "-crf", "23",
                "-r", str(FPS),
                str(seg_path),
            ], capture_output=True, check=True)
        elif ext == ".mp4":
            # Each utterance takes the next slice of its beat instead of replaying it from
            # frame 0: two sentences over one shot are two halves of one camera move, and
            # restarting the move at every sentence boundary is the rewind the episode
            # reads as motion graphics. A short source loops only when the narration asks for
            # more screen time; cloning its last frame would turn archival motion into a still.
            src_dur = probe_duration(visual_path)
            vf = (f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
                  f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2")
            overrun = start + duration_s - src_dur
            if overrun > 0:
                input_args = ["-stream_loop", "-1", "-i", str(visual_path),
                              "-ss", f"{start:.3f}"]
            else:
                input_args = ["-ss", f"{start:.3f}", "-i", str(visual_path)]
            subprocess.run([
                "ffmpeg", "-y",
                *input_args,
                "-t", str(duration_s),
                "-vf", vf,
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "ultrafast", "-crf", "23",
                "-r", str(FPS),
                "-an",
                str(seg_path),
            ], capture_output=True, check=True)

    print(f"  Built {len(list(seg_dir.glob('*.mp4')))} segments", flush=True)


def concat_segments(episode, manifest):
    """Concatenate all segments into one video (no audio)."""
    print("Concatenating segments...", flush=True)
    seg_dir = segments_dir(episode)
    video_only = episode / "video-only.mp4"

    list_file = episode / "segment-list.txt"
    with open(list_file, "w") as f:
        for u in manifest["utterances"]:
            seg = seg_dir / f"{u['id']}.mp4"
            f.write(f"file '{seg}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(video_only),
    ], capture_output=True, check=True)
    print(f"  Video: {video_only}", flush=True)
    return video_only


def mux_final(episode, video_path, audio_path, output=None, captions_path=None):
    """Combine video and audio into the final episode, at the contract's loudness and rate.

    The video is copied, never re-encoded: the grade already happened in `look_pass`, and a
    second x264 pass would only cost quality and an hour. Everything here is an audio decision.
    """
    print("Muxing final episode...", flush=True)
    output = Path(output) if output else master(episode)
    measured = loudness.measure(audio_path)
    print(f"  Narration measures {measured['input_i']} LUFS, {measured['input_tp']} dBFS true peak; "
          f"target {AUDIO['integrated_lufs_target']} LUFS", flush=True)
    inputs = ["-i", str(video_path), "-i", str(audio_path)]
    maps, subs = [], []
    if captions_path:
        # a soft subtitle stream: players offer it, nothing is burned into the picture
        inputs += ["-i", str(captions_path)]
        maps = ["-map", "0:v", "-map", "1:a", "-map", "2:0"]
        subs = ["-c:s", "mov_text", "-metadata:s:s:0", "language=eng"]
    subprocess.run([
        "ffmpeg", "-y", *inputs, *maps,
        "-filter:a", loudness.loudnorm_filter(measured),
        "-ac", str(AUDIO["channels_min"]),
        "-c:v", "copy", "-c:a", "aac", *subs,
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output),
    ], capture_output=True, check=True)

    size_mb = output.stat().st_size / 1024 / 1024
    print(f"\n  FINAL: {output} ({size_mb:.1f} MB)", flush=True)
    return output


def probe_duration(path):
    """Get duration of a media file in seconds."""
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ], capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def verify(episode, manifest, output=None):
    """Verify the final episode."""
    print("\n=== Verification ===", flush=True)
    output = Path(output) if output else master(episode)
    audio_dur = probe_duration(vo_dir(episode) / "full-audio.wav")
    episode_dur = probe_duration(output)
    expected_dur = manifest["totalSamples"] / narration_rate(manifest)

    print(f"  Expected duration: {expected_dur:.1f}s", flush=True)
    print(f"  Audio duration:    {audio_dur:.1f}s", flush=True)
    print(f"  Episode duration:  {episode_dur:.1f}s", flush=True)

    if abs(episode_dur - expected_dur) < 2.0:
        print("  Duration: OK", flush=True)
    else:
        print(f"  Duration: MISMATCH (delta={episode_dur - expected_dur:.1f}s)", flush=True)

    print(f"  Output: {output}", flush=True)


def main(argv=None, host=None, root=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    root = PROJECT_ROOT if root is None else Path(root)

    # The edit stage is a hundred ffmpeg calls long, so it asks the registry first: a moved binary
    # or a stale contract costs seconds to find out about here and thirty minutes to find out about
    # halfway through the segment build. It runs before the argument parse on purpose — a refusal
    # is the same answer whichever film was asked for.
    refusal = stage_report(PROJECT_ROOT, "edit", host=host)
    if refusal:
        print(f"assemble_episode: {refusal}", file=sys.stderr)
        return REFUSED

    parser = argparse.ArgumentParser(
        description="Assemble one episode from its rendered visuals and its narration audio.")
    parser.add_argument("--episode", required=True,
                        help="episode directory or slug under work/ (required: this tool has no "
                             "current episode of its own)")
    parser.add_argument("--remux", action="store_true",
                        help="redo only the sound and captions over the video already graded")
    parser.add_argument("--out", help="write the master here instead of the episode's own path")
    parser.add_argument("--no-finish", action="store_true",
                        help="skip sentence levelling, level rides and transition sounds")
    parser.add_argument("--burn-captions", action="store_true",
                        help="also burn the captions into the picture (re-encodes the video)")
    parser.add_argument("--shot-lengths-only", action="store_true",
                        help="publish the per-beat narration lengths and stop, without building")
    args = parser.parse_args(argv)

    episode = resolve(root, args.episode)
    shot_map = shots(episode, CONTRACT)
    manifest = load_manifest(episode)

    # Coverage is checked before the first ffmpeg call: assembling a film whose shot table and
    # narration describe different timelines produces a master that looks finished.
    require_coverage(episode, shot_map, [u["id"] for u in manifest["utterances"]])

    print(f"=== {episode.name}: episode assembly ===\n", flush=True)
    print(f"Loaded manifest: {len(manifest['utterances'])} utterances, "
          f"{manifest['totalSamples']} samples "
          f"({manifest['totalSamples'] / narration_rate(manifest):.1f}s) "
          f"over {len(shot_map)} shots\n", flush=True)

    write_shot_lengths(episode, manifest, shot_map)
    if args.shot_lengths_only:
        return 0

    voice_path = concat_audio(episode, manifest)
    if not args.no_finish:
        print("Finishing the narration (levels, level rides, transitions)...", flush=True)
        voice_path, _ = audio_finish.finish_voice(episode, manifest, json.loads(
            (episode / "shots.json").read_text(encoding="utf-8")))
    audio_path = add_music_bed(voice_path, music_bed_path(episode),
                               vo_dir(episode) / "full-audio-with-bed.wav")
    captions_path = captions.write_all(episode, manifest)
    if args.remux:
        video_path = graded_path(episode)
        if not video_path.is_file():
            print(f"assemble_episode: --remux needs the graded video {video_path}", file=sys.stderr)
            return 1
    else:
        generate_cards(episode, manifest, shot_map)
        ingest_archive(episode, manifest, shot_map, CONTRACT, root=root)
        build_segments(episode, manifest, shot_map)
        video_path = concat_segments(episode, manifest)
        video_path = look_pass.apply(video_path, graded_path(episode))
    output = Path(args.out) if args.out else master(episode)
    mux_final(episode, video_path, audio_path, output=output, captions_path=captions_path)
    if args.burn_captions:
        burned = output.with_name(output.stem + "-burned.mp4")
        captions.attach(output, captions_path, burned, burn=True)
        print(f"  Burned captions: {burned}", flush=True)
    verify(episode, manifest, output)

    print("\nDone!", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
