"""ElevenLabs voices for narrate.py: same `create(text, voice, speed)` shape as the Kokoro engine.

A cast voice written `eleven:<voice_id>` (script/cast.json) is spoken by ElevenLabs; anything else
stays with local Kokoro. The key is read from the environment (ELEVENLABS_API_KEY) or from a
`.env.local` at the repository root (git-ignored), never from a file that is committed.

Every synthesis is cached under `<vo>/eleven-cache/<hash>.json` (audio + character alignment), keyed
by voice, model, settings and text: re-running the narration stage costs no credits for lines that
did not change. The character alignment ElevenLabs returns is kept next to each line's wav as
`<id>.align.json`; word_marks.py turns it into exact word and mouth timings.
"""
import base64
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=pcm_24000"
MODEL = "eleven_v3"            # expressive: reads [softly], [desperate] ... directions in the text
VOICE = re.compile(r"eleven:[A-Za-z0-9]{16,32}")
SETTINGS = {"stability": 0.5}  # v3 takes 0.0 (creative), 0.5 (natural) or 1.0 (robust)


def api_key():
    key = os.environ.get("ELEVENLABS_API_KEY")
    if key:
        return key
    env = ROOT / ".env.local"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("ELEVENLABS_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("ELEVENLABS_API_KEY is not set (environment or .env.local)")


class ElevenEngine:
    sample_rate = 24000

    def __init__(self, cache_dir, fetch=None, opener=None, sleep=time.sleep):
        self.cache = Path(cache_dir)
        self.fetch = fetch or self._fetch
        self.open = opener or urllib.request.urlopen
        self.sleep = sleep
        self.last_alignment = None

    def _fetch(self, voice_id, body):
        """One synthesis. A busy or failing server (429, 5xx) or a dropped connection is retried
        with a growing wait: a long episode is dozens of calls, and one hiccup used to stop the
        whole narration stage. Any other refusal (a bad key, a voice that does not exist, no
        credits) is not retried and is reported with ElevenLabs' own explanation."""
        data = json.dumps(body).encode("utf-8")
        headers = {"xi-api-key": api_key(), "Content-Type": "application/json"}
        for attempt in range(len(RETRY_WAITS) + 1):
            req = urllib.request.Request(API.format(voice=voice_id), data=data, headers=headers)
            try:
                with self.open(req, timeout=120) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = _error_detail(exc)
                if exc.code not in RETRY_STATUS or attempt == len(RETRY_WAITS):
                    raise RuntimeError(f"ElevenLabs refused the line (HTTP {exc.code}): {detail}") from None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                if attempt == len(RETRY_WAITS):
                    raise RuntimeError(f"ElevenLabs could not be reached: {exc}") from None
            self.sleep(RETRY_WAITS[attempt])

    def create(self, text, voice, speed=1.0):
        voice_id = voice.split(":", 1)[1]
        body = {"text": text, "model_id": MODEL, "voice_settings": dict(SETTINGS)}
        if speed != 1.0:                 # ElevenLabs honours 0.7-1.2; 1.0 stays out so old caches still hit
            body["voice_settings"]["speed"] = min(1.2, max(0.7, float(speed)))
        h = hashlib.sha1(json.dumps([voice_id, body], sort_keys=True).encode("utf-8")).hexdigest()[:20]
        path = self.cache / f"{h}.json"
        data = None
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data["audio_base64"]
            except (ValueError, KeyError, TypeError):
                data = None          # a damaged cache entry from an older run: fetch the line again
        if data is None:
            data = self.fetch(voice_id, body)
            self.cache.mkdir(parents=True, exist_ok=True)
            # written whole or not at all: a half-written cache file (a crash, a full disk) would
            # otherwise fail every later run on its JSON instead of fetching the line again
            partial = path.with_name(f"{path.name}.{os.getpid()}.tmp")
            partial.write_text(json.dumps(data), encoding="utf-8")
            os.replace(partial, path)
        pcm = numpy.frombuffer(base64.b64decode(data["audio_base64"]), dtype="<i2").astype(numpy.float32) / 32767.0
        pcm, self.last_alignment = tighten(pcm, data.get("alignment"), self.sample_rate)
        return pcm, self.sample_rate


RETRY_STATUS = {429, 500, 502, 503, 504}
RETRY_WAITS = (2, 5, 15, 30)   # s before each retry


def _error_detail(exc):
    """ElevenLabs' own sentence for a refusal ({"detail": {"message": ...}}), else the HTTP reason."""
    try:
        body = json.loads(exc.read().decode("utf-8", "replace"))
        detail = body.get("detail", body)
        if isinstance(detail, dict):
            detail = detail.get("message") or detail.get("status") or json.dumps(detail)
        return str(detail)[:300]
    except Exception:
        return str(exc.reason)


MAX_PAUSE = 0.4    # s: a longer silence inside a line is cut down to this (v3 drags its [pause]s)
EDGE = (0.05, 0.12)  # s kept before the first and after the last sound
SILENT_DB = -45.0


def tighten(pcm, alignment, rate, max_pause=MAX_PAUSE, edge=EDGE):
    """Shorten long silences and trim the edges; the character alignment is moved to match, so word and
    mouth marks stay exact. Returns (pcm, alignment)."""
    hop = int(rate * 0.01)
    n = len(pcm) // hop
    if n < 3:
        return pcm, alignment
    rms = numpy.sqrt(numpy.mean(pcm[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    loud = 20 * numpy.log10(rms) > SILENT_DB
    if not loud.any():
        return pcm, alignment
    first, last = int(numpy.argmax(loud)), int(n - 1 - numpy.argmax(loud[::-1]))
    cuts = []                                  # (start_s, end_s) of audio removed
    lead = first * hop / rate - edge[0]
    if lead > 0:
        cuts.append((0.0, lead))
    i = first
    while i <= last:
        if not loud[i]:
            j = i
            while j <= last and not loud[j]:
                j += 1
            gap = (j - i) * hop / rate
            if gap > max_pause:
                mid = (i * hop / rate + j * hop / rate) / 2
                cuts.append((mid - (gap - max_pause) / 2, mid + (gap - max_pause) / 2))
            i = j
        else:
            i += 1
    tail = (last + 1) * hop / rate + edge[1]
    total = len(pcm) / rate
    if tail < total:
        cuts.append((tail, total))
    if not cuts:
        return pcm, alignment
    keep, at = [], 0
    for a, b in cuts:
        keep.append(pcm[at:int(a * rate)])
        at = int(b * rate)
    keep.append(pcm[at:])
    out = numpy.concatenate(keep)

    def move(t):
        shift = 0.0
        for a, b in cuts:
            if t >= b:
                shift += b - a
            elif t > a:
                shift += t - a
        return round(max(0.0, t - shift), 3)

    if alignment:
        alignment = dict(alignment,
                         character_start_times_seconds=[move(t) for t in alignment["character_start_times_seconds"]],
                         character_end_times_seconds=[move(t) for t in alignment["character_end_times_seconds"]])
    return out, alignment


def word_marks(text, alignment):
    """[(word, start, end)] for `text.split()` from ElevenLabs' character alignment."""
    chars = alignment["characters"]
    starts, ends = alignment["character_start_times_seconds"], alignment["character_end_times_seconds"]
    said = "".join(chars)
    out, pos = [], 0
    for w in text.split():
        i = said.find(w, pos)
        if i < 0:
            i = pos
        if not chars:
            break
        i = min(i, len(chars) - 1)  # more words than the alignment placed: the rest sit at the end
        j = max(i, min(len(chars), i + len(w)) - 1)
        out.append((w, round(starts[i], 3), round(max(ends[j], starts[i] + 0.02), 3)))
        pos = j + 1
    return out


def phones(alignment):
    """[(letter, start, end)]: letters stand in for phonemes (lip_sync maps m/b/p to closed, a to open).
    A [direction] is not spoken, so its characters are left out."""
    out, inside = [], False
    for c, a, b in zip(alignment["characters"], alignment["character_start_times_seconds"],
                       alignment["character_end_times_seconds"]):
        if c == "[":
            inside = True
        if not inside:
            out.append((c.lower(), round(a, 3), round(b, 3)))
        if c == "]":
            inside = False
    return out
