"""Does the finished episode obey the house style? Measured, on the shipped pixels.

    python tools/qc_episode.py --episode work/episode-artemis-ii \
        --master work/episode-artemis-ii/episode-artemis-ii.mp4

Every bound comes from `workflow/style.json`, so this script holds no opinions of its own:
change the contract and the gate moves with it. It exists because the two defects that most
recently cost this project a multi-hour re-render were invisible to the build — a beat that
renders successfully can still be a photograph held for eighteen seconds, and a mux that
exits zero can still ship eleven LU under the loudness the platform normalises to.

Three kinds of check, deliberately separated:

  * measured on decoded pixels — motion and loudness, which no upstream artefact can attest to;
  * read from ffprobe — canvas, streams, duration;
  * read from the episode's own files — the timeline, the shot map, the licence manifest.

Exit status is 1 when anything reports `error`. `warn` is printed and does not fail the build,
because a warning is a taste judgement the operator may overrule; an error is a contract breach.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import statistics
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflow import archive  # noqa: E402
from workflow.capabilities import REFUSED, stage_report  # noqa: E402
from workflow.config import style_contract  # noqa: E402
from workflow.episode import (  # noqa: E402
    resolved_cut,
    EPISODE_DOCUMENT, document as read_episode_document, graded_path,
)
from loudness import loudnorm_filter, measure as delivery_measure  # noqa: E402

MOTION_SPAN = 1.0   # seconds between the two frames a motion score compares
MOTION_OFFSET = 0.2  # fraction of the shot at which to take them, so the cut itself is not measured
MUSIC_FLOOR_PERCENTILE = 5   # of ffmpeg's 100 ms momentary track: the floor between the words
CUT_WINDOW = 1.0   # seconds of master read on each side of a cut, for the source-change rule


@dataclass(frozen=True)
class Shot:
    id: str
    kind: str
    name: str
    start: float
    duration: float
    lines: tuple = ()          # the narration lines a cut-list shot plays over


@dataclass(frozen=True)
class Finding:
    severity: str   # "error" fails the build, "warn" is printed for the operator
    code: str
    subject: str
    message: str


def error(code, subject, message):
    return Finding("error", code, subject, message)


def warn(code, subject, message):
    return Finding("warn", code, subject, message)


# ---------------------------------------------------------------- measurement

def probe(master: Path) -> dict:
    """Container truth: canvas, frame rate, stream counts, audio shape, duration."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(master)],
        capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    if video is None:
        raise ValueError(f"{master} has no video stream")
    return {
        "width": int(video["width"]),
        "height": int(video["height"]),
        "fps": video.get("r_frame_rate", "0/1"),
        "duration": float(data["format"]["duration"]),
        "video_streams": sum(1 for s in data["streams"] if s["codec_type"] == "video"),
        "audio_streams": sum(1 for s in data["streams"] if s["codec_type"] == "audio"),
        "subtitle_streams": sum(1 for s in data["streams"] if s["codec_type"] == "subtitle"),
        "audio_channels": int(audio["channels"]) if audio else 0,
        "audio_sample_rate": int(audio["sample_rate"]) if audio else 0,
    }


def loudness(master: Path) -> tuple[float, float, float]:
    """ITU-R BS.1770 integrated loudness, true peak and range, from ffmpeg's ebur128."""
    proc = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(master), "-map", "a:0",
         "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True)
    log = proc.stderr
    integrated = re.findall(r"I:\s*(-?[\d.]+)\s*LUFS", log)
    peak = re.findall(r"Peak:\s*(-?[\d.]+)\s*dBFS", log)
    lra = re.findall(r"LRA:\s*(-?[\d.]+)\s*LU", log)
    if not integrated or not peak:
        raise ValueError(f"could not read loudness from {master}; ffmpeg said:\n{log[-800:]}")
    return float(integrated[-1]), float(peak[-1]), float(lra[-1]) if lra else 0.0


def momentary_floor(path: Path) -> float | None:
    """The floor of BS.1770 momentary loudness: what the programme plays between the words.

    ffmpeg prints a momentary value every 100 ms over a 400 ms window. The percentile rather than
    the minimum is the number, because a single silent frame at the head or tail is not a mix
    decision, and `-120.x` is ebur128's sentinel for digital silence rather than a measurement.
    Returns None when the file yields no readable track at all.
    """
    proc = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path), "-map", "a:0",
         "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True)
    values = np.array([float(v) for v in re.findall(r"M:\s*(-?[\d.]+)", proc.stderr)], dtype=float)
    values = values[values > -100.0]
    if not values.size:
        return None
    return float(np.percentile(values, MUSIC_FLOOR_PERCENTILE))


def narration_floor(episode: Path, contract: dict) -> float | None:
    """The bare narration's floor, pushed to the delivery target so the master's is comparable.

    The stem sits ~11 LU under the target, and a floor read at one level is not the same number as
    a floor read at another, so the stem goes through the delivery filter the assembler puts the
    mix through. Nothing is inferred from the stem's own integrated reading: `loudnorm` in dynamic
    mode moves a deep floor by more than the average gain — 1.1 dB on the Artemis II narration —
    and this check is about a 4 dB gap.
    """
    stem = Path(episode) / "vo/full-audio.wav"
    if not stem.is_file():
        return None
    audio = contract["audio"]
    with tempfile.TemporaryDirectory() as td:
        at_target = Path(td) / "narration-at-target.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(stem),
             "-af", loudnorm_filter(delivery_measure(stem, audio), audio),
             "-c:a", "pcm_s16le", str(at_target)], check=True)
        return momentary_floor(at_target)


