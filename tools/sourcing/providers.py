"""Search adapters for the archival providers the style contract enables.

Before this rewrite the module held one function per provider, each spelling out its own endpoint
URL, its own query and limit parameter names, and the rights fields it happened to trust. That is
exactly the shape `workflow/style.json` exists to replace: `archive.sourcing.providers` now carries
the endpoint, the parameter names, the declared field list, the etiquette and the evidence fields in
priority order, so adding or dropping an archive is an edit to the contract and not an edit here.
The stock-photo provider this module used to call by name is gone rather than configured: it needed
a credential, which this machine does not store, and a bought-in image is not archival evidence.

What stays in this file is mechanical: build the query string from the declared parameters, send it
through the shared transport (retry ladder, spacing, cache, contract User-Agent), and normalise each
returned document through the declared `item_fields` and `url_templates`.

Two deliberate gaps, both so a second copy of the policy never exists:

* **No rights verdict.** A candidate carries `evidence` — the contract-named fields in priority
  order with the raw value each one actually held — and the accept/refuse decision belongs to
  `tools/sourcing/rights.py`. `search()` therefore does not call `transport.check_payload`: a
  search that finds nothing has to stay an empty list, and the caller that turns a payload into a
  verdict is the one that can tell «our query was wrong» apart from «no such footage exists», via
  `check_payload(payload, provider_entry(name), what=...)`.
* **No credential on any path.** Nothing here reads the environment, and every request is built by
  `transport.build_request`, which takes no header argument at all.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.sourcing import transport  # noqa: E402
from tools.sourcing.download import _open_url  # noqa: E402

DEFAULT_LIMIT = 5
NONCOMMERCIAL_REFUSAL = "noncommercial"

# The stock manifest's own vocabulary (see `manifest.KINDS`) — a different question from the
# contract's `form_by_value`, which answers "clip or still" for the timeline. The keys here are
# provider media-type *values*; the field they came from is read through `item_fields`, so neither
# a provider nor a field name is spelled in this file.
KIND_BY_MEDIA_TYPE = {
    "audio": "music",
    "image": "photo",
    "movies": "video",
    "text": "screenshot",
    "texts": "screenshot",
    "video": "video",
    "web": "screenshot",
}
DEFAULT_KIND = "photo"

_STATE = transport.RateState()
_CONTRACT = None


class ProviderUnavailable(ValueError):
    """The contract does not carry this provider, or carries it switched off.

    Refused by name rather than routed to a default, because a dispatcher that falls back searches
    an archive nobody approved and hands the results back as if the approved one had said them.
    """


def _contract(contract):
    """The caller's contract, or the house one — read at call time, never at import."""
    global _CONTRACT
    if contract is not None:
        return contract
    if _CONTRACT is None:
        from workflow.config import style_contract

        _CONTRACT = style_contract(ROOT)
    return _CONTRACT


def provider_entry(name, *, contract=None) -> dict:
    """`archive.sourcing.providers[name]`, refused by name when it is absent or disabled."""
    providers = _contract(contract)["archive"]["sourcing"]["providers"]
    entry = providers.get(str(name))
    if entry is None:
        raise ProviderUnavailable(f"{name} is not a provider in archive.sourcing; the contract "
                                  f"offers {sorted(providers)}")
    if not entry.get("enabled", False):
        raise ProviderUnavailable(f"{name} is listed in archive.sourcing with enabled false, so "
                                  f"the style contract has taken it out of the run")
    return entry


def search_url(name, query, limit=DEFAULT_LIMIT, *, contract=None) -> str:
    """The declared endpoint plus the declared parameters, with nothing invented here."""
    block = _contract(contract)
    entry = provider_entry(name, contract=block)
    parameters = dict(entry.get("search_params", {}))
    parameters[entry["query_param"]] = str(query)
    parameters[entry["limit_param"]] = str(limit)
    declared_fields = [str(field) for field in entry.get("fields", [])]
    if entry.get("fields_param") and declared_fields:
        parameters[entry["fields_param"]] = declared_fields
    policy = transport.transport_policy(block)
    if entry.get("sends_maxlag"):
        parameters[policy["maxlag_parameter"]] = str(policy["maxlag_value"])
    return f"{entry['search_endpoint']}?{urlencode(parameters, doseq=True)}"


