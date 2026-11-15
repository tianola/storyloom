"""One home for "what does this audio actually measure at".

The assembler needs the number to build its delivery gain and the music bed needs the same number
to sit a stated distance under the voice. Both read ffmpeg's `loudnorm` first pass, so the parse
lives here once: two implementations of the same measurement is how a mix and a gate start
disagreeing about what finished means.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflow.config import style_contract  # noqa: E402

AUDIO = style_contract(ROOT)["audio"]


def _peak_target(audio=AUDIO):
    """Where the delivery chain aims the peak, which is under where the contract caps it.

    The ceiling is read off the *encoded* master: the Artemis II bed mix measured -25.29 LUFS with
    a -6.41 dBFS true peak, this filter landed the PCM at -14.00 LUFS / -1.00 dBFS — exactly on the
    ceiling, zero margin — and `aac -b:a 192k` moved it to -0.70 dBFS, which is the breach the gate
    reported. Lossy encoding overshoots inter-sample peaks, so aiming at the ceiling itself
    guarantees crossing it.
    """
    return audio["true_peak_max_dbfs"] - audio["encode_true_peak_headroom_db"]


def measure(audio_path, audio=AUDIO):
    """First pass of two-pass loudnorm: what this audio actually measures at.

    ffmpeg prints the measurement as a JSON object at the very end of the filter log, after
    thousands of per-frame lines, so the parse takes the *last* brace pair rather than the first.
    """
    probe_filter = (f"loudnorm=I={audio['integrated_lufs_target']}"
                    f":TP={_peak_target(audio)}:LRA={audio['loudness_range_lu']}"
                    ":print_format=json")
    proc = subprocess.run(["ffmpeg", "-v", "info", "-i", str(audio_path),
                           "-af", probe_filter, "-f", "null", "-"],
                          capture_output=True, text=True)
    log = proc.stderr
    if "}" not in log:
        raise ValueError(f"loudnorm printed no measurement for {audio_path}:\n{log[-800:]}")
    return json.loads(log[log.rindex("{"):log.rindex("}") + 1])


def loudnorm_filter(measured, audio=AUDIO):
    """The second pass: apply the gain that was measured, then land on the delivery rate.

    `linear=true` asks for one clean gain rather than a level that rides all the way through, so a
    narration bed with a 2.5 LU range comes up as a mix instead of being pumped. It is not a
    ceiling guard: with 11 LU of gain owed, ffmpeg reached the target by compressing and still
    parked the PCM right on TP, so the headroom in `_peak_target` is what keeps the encoded master
    under the contract. aresample comes last because loudnorm resamples internally to 192 kHz and
    leaves the stream there — a master built without this line ships at a rate nothing expects.
    """
    return (f"loudnorm=I={audio['integrated_lufs_target']}"
            f":TP={_peak_target(audio)}:LRA={audio['loudness_range_lu']}"
            f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
            f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
            f":offset={measured['target_offset']}:linear=true,"
            f"aresample={audio['sample_rate_min']}")