def frame(master: Path, when: float) -> np.ndarray:
    with tempfile.TemporaryDirectory() as td:
        png = Path(td) / "f.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0.0, when):.3f}",
                        "-i", str(master), "-frames:v", "1", str(png)],
                       capture_output=True, check=True)
        return np.asarray(Image.open(png).convert("L"), dtype=np.float64)


def motion(master: Path, start: float, span: float = MOTION_SPAN) -> float:
    """Mean absolute greyscale difference between two frames `span` seconds apart.

    This is the number the rhythm rule is written against. It is not optical flow and it does
    not know what moved: it answers the only question that matters for a static hold, which is
    whether a viewer watching this span would see a photograph or a shot. `look_pass` adds film
    grain to every frame, so a genuinely frozen image still scores about 0.7 — that floor is why
    the contract's bound is 2.0 rather than something near zero.
    """
    a = frame(master, start)
    b = frame(master, start + span)
    return float(np.abs(a - b).mean())


def measure_motions(master: Path, shots: list[Shot], span: float = MOTION_SPAN) -> dict[str, float]:
    scores = {}
    for shot in shots:
        offset = min(1.0, shot.duration * MOTION_OFFSET)
        if shot.duration < offset + span + 0.2:
            offset = max(0.0, shot.duration - span - 0.2)
        scores[shot.id] = round(motion(master, shot.start + offset, span), 3)
    return scores


# ---------------------------------------------------------------- timeline

def load_timeline(episode: Path) -> list[Shot]:
    """The shot list as it was actually published: narration timing plus the assembler's map.

    `vo/manifest.json` owns the clock (startSample/samples at the TTS sample rate) and
    `shots.json` owns what is on screen. Keeping the map in a file rather than importing it from
    the assembler is what makes this gate usable for the next episode, whose assembler will not
    be `assemble_episode.py`.
    """
    cut = resolved_cut(episode)
    if cut is not None:
        # A cut-list episode publishes the cut it was made to; its shots are the timeline.
        return [Shot(id=s["id"], kind=s["source"]["kind"], name=s["source"]["name"],
                     start=s["start"], duration=s["end"] - s["start"], lines=tuple(s.get("lines", ())))
                for s in cut["shots"]]
    manifest = json.loads((episode / "vo/manifest.json").read_text(encoding="utf-8"))
    sample_rate = manifest["sampleRate"]
    shot_map = json.loads((episode / "shots.json").read_text(encoding="utf-8"))
    shots = []
    for u in sorted(manifest["utterances"], key=lambda x: x["startSample"]):
        entry = shot_map.get(u["id"], {})
        shots.append(Shot(
            id=u["id"],
            kind=entry.get("kind", "unknown"),
            name=entry.get("name", f"unmapped-{u['id']}"),
            start=u["startSample"] / sample_rate,
            duration=u["samples"] / sample_rate,
        ))
    return shots


def manifest_ids(episode: Path) -> list[str]:
    manifest = json.loads((episode / "vo/manifest.json").read_text(encoding="utf-8"))
    return [u["id"] for u in manifest["utterances"]]


def licence_entries(episode: Path) -> list[dict]:
    path = episode / "assets/license-manifest.json"
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- checks

def check_static_holds(shots, motions, contract) -> list[Finding]:
    """The rule the brief states: nothing holds as a still for longer than ten seconds."""
    rhythm = contract["rhythm"]
    static_max = rhythm["motion_static_max"]
    limit = rhythm["max_static_seconds"]
    findings = []
    for shot in shots:
        score = motions.get(shot.id)
        if score is None:
            findings.append(error("motion_unmeasured", shot.name,
                                  f"{shot.id} has no motion measurement, so its static hold "
                                  "cannot be judged"))
            continue
        if score < static_max and shot.duration > limit:
            findings.append(error(
                "static_hold", shot.name,
                f"{shot.id} ({shot.kind}) holds {shot.duration:.1f}s at motion {score:.2f}, "
                f"under the {static_max} still threshold and past the {limit:.0f}s limit — "
                "it reads as a photograph with narration over it"))
    return findings


def check_slow_shots(shots, motions, contract) -> list[Finding]:
    rhythm = contract["rhythm"]
    findings = []
    for shot in shots:
        score = motions.get(shot.id)
        if score is None:
            continue
        if rhythm["motion_static_max"] <= score < rhythm["motion_slow_max"]:
            findings.append(warn(
                "slow_shot", shot.name,
                f"{shot.id} moves at {score:.2f} for {shot.duration:.1f}s — above the still "
                "threshold but the slowest band in the episode; check it is a deliberate drift"))
    return findings


def check_hook(opening_motion, contract) -> list[Finding]:
    rhythm = contract["rhythm"]
    if opening_motion < rhythm["motion_static_max"]:
        return [error("hook_static", f"first {rhythm['hook_max_seconds']:.0f}s",
                      f"the opening measures {opening_motion:.2f}, which is a still — the hook "
                      "window is the only part of the video every viewer sees")]
    return []


def check_loudness(integrated, peak, contract) -> list[Finding]:
    audio = contract["audio"]
    target = audio["integrated_lufs_target"]
    findings = []
    if abs(integrated - target) > audio["loudness_tolerance_lu"]:
        findings.append(error(
            "loudness_off_target", "audio",
            f"integrated {integrated:.1f} LUFS against a {target:.1f} LUFS target "
            f"({integrated - target:+.1f} LU) — the platform normalises to {target:.0f}, so this "
            "master will be gain-ridden on playback"))
    if peak > audio["true_peak_max_dbfs"]:
        findings.append(error(
            "true_peak_over", "audio",
            f"true peak {peak:.1f} dBFS over the {audio['true_peak_max_dbfs']:.1f} dBFS ceiling — "
            "transcoding to lossy will clip it"))
    return findings


