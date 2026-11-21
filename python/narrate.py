"""Offline English narration through local Kokoro ONNX.

Validates a data-only request, synthesizes one 24 kHz mono PCM WAV per
utterance, and writes manifest.json whose timings come from the audio arrays.
"""

import argparse
import json
import math
import os
import re
import sys
import tempfile
import wave
from pathlib import Path

import numpy

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.capabilities import REFUSED, stage_report  # noqa: E402


SAMPLE_RATE = 24000
SAMPLE_WIDTH = 2
MAX_TEXT_CHARS = 5000
SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
RESERVED_ID = re.compile(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]", re.IGNORECASE)
ENGLISH_VOICE = re.compile(r"[ab][fm]_[a-z0-9_]{1,31}|eleven:[A-Za-z0-9]{16,32}")   # Kokoro English, or ElevenLabs


class EngineError(RuntimeError):
    """The synthesis engine returned audio this adapter cannot honour."""


def validate_request(value: dict) -> dict:
    if not isinstance(value, dict) or not {"voice", "speed", "utterances"} <= value.keys():
        raise ValueError("Request must contain voice, speed and utterances")
    voice = value["voice"]
    if not isinstance(voice, str) or not ENGLISH_VOICE.fullmatch(voice):
        raise ValueError("Voice must be an English Kokoro voice ID or eleven:<voice_id>")
    speed = value["speed"]
    wrong_type = type(speed) not in (int, float)
    if wrong_type or (isinstance(speed, float) and not math.isfinite(speed)) or not 0.5 <= speed <= 2.0:
        raise ValueError("Speed must be a finite number between 0.5 and 2.0")
    utterances = value["utterances"]
    if not isinstance(utterances, list) or not utterances:
        raise ValueError("Request must contain at least one utterance")
    seen = set()
    for utterance in utterances:
        if not isinstance(utterance, dict):
            raise ValueError("Each utterance must be an object")
        identity = utterance.get("id")
        if not isinstance(identity, str) or not SAFE_ID.fullmatch(identity):
            raise ValueError("Utterance IDs must be safe filenames of 1 to 64 characters")
        if RESERVED_ID.fullmatch(identity):
            raise ValueError("Utterance ID is a reserved Windows filename")
        if identity.casefold() in seen:
            raise ValueError("Utterance IDs must be unique, ignoring case")
        seen.add(identity.casefold())
        text = utterance.get("text")
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT_CHARS:
            raise ValueError(f"Utterance text must contain 1 to {MAX_TEXT_CHARS} characters")
        if any(ord(char) < 32 and char not in "\t\n\r" for char in text):
            raise ValueError("Utterance text contains control characters")
        # optional per-line voice (a character speaking), speaker and a respelt text for synthesis only
        own = utterance.get("voice")
        if own is not None and (not isinstance(own, str) or not ENGLISH_VOICE.fullmatch(own)):
            raise ValueError(f"Utterance {identity!r}: voice must be an English Kokoro voice ID")
        speaker = utterance.get("speaker")
        if speaker is not None and (not isinstance(speaker, str) or not SAFE_ID.fullmatch(speaker)):
            raise ValueError(f"Utterance {identity!r}: speaker must be a safe id")
        mode = utterance.get("mode")
        if mode is not None and mode not in ("say", "thought"):
            raise ValueError(f"Utterance {identity!r}: mode must be 'say' or 'thought'")
        own_speed = utterance.get("speed")
        if own_speed is not None and (type(own_speed) not in (int, float) or not 0.7 <= own_speed <= 1.2):
            raise ValueError(f"Utterance {identity!r}: speed must be a number from 0.7 to 1.2")
        spoken = utterance.get("spoken")
        if spoken is not None:
            if not isinstance(spoken, str) or not spoken.strip() or len(spoken) > MAX_TEXT_CHARS:
                raise ValueError(f"Utterance {identity!r}: spoken text must contain 1 to {MAX_TEXT_CHARS} characters")
            # a local voice's respelling must keep the word count (its word marks are matched by
            # position); an ElevenLabs line may carry [directions], which its alignment skips
            if not voice_of(value, utterance).startswith("eleven:") and len(spoken.split()) != len(text.split()):
                raise ValueError(f"Utterance {identity!r}: spoken text must respell word for word")
    return value


def voice_of(value: dict, utterance: dict) -> str:
    """The voice a line is spoken in: its own, else the episode's narrator voice."""
    return utterance.get("voice") or value["voice"]


def build_manifest(voice: str, chunks: list[dict]) -> dict:
    utterances = []
    total = 0
    for chunk in chunks:
        end = total + chunk["samples"]
        utterances.append({**chunk, "startSample": total, "endSample": end})
        total = end
    return {"sampleRate": SAMPLE_RATE, "voice": voice, "utterances": utterances, "totalSamples": total}


def to_pcm16(audio) -> bytes:
    flat = numpy.asarray(audio, dtype=numpy.float32).reshape(-1)
    scaled = numpy.clip(flat, -1.0, 1.0) * 32767.0
    return numpy.rint(scaled).astype("<i2").tobytes()