def search(name, query, *, limit=DEFAULT_LIMIT, opener=_open_url, contract=None,
           episode_dir=None, retrieval_date=None, state=None, sleep=time.sleep,
           monotonic=time.monotonic, rng=random.random) -> list[dict]:
    """One query, one provider, normalised candidates — cache-first when a run is named.

    `episode_dir` together with `retrieval_date` is what makes an overnight re-run cost no network:
    the key is host, url and date — the trio `transport.cache_key_fields` names — and `transport`
    owns where that lands. The spacing between calls to one host rides on the shared `RateState`, so
    a hundred items for one topic queue instead of stampeding, which is what answers a Commons load
    over roughly one request a second with a 429.
    """
    block = _contract(contract)
    entry = provider_entry(name, contract=block)
    policy = transport.transport_policy(block)
    url = search_url(name, query, limit, contract=block)
    stamp = str(retrieval_date) if retrieval_date else ""
    cached = episode_dir is not None and bool(stamp)
    payload = transport.read_cache(episode_dir, policy, url, stamp) if cached else None
    if payload is None:
        payload = _open_json(_request(url, block), opener=opener, contract=block, state=state,
                             min_interval_seconds=float(entry.get("min_interval_seconds", 0.0)),
                             sleep=sleep, monotonic=monotonic, rng=rng)
        if cached:
            transport.write_cache(episode_dir, policy, url, stamp, payload)
    return parse(name, payload, contract=block)


def parse(name, payload, *, contract=None) -> list[dict]:
    """Normalise one raw search payload into candidates, reading only contract-named fields."""
    entry = provider_entry(name, contract=contract)
    return [candidate(name, document, entry)
            for document in transport.docs_of(payload, entry)
            if isinstance(document, dict)]


def candidate(name, document, entry) -> dict:
    """The row shape the manifest and the purchase list already expect, filled from the contract.

    Every value is pulled through `item_fields` / `url_templates` / `evidence_fields`, so this is
    the same code for all three archives; only the data beside it differs.
    """
    fields = entry.get("item_fields", {})
    asset_id = _text(_read(document, entry, fields.get("asset_id")))
    placeholders = {"asset_id": asset_id,
                    "title": _text(_read(document, entry, fields.get("title")))}
    url = (_located(document, entry, "page_url", placeholders)
           or _located(document, entry, "file_url", placeholders))
    preview = _located(document, entry, "preview_url", placeholders) or url
    evidence = evidence_of(document, entry)
    licence = evidence[0]["raw_value"] if evidence else ""
    media_type = _text(_read(document, entry, fields.get("mediatype"))).casefold()
    return {
        "provider": str(name),
        "asset_id": asset_id,
        "url": url,
        "preview_url": preview,
        "kind": KIND_BY_MEDIA_TYPE.get(media_type, DEFAULT_KIND),
        "evidence": evidence,
        "license_review": {
            # `required` keeps its old meaning — somebody has to look at this before it ships. The
            # rights *verdict* is rights.py's, and it reads `evidence`, not this annotation.
            "required": True,
            "name": licence or "Unspecified",
            "url": licence if _is_url(licence) else "",
            "attribution": _attribution(document, entry),
            "noncommercial": _refusal_of(licence, entry) == NONCOMMERCIAL_REFUSAL,
        },
    }


def evidence_of(document, entry) -> list[dict]:
    """Each ranked rights field with the value it actually carried, in the contract's priority order.

    A field that came back empty stays absent rather than padded: a refusal has to name the paths
    that were searched, and an invented value here is the one a verdict would then trust.
    """
    container = str(entry.get("evidence_read_path") or "")
    rows = []
    for field in sorted(entry.get("evidence_fields", []), key=lambda item: item.get("priority", 0)):
        path = str(field.get("path") or "")
        value = _text(_read(document, entry, path, base=_nested(document, container)))
        if not value:
            continue
        rows.append({
            "field_path": f"{container}.{path}" if container else path,
            "raw_value": value,
            "priority": field.get("priority"),
        })
    return rows


def _nested(document, path):
    node = transport.walk(document, str(path or ""))
    return node if isinstance(node, (dict, list)) else None


def _read(document, entry, path, *, base=None):
    """Follow a contract path from wherever that path lives.

    `item_fields` paths are document-relative for Internet Archive and NASA. Commons nests its
    metadata under `imageinfo.0`, so the same contract writes both `imageinfo.0.descriptionurl` —
    read from the document — and `extmetadata.Artist.value` — read from the node its
    `evidence_read_path` points inside. Every candidate root is tried: the caller's, the document,
    the evidence container, the container's parent.
    """
    if not path:
        return None
    path = str(path)
    container = str(entry.get("evidence_read_path") or "")
    above = container.rsplit(".", 1)[0] if "." in container else ""
    for node in (base, document, _nested(document, container), _nested(document, above)):
        if isinstance(node, (dict, list)):
            value = transport.walk(node, path)
            if value is not None:
                return value
    return None


def _located(document, entry, key, placeholders) -> str:
    """One URL-ish item field: a `url_templates` placeholder, or a plain path through the payload."""
    path = str(entry.get("item_fields", {}).get(key) or "")
    if not path:
        return ""
    template = entry.get("url_templates", {}).get(path)
    if template is not None:
        return _expand(str(template), placeholders)
    return _text(_read(document, entry, path))