def check_music_bed(master_floor, stem_floor, contract) -> list[Finding]:
    """Is there anything at all under the voice in the delivered master?

    Integrated loudness cannot answer this: `loudnorm` normalises a bedless and a bed-bearing mix
    onto the same -14 LUFS, so a dropped bed is invisible to every other number this gate reads —
    and a silent master still measures the same true peak. The floor is the signature that
    survives normalisation, because a bed keeps playing in the gaps the narration leaves.
    """
    audio = contract["audio"]
    if master_floor is None or stem_floor is None:
        missing = "master" if master_floor is None else "narration stem in vo/full-audio.wav"
        return [error("music_bed_unmeasurable", "audio",
                      f"no momentary loudness floor could be read from the {missing}, so the bed "
                      "cannot be judged; an unmeasured bed is not a verified one")]
    bound = audio["music_floor_lift_min_db"]
    lift = master_floor - stem_floor
    if lift < bound:
        return [error("music_bed_missing", "audio",
                      f"the master falls to {master_floor:.1f} LUFS between the words where the "
                      f"bare narration falls to {stem_floor:.1f} — a lift of {lift:+.1f} dB against "
                      f"a {bound:.1f} dB minimum, so nothing is audible under the voice even though "
                      f"the bed is mixed {audio['music_under_voice_db']:.0f} dB under it")]
    return []


def check_audio_format(channels, sample_rate, contract) -> list[Finding]:
    audio = contract["audio"]
    findings = []
    if channels and channels < audio["channels_min"]:
        findings.append(warn(
            "audio_mono", "audio",
            f"{channels} channel(s) at {sample_rate} Hz; the contract asks for "
            f"{audio['channels_min']} — a stereo master survives platform transcoding better"))
    if sample_rate and sample_rate < audio["sample_rate_min"]:
        findings.append(warn(
            "audio_sample_rate_low", "audio",
            f"{sample_rate} Hz is under the {audio['sample_rate_min']} Hz floor; the platform "
            "upsamples anyway, so ship the higher rate"))
    return findings


def check_canvas(width, height, fps, contract) -> list[Finding]:
    canvas = contract["canvas"]
    findings = []
    if (width, height) != (canvas["width"], canvas["height"]):
        findings.append(error(
            "canvas_resolution", "video",
            f"{width}x{height} against a contracted {canvas['width']}x{canvas['height']} — the "
            "assembler pads and downscales silently, so a mismatch never fails the render"))
    try:
        num, den = fps.split("/")
        measured = float(num) / float(den) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        measured = 0.0
    if abs(measured - canvas["fps"]) > 0.01:
        findings.append(error("canvas_fps", "video",
                              f"{measured:.3f} fps against a contracted {canvas['fps']} fps"))
    return findings


def check_duration(measured, expected, contract) -> list[Finding]:
    tolerance = contract["qc"]["duration_tolerance_seconds"]
    if abs(measured - expected) > tolerance:
        return [error("duration_mismatch", "video",
                      f"video is {measured:.2f}s but the narration manifest asks for "
                      f"{expected:.2f}s (tolerance {tolerance:.1f}s) — a segment was dropped, "
                      "duplicated or cached from an older build")]
    return []


def check_streams(streams, contract) -> list[Finding]:
    findings = []
    if streams["audio_streams"] == 0:
        findings.append(error("no_audio", "video", "the master has no audio stream"))
    if streams["video_streams"] > 1:
        findings.append(warn("multiple_video_streams", "video",
                             f"{streams['video_streams']} video streams; players pick the first"))
    return findings


def check_captions(subtitle_streams, contract) -> list[Finding]:
    if subtitle_streams:
        return []
    required = contract["qc"]["captions_required"]
    make = error if required else warn
    return [make("no_captions", "video",
                 "no subtitle stream in the master — captions are the difference between a video "
                 "that works muted and one that does not")]


def check_coverage(shots, ids, contract) -> list[Finding]:
    mapped = {s.id for s in shots} | {line for s in shots for line in s.lines}
    missing = [i for i in ids if i not in mapped]
    if missing:
        return [error("shot_missing", "timeline",
                      f"narration without a shot: {', '.join(missing)} — the assembler fills "
                      "these with black")]
    return []


def check_long_shots(shots, contract) -> list[Finding]:
    limit = contract["rhythm"]["max_shot_seconds"]
    return [warn("shot_too_long", s.name,
                 f"{s.id} runs {s.duration:.1f}s without a cut, past the {limit:.0f}s limit — "
                 "one idea per shot, and this one has had time to become two")
            for s in shots if s.duration > limit]


def check_licence_entries(entries, contract) -> list[Finding]:
    required = contract["qc"]["licence_required_keys"]
    findings = []
    for entry in entries:
        missing = [k for k in required if not entry.get(k)]
        if missing:
            findings.append(error(
                "licence_entry_incomplete", str(entry.get("id", "?")),
                f"missing {missing} — an unattributable asset cannot ship"))
    return findings


# ---------------------------------------------------------------- archival layer
#
# The rules themselves live in `workflow/archive.py` (#142) — this section only decides who hears
# about them, at what severity, and never restates a bound. One rule is the exception, and it is
# here by ruling rather than by taste (#148 fix round 1): comparing the declared records against
# the timeline needs a shot list, and only the gate holds one. That library's `Finding` is
# `(code, severity, message)` and spells a warning `warning`, while the gate's is
# `(severity, code, subject, message)` and spells it `warn`; every finding from there passes
# through `to_gate_finding` on its way into the report.

