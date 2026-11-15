"""One retry ladder, one etiquette rule, one cache — shared by the JSON and the binary opener.

Before #149 neither `_open_url` nor `_open_json` retried anything, so a 429 from Commons — which
the research measured at over roughly one request a second — was a crash rather than a wait, and
two independent transport stacks each had to be taught the same lesson separately. They now share
`retry_call`, which reads its ladder from `archive.sourcing.transport` and takes the clock, the
sleeper and the jitter source as arguments, so a test can measure the policy instead of waiting
for it.

The status semantics are the part worth stating: 429 and 503 are waits, 403 is a client bug
(on Commons a missing User-Agent), and 400 and 404 are our request being wrong about an API that
changed — the class that never improves on a fifth try, and the exact class that swallowed NASA's
`usage` filter and the deleted `/count` endpoint without anything appearing to break.

Nothing here can carry a credential. There is no `Authorization` path and no environment read,
because anonymous read is sufficient on all three hosts and a code path that *can* send a key is
the failure the operator is avoiding rather than the key itself.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TransportFailure(RuntimeError):
    """The network refused to cooperate; never a rights verdict in either direction."""


class TransientFailure(TransportFailure):
    """A transient status survived every declared attempt."""

    def __init__(self, host, code, attempts):
        super().__init__(f"{host} answered {code} on all {attempts} attempts")
        self.host, self.code, self.attempts = host, code, attempts


class RequestShapeError(TransportFailure):
    """The payload is empty in the way that means our query was wrong, not that footage is absent.

    A bad `fl[]` list and a genuinely empty collection both arrive as JSON with no docs. Reading
    the first as the second silences a corpus over a typo, which is why the two are different
    exception types and different refusal reasons in the report.
    """


def transport_policy(contract: dict) -> dict:
    return contract["archive"]["sourcing"]["transport"]


def user_agent(contract: dict) -> str:
    sourcing = contract["archive"]["sourcing"]
    agent = str(sourcing.get("user_agent", "")).strip()
    if not agent:
        raise ValueError("archive.sourcing.user_agent is empty; Commons answers 403 to a request "
                         "that does not say who is asking")
    return agent


def headers(contract: dict) -> dict:
    return {"Accept": "application/json", "User-Agent": user_agent(contract)}


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").casefold()


class RateState:
    """Wall-clock spacing between successive calls to the same host.

    `serial_only` is the point: the ladder is one archiver politely queueing, and the first call
    to a host buys no wait because there is nothing yet to be polite *about*.
    """

    def __init__(self, *, monotonic=time.monotonic):
        self.monotonic = monotonic
        self.last: dict[str, float] = {}

    def wait(self, host: str, seconds: float, sleep):
        if seconds <= 0:
            return
        last = self.last.get(host)
        if last is not None:
            remaining = seconds - (self.monotonic() - last)
            if remaining > 0:
                sleep(remaining)
        self.last[host] = self.monotonic()


def retry_call(invoke, *, contract, host, channel="json", state=None, min_interval_seconds=0.0,
               sleep=time.sleep, monotonic=time.monotonic, rng=random.random, policy=None):
    """Call `invoke()` until it succeeds, the ladder runs out, or the status says stop.

    `max_retries` counts the waits *after* the first try, and the backoff list is exactly that
    long — a rung nobody can reach is a bound nobody measures, which `test_sourcing_transport`
    checks. Every delay is stretched by at most `jitter_fraction` so a hundred items for one topic
    do not all come back on the same second.
    """
    policy = policy or transport_policy(contract)
    backoff = [float(value) for value in policy["backoff_seconds"]]
    retries = int(policy["max_retries"])
    if len(backoff) != retries:
        raise ValueError(f"transport.backoff_seconds has {len(backoff)} rungs but "
                         f"max_retries is {retries}; the two are one promise stated twice")
    transient = {int(code) for code in policy["transient_status"]}
    never = {int(code) for code in policy["never_retry_status"]}
    non_transient = {int(code) for code in policy["non_transient_status"]}
    jitter = float(policy["jitter_fraction"])
    header = policy["retry_after_header"]
    attempts = 0
    while True:
        attempts += 1
        if state is not None:
            state.wait(host, float(min_interval_seconds), sleep)
        try:
            return invoke()
        except HTTPError as error:
            code = int(error.code)
            if code in never or code in non_transient or code not in transient:
                raise
            if attempts > retries:
                raise TransientFailure(host, code, attempts) from None
            delay = _retry_after(error, header)
            if delay is None:
                delay = backoff[attempts - 1] * (1.0 + jitter * float(rng()))
            sleep(delay)
        except URLError as error:
            if attempts > retries:
                raise TransportFailure(f"{host} never answered: {error.reason}") from None
            sleep(backoff[attempts - 1] * (1.0 + jitter * float(rng())))


def _retry_after(error: HTTPError, header: str):
    raw = error.headers.get(header) if error.headers else None
    if raw is None:
        return None
    try:
        seconds = float(str(raw).strip())
    except ValueError:
        return None
    return max(0.0, seconds)


def build_request(url: str, contract: dict, *, accept: str = "application/json") -> Request:
    """A GET with the contract's User-Agent and nothing else — no credential header exists here."""
    return Request(url, headers={"Accept": accept, "User-Agent": user_agent(contract)})