def write_wav(path: Path, audio) -> int:
    pcm = to_pcm16(audio)
    frames = len(pcm) // SAMPLE_WIDTH
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with wave.open(str(temporary), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(SAMPLE_WIDTH)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(pcm)
    os.replace(temporary, path)
    return frames


def synthesize(request: dict, output_dir, engine) -> dict:
    value = validate_request(request)
    output_dir = Path(output_dir)
    installed = getattr(engine, "voices", None)
    if installed is not None:
        for voice in [value["voice"]] + [u["voice"] for u in value["utterances"] if u.get("voice")]:
            if voice not in installed and not voice.startswith("eleven:"):
                raise ValueError(f"Voice {voice!r} is not installed in the engine")
    engine_rate = getattr(engine, "sample_rate", SAMPLE_RATE)
    if engine_rate != SAMPLE_RATE:
        raise EngineError(f"Engine reports {engine_rate} Hz but {SAMPLE_RATE} Hz is required")

    chunks = []
    output_dir.mkdir(parents=True, exist_ok=True)
    cloud = None
    for utterance in value["utterances"]:
        identity, text = utterance["id"], utterance["text"]
        voice = voice_of(value, utterance)
        speaker = engine
        if voice.startswith("eleven:"):
            if cloud is None:
                cloud = eleven_engine(output_dir / "eleven-cache")
            speaker = cloud
        try:
            audio, sample_rate = speaker.create(utterance.get("spoken") or text, voice,
                                                speed=utterance.get("speed", value["speed"]))
        except (ValueError, EngineError):
            raise
        except Exception as error:
            raise EngineError(f"Synthesis failed for {identity!r}: {error}") from error
        if sample_rate != SAMPLE_RATE:
            raise EngineError(f"Utterance {identity!r} returned {sample_rate} Hz, expected {SAMPLE_RATE} Hz")
        if len(audio) == 0:
            raise EngineError(f"Utterance {identity!r} returned an empty waveform")
        filename = f"{identity}.wav"
        samples = write_wav(output_dir / filename, audio)
        align = output_dir / f"{identity}.align.json"
        if speaker is cloud and cloud is not None and cloud.last_alignment:
            align.write_text(json.dumps({"text": text, "alignment": cloud.last_alignment}), encoding="utf-8")
        elif align.exists():
            align.unlink()
        chunk = {"id": identity, "file": filename, "text": text, "samples": samples}
        if utterance.get("speaker"):
            chunk.update(speaker=utterance["speaker"], voice=voice, mode=utterance.get("mode", "say"))
        chunks.append(chunk)
    return build_manifest(value["voice"], chunks)


def eleven_engine(cache_dir):
    """The ElevenLabs engine (python/eleven.py); a seam tests replace."""
    import eleven
    return eleven.ElevenEngine(cache_dir)


def write_manifest(manifest: dict, path: Path) -> Path:
    temporary = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), prefix=".manifest-", suffix=".tmp", delete=False
    )
    try:
        json.dump(manifest, temporary, ensure_ascii=False, indent=2)
        temporary.write("\n")
        temporary.close()
        os.replace(temporary.name, path)
    except BaseException:
        temporary.close()
        os.unlink(temporary.name)
        raise
    return path


def load_engine(model_path: Path, voices_path: Path):
    from kokoro_onnx import Kokoro

    return Kokoro(str(model_path), str(voices_path))


def _require_asset(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"{label} file not found: {resolved}")
    return resolved


def main(argv=None, engine_factory=load_engine, host=None) -> int:
    parser = argparse.ArgumentParser(description="Synthesize English narration with local Kokoro ONNX.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--voices", required=True, type=Path)
    args = parser.parse_args(argv)

    # A 96-utterance batch is long enough to be worth refusing to start on a machine that cannot
    # finish it. The weights are checked for wholeness here, not just existence: `_require_asset`
    # below cannot tell a 325 MB model from a 4 KB stub, and a stub fails an hour in.
    refusal = stage_report(REPO_ROOT, "vo", host=host)
    if refusal:
        print(f"narrate: {refusal}", file=sys.stderr)
        return REFUSED

    try:
        request = json.loads(args.input.read_text(encoding="utf-8"))
    except OSError as error:
        print(f"narrate: cannot read request: {error}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as error:
        print(f"narrate: request is not valid JSON: {error}", file=sys.stderr)
        return 2
    try:
        validate_request(request)
    except ValueError as error:
        print(f"narrate: invalid request: {error}", file=sys.stderr)
        return 2

    try:
        model = _require_asset(args.model, "model")
        voices = _require_asset(args.voices, "voices")
    except FileNotFoundError as error:
        print(f"narrate: {error}", file=sys.stderr)
        return 3

    output = args.output.resolve()
    for label, path in (("model", model), ("voices", voices)):
        if output in path.parents:
            print(f"narrate: output directory must not contain the {label} asset: {output}", file=sys.stderr)
            return 2

    print(f"narrate: loading engine from {model}", file=sys.stderr)
    try:
        engine = engine_factory(model, voices)
        manifest = synthesize(request, output, engine)
    except ValueError as error:
        print(f"narrate: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"narrate: synthesis failed: {error}", file=sys.stderr)
        return 1

    path = write_manifest(manifest, output / "manifest.json")
    audio_seconds = manifest["totalSamples"] / SAMPLE_RATE
    print(
        f"narrate: wrote {len(manifest['utterances'])} utterances, "
        f"{manifest['totalSamples']} samples ({audio_seconds:.3f} s)",
        file=sys.stderr,
    )
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