ARCHIVAL_LAYER = "archive"
# The ladder decides the severity of a mix finding; the library only ever reports the words.
MIX_SEVERITY_BY_RUNG = {"warn": "warn", "closed": "error"}
# The library spells a warning `warning` and the gate spells it `warn`; this table is the only
# place that knows both spellings, so a promotion there cannot arrive here as advice.
SEVERITY_BY_LIBRARY_WORD = {"error": "error", "warning": "warn", "warn": "warn"}


def to_gate_finding(found, subject, *, severity=None):
    """One archival-library finding, in the shape this gate prints.

    A severity word neither file defines is refused rather than defaulted: a blocker that arrives
    spelled wrongly and leaves as advice is an unlicensed shot on a master, and the report would
    say it had been judged.
    """
    word = found.severity if severity is None else severity
    mapped = SEVERITY_BY_LIBRARY_WORD.get(word)
    if mapped is None:
        raise ValueError(f"the archival rules reported severity {word!r}, which this gate has no "
                         "rung for; guessing one re-decides what blocks a build")
    return Finding(mapped, found.code, subject, found.message)


def archive_rung(contract, document) -> tuple[str, list[Finding]]:
    """The rung this episode is judged on, plus what its own record had to say.

    One place asks, so the metadata half and the mix half cannot be judged in different rungs. A
    record the library refuses becomes a finding instead of a traceback: the gate has to report
    the rest of the episode too.
    """
    try:
        mode, found = archive.resolve_mode(contract, document)
    except ValueError as exc:
        return (archive.profile(contract)["mode"],
                [error("archive_opt_out_invalid", EPISODE_DOCUMENT, str(exc))])
    return mode, [to_gate_finding(f, EPISODE_DOCUMENT) for f in found]


def archival_records(episode: Path, contract: dict) -> dict:
    """The declared layer, or nothing when the declaration cannot be read.

    `check_archive_metadata` reports that failure; a pixel check restating it would name a second
    file for one fault and send the operator to the wrong one.
    """
    try:
        return archive.records(episode, contract, required=False)
    except ValueError:
        return {}


def check_archive_metadata(episode: Path, contract: dict, document: dict,
                           shots: list[Shot]) -> list[Finding]:
    """The deterministic half of the layer, at the severity the contract puts metadata on.

    A validator's own sentence is quoted, not paraphrased — those messages were written to be read
    by whoever has to fix the row. Absence of the layer *from the timeline* is not a finding here:
    the mix rule owns that judgement, and one fact from two checks is two facts a reader can
    negotiate with.

    What *is* judged here is the declared book against the presented film, in both directions, and
    that comparison can only live in the gate: `workflow/archive.py::records()` has no timeline,
    and its signature is shared by the assembler and by three test modules. The path it closes is
    the stale clip — the assembler resolves an archival shot by name, so a clip left on disk from
    an earlier build cuts in whether or not `archive.json` still records it, and a gate reading
    only the declared layer would call that master clean.
    """
    _, findings = archive_rung(contract, document)
    declared = archive.paths(contract)
    try:
        archive.ledger(episode, contract)
    except ValueError as exc:
        # `records()` reads the ledger too, so a bad row surfaces in both calls; the ledger check
        # goes first and stops there, because nothing about a shot can be judged from a file that
        # does not load — including which shots it claims to cover.
        return findings + [error("archive_ledger_invalid", declared["ledger_filename"], str(exc))]
    try:
        records = archive.records(episode, contract, required=False)
    except ValueError as exc:
        return findings + [error("archive_records_invalid", declared["records_filename"],
                                 str(exc))]

    # Both files loaded, so the book can be read against the film. Neither loop has anything to
    # say about a timeline that presents no archival layer, which is why a 3D-only episode cannot
    # move its counts here.
    archival_names = {shot.name for shot in shots if shot.kind == ARCHIVAL_LAYER}
    for shot in shots:
        if shot.kind == ARCHIVAL_LAYER and shot.name not in records:
            findings.append(error(
                "archive_shot_without_record", shot.name,
                f"{shot.name} is on the timeline in the archival layer and "
                f"{declared['records_filename']} holds no record for it, so the film puts "
                "footage on screen whose rights nobody has stated. Write its record in that "
                "file, keyed by exactly this shot name, citing a `licence` row that exists in "
                f"{declared['ledger_filename']} — the clip is probably still on disk from an "
                "earlier build, and an unlicensed shot is the one finding this gate cannot be "
                "argued past."))
    for name in sorted(set(records) - archival_names):
        findings.append(error(
            "archive_record_without_shot", name,
            f"{declared['records_filename']} records {name} and the timeline carries no "
            "archival shot of that name, so the book describes footage that is not in this "
            "film. Either the shot was cut and its record has to be deleted with it, or the "
            "record points at the wrong name and the rights it states belong to a different "
            "shot. A record nobody can match is not a harmless spare: it is a claim about this "
            "master that this master cannot honour."))
    return findings


def mix_shots(shots: list[Shot]) -> list[dict]:
    """The gate's timeline in the shape `mix_findings` reads: layer, start, seconds.

    `kind` is the layer and `duration` is the seconds. The unit is what the mix is a share of, so
    a crossed-over field prints a wrong number rather than a wrong name — which is why a test adds
    the seconds by hand and expects to see exactly those quoted back.
    """
    return [{"layer": shot.kind, "start": shot.start, "seconds": shot.duration} for shot in shots]


