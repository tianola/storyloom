"""Bounded, atomic downloads for sourced media."""

import hashlib
import io
import logging
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

CHUNK_BYTES = 1024 * 1024
TIMEOUT_SECONDS = 60
DEFAULT_MAX_BYTES = 100 * 1024 * 1024
LOGGER = logging.getLogger(__name__)


def _require_http_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("only HTTP(S) download URLs are allowed")


def download_binary(
    url: str,
    destination: Path,
    opener=urlopen,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Path:
    """Download to a sibling partial file and atomically move it after EOF."""
    _require_http_url(url)
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer")
    destination = Path(destination)
    if os.path.lexists(destination):
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = Path(str(destination) + ".partial")
    partial.unlink(missing_ok=True)

    response = opener(url, timeout=TIMEOUT_SECONDS)
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

    LOGGER.info("Downloaded %s (%d bytes, sha256=%s)", destination, total, digest.hexdigest())
    return destination
