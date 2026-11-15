"""Bounded, atomic downloads that hand back the digest of the bytes that landed.

Before #149 this module digested every chunk it wrote (line 84) and then only *logged* the result
(line 97), so the ledger could record a checksum nobody had re-read and an asset that changed on the
way to disk stayed invisible. `download_binary` now returns the sha256 and writes it beside the file
under the suffix the contract names, and `read_digest` re-computes it on the way into the ledger —
the ledger records the bytes this machine holds, not the bytes a provider advertised.

The retry ladder, the User-Agent and the etiquette are all in `tools/sourcing/transport.py` now, so
a binary fetch and a metadata query share one policy instead of two stacks learning the same lesson
separately. Nothing here can carry a credential: the only header sent is the User-Agent, and the
redirect handler strips an `Authorization` the moment the origin changes.
"""

import hashlib
import io
import logging
import os
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.sourcing import transport  # noqa: E402

CHUNK_BYTES = 1024 * 1024
TIMEOUT_SECONDS = 60
DEFAULT_MAX_BYTES = 100 * 1024 * 1024
LOGGER = logging.getLogger(__name__)

_HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")
_CACHED_POLICY = None


def policy(contract=None) -> dict:
    """`archive.sourcing.transport`, read once rather than re-derived per download."""
    global _CACHED_POLICY
    if contract is None and _CACHED_POLICY is not None:
        return _CACHED_POLICY
    if contract is None:
        from workflow.config import style_contract
        contract = style_contract(ROOT)
    block = transport.transport_policy(contract)
    if contract is None:
        _CACHED_POLICY = block
    return block


def _require_http_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("only HTTP(S) download URLs are allowed")


def _origin(url):
    parsed = urlsplit(url)
    default_port = {"http": 80, "https": 443}.get(parsed.scheme.lower())
    port = parsed.port if parsed.port is not None else default_port
    return parsed.scheme.lower(), parsed.hostname, port


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _require_http_url(newurl)
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and _origin(req.full_url) != _origin(redirected.full_url):
            for header_map in (redirected.headers, redirected.unredirected_hdrs):
                for name in list(header_map):
                    if name.lower() == "authorization":
                        del header_map[name]
        return redirected


_SAFE_OPENER = build_opener(_SafeRedirectHandler())


def _open_url(request, timeout=TIMEOUT_SECONDS):
    return _SAFE_OPENER.open(request, timeout=timeout)


def sidecar_path(destination, transport_policy_block=None) -> Path:
    """The sibling file carrying the digest, named by the contract rather than by habit."""
    suffix = (transport_policy_block or policy())["sidecar_suffix"]
    return Path(str(Path(destination)) + suffix)


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_digest(destination, contract=None) -> str:
    """The digest of the bytes on disk, refusing a sidecar that no longer describes them.

    Called by the ingest step, so a file that changed between download and ledger is an error here
    rather than a wrong number three episodes later.
    """
    destination = Path(destination)
    sidecar = sidecar_path(destination, policy(contract))
    if not destination.is_file():
        raise ValueError(f"{destination} is not on disk, so its sha256 cannot be read")
    if not sidecar.is_file():
        raise ValueError(f"{sidecar} is missing; the sha256 sidecar is what makes a ledger "
                         "digest a verified fact rather than a claim")
    recorded = sidecar.read_text(encoding="utf-8").strip().casefold()
    if not _HEX64.match(recorded):
        raise ValueError(f"{sidecar} does not hold a sha256 hex digest, got {recorded!r}")
    actual = _sha256_of(destination)
    if actual != recorded:
        raise ValueError(f"{destination} no longer matches its recorded sha256: sidecar says "
                         f"{recorded}, the bytes say {actual}; the file changed after it landed")
    return actual


def digest_matches(destination, expected, contract=None) -> bool:
    """Compare a published digest against the bytes we hold. Never trust, always compare."""
    if not isinstance(expected, str) or not _HEX64.match(expected.strip().casefold()):
        return False
    try:
        return _sha256_of(Path(destination)) == expected.strip().casefold()
    except OSError:
        return False


def download_binary(
    url: str,
    destination: Path,
    opener=_open_url,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    contract=None,
    state=None,
    min_interval_seconds: float = 0.0,
    sleep=time.sleep,
    monotonic=time.monotonic,
    rng=random.random,
) -> str:
    """Download to a sibling partial file, move it atomically, return its sha256.

    Returns the digest rather than the path because the digest is the fact the ledger needs; the
    path is already an argument. The sidecar is written after the move, so a partial or aborted
    download leaves neither a destination nor a claim about one.
    """
    bounds = policy(contract)
    _require_http_url(url)
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer")
    destination = Path(destination)
    if os.path.lexists(destination):
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = Path(str(destination) + ".partial")
    sidecar = sidecar_path(destination, bounds)

    def attempt():
        partial.unlink(missing_ok=True)
        response = opener(url, timeout=int(bounds["timeout_seconds"]))
        if isinstance(response, (bytes, bytearray)):
            response = io.BytesIO(response)
        digest = hashlib.sha256()
        total = 0
        try:
            final_url = response.geturl() if hasattr(response, "geturl") else url
            _require_http_url(final_url)
            try:
                with partial.open("wb") as output:
                    while True:
                        chunk = response.read(CHUNK_BYTES)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes:
                            raise ValueError(f"download exceeds maximum of {max_bytes} bytes")
                        digest.update(chunk)
                        output.write(chunk)
                if os.path.lexists(destination):
                    raise FileExistsError(destination)
                os.replace(partial, destination)
            except BaseException:
                partial.unlink(missing_ok=True)
                raise
        finally:
            close = getattr(response, "close", None)
            if close is not None:
                close()
        return digest.hexdigest(), total

    hex_digest, total = transport.retry_call(
        attempt, contract=contract if contract is not None else {}, host=transport.host_of(url),
        channel="binary", state=state, min_interval_seconds=min_interval_seconds,
        sleep=sleep, monotonic=monotonic, rng=rng, policy=bounds)

    sidecar.write_text(hex_digest + "\n", encoding="utf-8")
    LOGGER.info("Downloaded %s (%d bytes, sha256=%s)", destination, total, hex_digest)
    return hex_digest