def check_archive_mix(shots: list[Shot], contract: dict, document: dict) -> list[Finding]:
    """What the profile owes this film, at the severity its rung decides.

    The numbers in the text are the library's own: this function neither computes a share nor
    re-derives the acts, it only says whether the same sentence advises or refuses.
    """
    rung, _ = archive_rung(contract, document)
    if rung not in MIX_SEVERITY_BY_RUNG:
        return []           # `off` judges nothing, which is the whole meaning of the rung
    try:
        found = archive.mix_findings(mix_shots(shots), contract, mode=rung)
    except ValueError as exc:
        return [error("archive_mix_unmeasurable", "timeline", str(exc))]
    return [to_gate_finding(f, "archival mix", severity=MIX_SEVERITY_BY_RUNG[rung])
            for f in found]


def check_archival_rhythm(shots: list[Shot], contract: dict) -> list[Finding]:
    """The two-four-six second test, measured on the clock the film actually ships with.

    `shot_lengths.json` is per *beat* and rounded up to whole seconds, so judging a six second
    ceiling against it fails shots no viewer ever saw held that long; the timeline's float is the
    honest number. The comparison is made on the rounded value the message prints, so a finding
    never quotes a length that does not breach the bound it names.
    """
    ceiling = float(contract["archive"]["archive_rhythm"]["max_archival_shot_seconds"])
    findings = []
    for shot in shots:
        if shot.kind != ARCHIVAL_LAYER or round(shot.duration, 1) <= ceiling:
            continue
        findings.append(warn(
            "archival_shot_long", shot.name,
            f"{shot.id} holds the archival layer for {shot.duration:.1f}s against the contract's "
            f"{ceiling:.1f}s ceiling — past that length the removal test applies: mute it and cut "
            "it, and if nothing is lost it was padding. Measured on the narration clock, not on "
            "shot_lengths.json, which is per beat and already rounded up. This stays advice until "
            "the first archival episode's measured distribution calibrates it; that distribution "
            "is what promotes it, and `archive_rhythm.archival_share_status` says the figure is "
            "ours until retention data says otherwise"))
    return findings


GATE_SEVERITIES = ("error", "warn")


def severity_from(policy: str, *, rule: str) -> str:
    """The severity word the contract's enforcement policy declares, refused if it is neither.

    `archive.enforcement_policy` is the block that decides whether a rule blocks the build or only
    advises, so a gate that hardcoded "error" here would be restating a decision the contract owns -
    and one that silently downgraded an unknown word to a warning would turn a blocker into a line
    nobody reads.
    """
    word = str(policy).split()[0]
    if word not in GATE_SEVERITIES:
        raise ValueError(f"archive.enforcement_policy.{rule} declares severity {word!r}, which this "
                         "gate has no way to emit")
    return word


def digest_of(path: Path) -> str:
    """sha256 of a file, streamed.

    Deliberately not imported from the tool that wrote the report: the thing that verifies a digest
    should not share a helper with the thing that produced it.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_shared_finish(episode: Path, graded: Path, contract: dict) -> list[Finding]:
    """Did the one transform that unifies the two visual styles actually run, and only once?

    `archive.cohesion.shared_finishing_pass` is what makes a 3D beat and an archival insert read as
    the same film: grain, bloom, vignette and contrast reach every source in a single pass over the
    assembled master. Nothing about that survives into the pixels in a way this gate could measure -
    a skipped pass and a hand-added second pass both produce a watchable file - so the check reads
    the report the pass writes and the digest it recorded there. This is metadata, and the contract
    puts metadata on the blocking side.
    """
    finish = contract["archive"]["cohesion"]["finish"]
    severity = severity_from(contract["archive"]["enforcement_policy"]["metadata_rules"],
                             rule="metadata_rules")
    emit = error if severity == "error" else warn
    report = Path(episode) / finish["report_filename"]
    if not report.is_file():
        return [emit("shared_finish_unreported", str(report),
                     "no finishing-pass report, so nothing proves the shared grade ran. A concat "
                     "that skipped look_pass and a master graded again by hand afterwards both look "
                     "clean to every pixel check in this gate, and both break the single transform "
                     "that makes the 3D and the archive read as one film")]
    body = json.loads(report.read_text(encoding="utf-8"))
    graded = Path(graded)
    if not graded.is_file():
        return [emit("shared_finish_missing", str(graded),
                     "the finishing pass reported a graded master that is not there")]

    findings = []
    declared = {name: float(value) for name, value in finish["strengths"].items()}
    used = {name: float(value) for name, value in (body.get("strengths") or {}).items()}
    off = sorted(name for name in declared if used.get(name) != declared[name])
    if off:
        detail = ", ".join(f"{name} at {used.get(name)} against the contract's {declared[name]}"
                           for name in off)
        findings.append(emit(
            "shared_finish_off_contract", str(report),
            f"the grade that ran is not the house grade: {detail}. One transform over every source "
            "is the mechanism the contract names for cohesion, so a strength this episode needed "
            "moved belongs in workflow/style.json, where the next episode inherits it"))
    if str(body.get("graded_sha256") or "") != digest_of(graded):
        findings.append(emit(
            "shared_finish_digest_moved", str(graded),
            "the graded master no longer matches the digest the finishing pass recorded, so "
            "something encoded it again after the single transform - the second grade pass the "
            "contract's rule 7 refuses, and the reason a per-shot grain injection would go unseen"))
    return findings


def blend_shots(shots: list[Shot], declared: dict) -> list[Shot]:
    """The archival shots the contract asks to sit *inside* the episode's grade."""
    return [shot for shot in shots
            if (declared.get(shot.name) or {}).get("treatment") == "blend"]