def cache_path(episode_dir, policy: dict, url: str, retrieval_date: str) -> Path:
    """The raw response, keyed by exactly the three fields the contract names."""
    key = f"{host_of(url)}|{url}|{retrieval_date}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    directory = Path(episode_dir) / policy["cache_dir"] / host_of(url)
    return directory / f"{digest}.json"


def read_cache(episode_dir, policy: dict, url: str, retrieval_date: str):
    if episode_dir is None:
        return None
    path = cache_path(episode_dir, policy, url, retrieval_date)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_cache(episode_dir, policy: dict, url: str, retrieval_date: str, payload) -> None:
    if episode_dir is None:
        return
    path = cache_path(episode_dir, policy, url, retrieval_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def check_payload(payload, provider: dict, *, what: str) -> dict:
    """Empty because the request was wrong, and empty because there is nothing there, apart.

    §1.2's self-check: a malformed field list echoes back a malformed `fl[]` and a doc set with
    every requested key missing. Trusting a rights verdict over that would refuse an entire corpus
    for a query-string typo.
    """
    if not isinstance(payload, dict):
        raise RequestShapeError(f"{what}: expected a JSON object, got {type(payload).__name__}")
    probe = provider.get("payload_probe_path")
    if probe and walk(payload, probe) is None:
        raise RequestShapeError(f"{what}: the payload carries no {probe!r}, so the request shape "
                                f"is wrong and no rights conclusion can be drawn from it")
    echo_path = provider.get("field_echo_path")
    if echo_path:
        echo = walk(payload, echo_path)
        wanted = [str(field) for field in provider.get("fields", [])]
        if isinstance(echo, str) and wanted:
            missing = [field for field in wanted if field not in echo]
            if missing and docs_of(payload, provider):
                raise RequestShapeError(f"{what}: the server echoed {echo!r}, which omits "
                                        f"{missing}; the requested fields were never returned, so "
                                        "their absence is not evidence about the item")
    return payload


def docs_of(payload: dict, provider: dict) -> list:
    docs = walk(payload, provider["docs_path"])
    if isinstance(docs, dict):
        docs = list(docs.values())
    return list(docs or [])


def walk(document, path: str):
    """Follow a contract-named dot path through dicts and list indices.

    A path segment of the form `key=value` selects the first list entry whose `key` matches, which
    is how NASA's `links.rel=canonical.href` is addressed without a provider-specific parser.
    """
    current = document
    for segment in str(path or "").split("."):
        if segment == "":
            continue
        if current is None:
            return None
        if "=" in segment and not segment.startswith("http"):
            key, wanted = segment.split("=", 1)
            entries = current if isinstance(current, list) else [current]
            found = next((entry for entry in entries
                          if isinstance(entry, dict) and str(entry.get(key)) == wanted), None)
            current = found
            continue
        if isinstance(current, list):
            try:
                current = current[int(segment)]
            except (ValueError, IndexError):
                return None
        elif isinstance(current, dict):
            current = current.get(segment)
        else:
            return None
    return current