def _expand(template: str, placeholders: dict) -> str:
    try:
        return template.format(**placeholders)
    except KeyError as missing:
        raise ValueError(f"an archive.sourcing url_template fills {missing}, which no item field "
                         f"supplies") from None


def _attribution(document, entry) -> str:
    fields = entry.get("item_fields", {})
    return (_text(_read(document, entry, fields.get("attribution")))
            or _text(_read(document, entry, fields.get("attribution_fallback"))))


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _text(value) -> str:
    """Provider metadata as plain text: markup-wrapped, a `{"value": ...}` cell, or a list."""
    if isinstance(value, dict):
        value = value.get("value", "")
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(item) for item in value)
    parser = _TextParser()
    parser.feed(str(value or ""))
    return unescape("".join(parser.parts)).strip()


def _is_url(value) -> bool:
    return urlsplit(str(value)).scheme in {"http", "https"}


def _squash(value) -> str:
    """A licence string as the contract's rules see it: casefolded, unpunctuated, schemeless.

    `https://creativecommons.org/licenses/by-nc-sa/2.0/` and `CC BY-NC-SA 2.0` have to satisfy one
    rule, so the rule's own `value` is squashed the same way rather than compared character for
    character — which is what lets the contract keep writing its rules as prefixes.
    """
    text = re.sub(r"[^0-9a-z]", "", str(value or "").casefold())
    return re.sub(r"\Ahttps?", "", text)


def _matched_rule(value, rules):
    """The first declared rule whose `match` kind hits this value: prefix, exact, contains, token."""
    text = str(value or "").casefold()
    squashed = _squash(text)
    for rule in rules or []:
        needle = str(rule.get("value") or "")
        if not needle:
            continue
        kind = str(rule.get("match") or "")
        squashed_needle = _squash(needle)
        if kind == "prefix" and squashed.startswith(squashed_needle):
            return rule
        if kind == "exact" and squashed == squashed_needle:
            return rule
        if kind == "contains" and squashed_needle in squashed:
            return rule
        if kind == "token" and re.search(rf"(?<![0-9a-z]){re.escape(needle.casefold())}(?![0-9a-z])",
                                         text):
            return rule
    return None


def _refusal_of(value, entry) -> str:
    """The refusal reason the contract's own rules attach to a licence string, or an empty one.

    Only the legacy `noncommercial` annotation reads this here; the basis ladder is `rights.py`,
    which runs the same `basis_rules` over the whole evidence list and gets the verdict.
    """
    rule = _matched_rule(value, entry.get("basis_rules"))
    return str(rule.get("refusal") or "") if rule else ""


def _request(url, contract=None, *, accept="application/json"):
    """Every request is a transport-built one: the contract's User-Agent, and no header argument."""
    return transport.build_request(url, _contract(contract), accept=accept)


def _open_json(request, opener=_open_url, *, contract=None, state=None,
               min_interval_seconds=0.0, sleep=time.sleep, monotonic=time.monotonic,
               rng=random.random):
    """Fetch one JSON document through the shared ladder, so a 429 is a wait and not a crash.

    The clock, the sleeper and the jitter source are arguments for the same reason they are in
    `transport`: a test measures the declared policy instead of spending wall time on it.
    """
    block = _contract(contract)
    timeout = int(transport.transport_policy(block)["timeout_seconds"])

    def attempt():
        response = opener(request, timeout=timeout)
        try:
            final_url = response.geturl() if hasattr(response, "geturl") else request.full_url
            if urlsplit(final_url).scheme not in {"http", "https"}:
                raise ValueError("provider redirected to a non-HTTP(S) URL")
            return json.loads(response.read().decode("utf-8"))
        finally:
            close = getattr(response, "close", None)
            if close is not None:
                close()

    return transport.retry_call(attempt, contract=block, channel="json",
                                host=transport.host_of(request.full_url),
                                state=_STATE if state is None else state,
                                min_interval_seconds=float(min_interval_seconds), sleep=sleep,
                                monotonic=monotonic, rng=rng)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Search the archival providers the style contract enables, without credentials.")
    parser.add_argument("provider", help="a key of archive.sourcing.providers in the style contract")
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--episode-dir", help="cache the raw response under this episode directory")
    parser.add_argument("--retrieval-date", help="ISO date the cache key is stamped with")
    args = parser.parse_args(argv)
    try:
        results = search(args.provider, args.query, limit=args.limit,
                         episode_dir=args.episode_dir, retrieval_date=args.retrieval_date)
    except ProviderUnavailable as error:
        print(error, file=sys.stderr)
        return 2
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