def measure_lumas(master: Path, shots: list[Shot]) -> dict[str, float]:
    """Mean greyscale of one frame at each shot's middle, on the 0-255 scale `frame` decodes to."""
    return {shot.id: round(float(frame(master, shot.start + shot.duration / 2).mean()), 2)
            for shot in shots}


def check_blend_luma(shots, declared, lumas, contract) -> list[Finding]:
    """A `blend` shot owes the episode an exposure match; a `keep_distinct` shot owes nothing.

    The exemption is the contract's, not a convenience: a photographic source keeps its own
    contrast because that is what signals provenance, and judging it against our band would
    punish the reason it is `keep_distinct`. An episode with no blend shot costs no frames.
    """
    wanted = blend_shots(shots, declared)
    if not wanted:
        return []
    centre = sum(lumas.values()) / len(lumas) if lumas else None
    window = (centre * float(contract["archive"]["cohesion"]["blend_luma_window_fraction"])
              if centre is not None else None)
    findings = []
    for shot in wanted:
        luma = lumas.get(shot.id)
        if centre is None or luma is None:
            findings.append(warn("blend_luma_unmeasured", shot.name,
                                 f"{shot.id} is declared `blend` and no frame of it was measured, "
                                 "so its exposure match is unverified"))
            continue
        if abs(luma - centre) > window:
            findings.append(warn(
                "blend_luma_off_band", shot.name,
                f"{shot.id} blends at mean luma {luma:.1f} against an episode band of "
                f"{centre:.1f} +-{window:.1f} — a blended source that sits outside the band reads "
                "as inserted rather than as part of the film. Warn until the archival episodes "
                "calibrate the window against their measured bands"))
    return findings


def archival_boundaries(shots: list[Shot]) -> list[tuple[Shot, Shot]]:
    """Cuts where the film crosses into or out of the archival layer.

    A 3D-to-3D cut is already watched by the bed and target rules; what nothing else sees is the
    step the mix takes when the *source* changes.
    """
    return [(left, right) for left, right in zip(shots, shots[1:])
            if (left.kind == ARCHIVAL_LAYER) != (right.kind == ARCHIVAL_LAYER)]


def segment_loudness(master: Path, start: float, seconds: float) -> float:
    """Integrated loudness of one slice of the master — the number a cut moves away from."""
    with tempfile.TemporaryDirectory() as td:
        clip = Path(td) / "slice.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0.0, start):.3f}",
                        "-t", f"{seconds:.3f}", "-i", str(master), "-map", "a:0",
                        "-c:a", "pcm_s16le", str(clip)], capture_output=True, check=True)
        return loudness(clip)[0]


def measure_cut_deltas(master: Path, pairs) -> dict[str, float]:
    """The LU the mix moves at each boundary, keyed `left->right`.

    A slice that yields no reading is left out rather than guessed at; the check that reads this
    dict reports the gap, the way the motion rule reports an unmeasured shot.
    """
    deltas = {}
    for left, right in pairs:
        try:
            before = segment_loudness(master, right.start - CUT_WINDOW, CUT_WINDOW)
            after = segment_loudness(master, right.start, CUT_WINDOW)
        except (ValueError, subprocess.CalledProcessError):
            continue
        deltas[f"{left.id}->{right.id}"] = after - before
    return deltas


def check_cut_loudness(pairs, deltas, contract) -> list[Finding]:
    """Does the mix survive the cut into and out of a source?"""
    bound = float(contract["archive"]["cohesion"]["loudness_delta_across_cuts_max_lu"])
    findings = []
    for left, right in pairs:
        delta = deltas.get(f"{left.id}->{right.id}")
        subject = f"{left.name} | {right.name}"
        if delta is None:
            findings.append(warn("cut_loudness_unmeasured", subject,
                                 f"the cut into {right.id} at {right.start:.1f}s could not be "
                                 "measured on either side, so the step in the mix there is "
                                 "unverified"))
            continue
        if abs(delta) > bound:
            findings.append(warn(
                "cut_loudness_jump", subject,
                f"the mix moves {delta:+.1f} LU across the archival boundary at "
                f"{right.start:.1f}s ({left.kind} to {right.kind}), over the {bound:.1f} LU the "
                "contract allows a source change — an editor's level ride, not a re-render. Warn "
                "until the archival episodes' measured deltas calibrate the bound"))
    return findings


# ---------------------------------------------------------------- orchestration

def measure_cuts(master: Path) -> list[float]:
    """Cut times in seconds, found by ffmpeg's scene detector the way the references were measured."""
    run_ = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(master), "-an",
                           "-vf", "scale=320:-2,scdet=threshold=10:sc_pass=0", "-f", "null", "-"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [float(m) for m in re.findall(r"lavfi\.scd\.time: ([0-9.]+)", run_.stderr)]


def check_cut_rhythm(cuts: list[float], duration: float, contract: dict) -> list[Finding]:
    """Uniform cutting reads as slides; the reference films mix quick montage with long held moves."""
    rule = contract["rhythm"]["cuts"]
    bounds = [0.0] + sorted(cuts) + [duration]
    lengths = [b - a for a, b in zip(bounds, bounds[1:]) if b - a > 0.2]
    if len(lengths) < 3:
        return []
    findings = []
    median = statistics.median(lengths)
    if median > rule["median_max_seconds"]:
        findings.append(error("cut_rhythm_slow", "master",
                              f"the median shot runs {median:.1f}s (reference films 1.5-3.3s, at most "
                              f"{rule['median_max_seconds']}s): the film cuts at one even pace, which reads as slides"))
    short = sum(x < rule["short_seconds"] for x in lengths) / len(lengths)
    if short < rule["short_share_min"]:
        findings.append(error("cut_rhythm_no_montage", "master",
                              f"{short:.0%} of shots are under {rule['short_seconds']}s (reference films 17-51%, at least "
                              f"{rule['short_share_min']:.0%}): no quick montage anywhere"))
    if max(lengths) < rule["held_shot_min_seconds"]:
        findings.append(error("cut_rhythm_no_hold", "master",
                              f"the longest shot is {max(lengths):.1f}s (reference films 53s and more, at least "
                              f"{rule['held_shot_min_seconds']:.0f}s): nothing is explained in one held, moving shot"))
    return findings


def known_cuts(episode: Path) -> list[float] | None:
    """The cuts the edit was built with (beat changes and every planned shot change), read off
    the storyboard by tools/sound_design.py; None when the episode has no storyboard.
    A cut-list episode's cuts are its shots' starts, exactly as the cut was resolved."""
    cut = resolved_cut(episode)
    if cut is not None:
        return [s["start"] for s in cut["shots"][1:]]
    if not (Path(episode) / "storyboard.json").exists():
        return None
    import sound_design
    return [t for t, _ in sound_design.plan_events(episode)["cuts"]]


def check_cut_detection(detected: list[float], known: list[float] | None, duration: float,
                        contract: dict) -> list[Finding]:
    """The rhythm gate reads the detector, the way the reference films were measured. On a dark,
    slowly lit master the detector misses cuts (33 of 47 on ask-chatgpt's first story cut), so its
    reading is set against the edit we know: how many known cuts it found, and the rhythm of the
    known edit itself. Advice only; the gate stays on the detector for comparability."""
    rule = contract["rhythm"]["cuts"]
    if not known or not detected:
        return []
    findings = []
    # Where the picture sits against the voice: the edit's cuts are on the narration clock, the
    # detector's are on the picture's. Their offset, third by third, is the A/V sync of the film.
    near = [(k, min(detected, key=lambda d: abs(d - k)) - k) for k in known]
    near = [(k, off) for k, off in near if abs(off) < 1.0]
    bound = rule["sync_offset_max_seconds"]
    span = max(k for k in known) or 1.0
    for part in range(3):
        offs = [off for k, off in near if part * span / 3 <= k < (part + 1) * span / 3 + (part == 2)]
        if len(offs) >= 5 and abs(statistics.median(offs)) > bound:
            findings.append(error("picture_out_of_sync", f"{part * span / 3:.0f}-{(part + 1) * span / 3:.0f}s",
                                  f"the cuts land {statistics.median(offs):+.2f}s from where the edit put them "
                                  f"(median of {len(offs)}; at most {bound}s): picture and voice have drifted apart"))
    tol = rule["known_cut_match_seconds"]
    found = sum(any(abs(d - k) <= tol for d in detected) for k in known)
    recall = found / len(known)
    bounds = [0.0] + sorted(known) + [duration]
    lengths = [b - a for a, b in zip(bounds, bounds[1:]) if b - a > 0.2]
    median = statistics.median(lengths) if lengths else 0.0
    short = sum(x < rule["short_seconds"] for x in lengths) / max(1, len(lengths))
    summary = (f"the detector found {found} of the {len(known)} cuts in the edit ({recall:.0%}); the edit itself "
               f"has a median shot of {median:.1f}s, {short:.0%} under {rule['short_seconds']}s and a longest "
               f"shot of {max(lengths, default=0):.1f}s")
    if recall < rule["detector_recall_min"]:
        findings.append(warn("cut_detector_misses", "master", summary + " — the rhythm reading above undercounts "
                             "cuts; trust the edit's numbers and look at the dark or slow transitions it missed"))
    elif rule.get("report_known_rhythm"):
        findings.append(warn("cut_rhythm_known", "master", summary))
    return findings


def shot_frames(master: Path, cuts: list[float], duration: float, width=320, height=180):
    """[(middle_s, gray frame 0..1)] for every shot at least 0.6 s long, in one decode at 2 fps."""
    fps = 2
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(master), "-vf", f"fps={fps},scale={width}:{height}",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, height, width).astype(np.float32) / 255.0
    bounds = [0.0] + sorted(cuts) + [duration]
    return [((a + b) / 2, frames[min(len(frames) - 1, int((a + b) / 2 * fps))])
            for a, b in zip(bounds, bounds[1:]) if b - a >= 0.6 and len(frames)]


def check_empty_shots(frames, contract) -> list[Finding]:
    """Shots with almost nothing in them: the share of the picture carrying an edge (a luminance
    step over `edge_step`) is under `edge_share_min`. On ask-chatgpt v4 the median shot had 11%
    and the ones a reviewer called empty (a black screen, a phone alone in the dark) had under 2%.
    Advice until other episodes calibrate it."""
    rule = contract["qc"]["empty_shots"]
    findings = []
    for t, f in frames:
        gy, gx = np.gradient(f)
        share = float((np.hypot(gx, gy) > rule["edge_step"]).mean())
        if share < rule["edge_share_min"]:
            findings.append(warn("empty_shot", f"{t:.1f}s",
                                 f"the shot around {t:.1f}s carries detail in {share:.1%} of the picture (at least "
                                 f"{rule['edge_share_min']:.0%}): frame something, or move closer"))
    return findings


def check_framing_reports(episode: Path) -> list[Finding]:
    """What the builder could not frame (renders/3d/<beat>.framing.json, written beside each
    render): labels whose part is off screen, text the frame edge cuts through. The builder knows
    the geometry exactly, so these are facts about the picture, reported here so they are read."""
    findings = []
    for path in sorted((Path(episode) / "renders" / "3d").glob("*.framing.json")):
        beat = path.name[:-len(".framing.json")]
        if not (path.with_name(f"{beat}.mp4")).exists():
            continue
        for line in json.loads(path.read_text(encoding="utf-8")):
            findings.append(warn("framing", beat, line))
    return findings


def run(episode: Path, master: Path, contract: dict | None = None,
        motions: dict[str, float] | None = None, measure: bool = True) -> list[Finding]:
    """Every check, in the order an operator would want to read the failures."""
    contract = contract or style_contract(ROOT)
    episode = Path(episode)
    master = Path(master)
    if not master.is_file():
        return [error("master_missing", str(master), "no such file — nothing to judge")]

    streams = probe(master)
    manifest = json.loads((episode / "vo/manifest.json").read_text(encoding="utf-8"))
    expected = manifest["totalSamples"] / manifest["sampleRate"]

    shots_path = episode / ("cut.resolved.json" if (episode / "cut.json").is_file() else "shots.json")
    if not shots_path.is_file():
        return [error("shot_map_missing", str(shots_path),
                      "the assembler has not published a shot map, so no scene can be judged")]
    shots = load_timeline(episode)
    document = read_episode_document(episode) if (episode / EPISODE_DOCUMENT).is_file() else {}

    findings = []
    findings += check_coverage(shots, manifest_ids(episode), contract)
    findings += check_canvas(streams["width"], streams["height"], streams["fps"], contract)
    findings += check_streams(streams, contract)
    findings += check_duration(streams["duration"], expected, contract)
    findings += check_captions(streams["subtitle_streams"], contract)
    findings += check_audio_format(streams["audio_channels"], streams["audio_sample_rate"], contract)
    findings += check_licence_entries(licence_entries(episode), contract)
    findings += check_long_shots(shots, contract)
    findings += check_archive_metadata(episode, contract, document, shots)
    findings += check_archive_mix(shots, contract, document)
    findings += check_archival_rhythm(shots, contract)
    findings += check_shared_finish(episode, graded_path(episode), contract)
    findings += check_framing_reports(episode)

    if streams["audio_streams"]:
        integrated, peak, lra = loudness(master)
        findings += check_loudness(integrated, peak, contract)
        findings += check_music_bed(momentary_floor(master),
                                    narration_floor(episode, contract), contract)

    if measure:
        motions = measure_motions(master, shots)
        findings += check_static_holds(shots, motions, contract)
        findings += check_slow_shots(shots, motions, contract)
        detected = measure_cuts(master)
        findings += check_cut_rhythm(detected, streams["duration"], contract)
        known = known_cuts(episode)
        findings += check_cut_detection(detected, known, streams["duration"], contract)
        findings += check_empty_shots(shot_frames(master, known or detected, streams["duration"]), contract)
        hook_window = contract["rhythm"]["hook_max_seconds"]
        findings += check_hook(motion(master, 0.5, min(hook_window, streams["duration"] - 1.0)),
                               contract)
        # The pixel half only decodes frames when the film actually carries the layer, so a
        # 3D-only episode like Artemis II pays nothing for a rule it cannot breach.
        declared = archival_records(episode, contract)
        if blend_shots(shots, declared):
            findings += check_blend_luma(shots, declared, measure_lumas(master, shots), contract)
        boundaries = archival_boundaries(shots)
        if boundaries:
            findings += check_cut_loudness(boundaries, measure_cut_deltas(master, boundaries),
                                           contract)
    else:
        findings += check_static_holds(shots, motions or {}, contract)

    return findings


def render(findings: list[Finding]) -> str:
    """The report an operator reads: failures first, each one naming the thing that failed."""
    lines = ["=== Episode QC ===", ""]
    for severity, label in (("error", "CONTRACT BREACHES"), ("warn", "ADVISORY")):
        group = [f for f in findings if f.severity == severity]
        lines.append(f"{label}: {len(group)}")
        for f in sorted(group, key=lambda x: (x.code, x.subject)):
            lines.append(f"  [{f.code}] {f.subject}: {f.message}")
        lines.append("")
    errors = sum(1 for f in findings if f.severity == "error")
    lines.append(f"verdict: {'FAIL' if errors else 'PASS'} "
                 f"({errors} error(s), {len(findings) - errors} warning(s))")
    return "\n".join(lines)


def main(argv=None, host=None) -> int:
    # Windows consoles default to a legacy codepage and turn the report's punctuation into '?'.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Judge a finished episode against workflow/style.json.")
    parser.add_argument("--episode", type=Path, required=True)
    parser.add_argument("--master", type=Path, required=True)
    parser.add_argument("--json", type=Path, help="also write the findings as JSON")
    parser.add_argument("--no-motion", action="store_true",
                        help="skip the pixel measurements (fast, but the rhythm rule goes unjudged)")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    args = parser.parse_args(argv)

    # A verdict this gate cannot complete is not a pass, so the qc stage refuses on a machine that
    # cannot run the intelligibility check - an episode "clean" only because the listening tool was
    # broken is precisely the slop this gate exists to keep out.
    refusal = stage_report(ROOT, "qc", host=host)
    if refusal:
        print(f"qc_episode: {refusal}", file=sys.stderr)
        return REFUSED

    findings = run(episode=args.episode, master=args.master, measure=not args.no_motion)
    print(render(findings), flush=True)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps([f.__dict__ for f in findings], indent=1), encoding="utf-8")
        print(f"\nwrote {len(findings)} findings to {args.json}", flush=True)

    errors = sum(1 for f in findings if f.severity == "error")
    warnings = len(findings) - errors
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
