"""The contract's declared entry point: find the footage, land the bytes, write the row.

`workflow/style.json` → `archive.sourcing.entry_point` names this file, and the block beside it
owns every endpoint, field name, number and refusal reason the run needs. What lives here is the
seam between them: read the episode's archival shots, ask the enabled archives for footage, put
the bytes on disk with the sha256 sidecar `transport.sidecar_suffix` names, and append one rights
row and one record per shot — the two files `workflow/archive.py` validates and `qc_episode.py`
judges.

The ownership split is the one #149b states: **providers = facts about a document, rights = the
verdict, archive_source = the row and the file.** Three consequences are deliberate, and all three
are delegations rather than copies, because the #149a review finding F3 was that a second engine
over the contract's rules is worse than one that is wrong:

* the request, the retry ladder and the cache are `transport`'s;
* the search, the document normalisation and the path resolution are `providers`' — this file uses
  its `_located`, `_read`, `_text` and `_open_json` instead of re-typing them;
* the licence-string matcher is looked up in whichever sourcing module carries it today
  (`rights.matched_rule` once #149b lands, `providers._matched_rule` until then).

**Rights verdicts are bypassed for this build, by instruction.** The verdict ladder the contract
declares — `gates`, `contradictions`, `restrictions_gate`, `allowed_bases`, and the publication-year
floor *as a rights rule* — is not evaluated here, and every candidate the archives return is
downloaded. Two things survive that instruction, and neither one is a verdict:

1. `rights_basis` is a closed enum in `archive.rights.rights_basis_enum`, and
   `workflow/archive.ledger()` refuses a row that cannot name one. The value is therefore read from
   the same contract data a verdict would read — `accept_from_source` first, then `basis_rules`
   over the ranked evidence — as a *name*, not a judgement. A matched rule that carries a refusal
   instead of a basis names no basis, so the row is unwritable and the item is skipped with that
   contract reason attached: the schema declining a row, not this tool rendering a verdict.
2. The two ledger rules the validator enforces on every row — `publication_year_floor` for the
   bases it names, and the `obligations_required_for_bases` duty — are checked before anything is
   committed, because a row they refuse cannot be written at all and D-043 says a partial ledger is
   worse than no ledger.

D-043 is the shape of the whole run. The three conditions in
`archive.sourcing.refuse_before_download_when` stop everything before a request is made, the merged
pair of files is validated in a staging directory before either real file is touched, and if the
final round trip through `workflow/episode.archive_sources()` fails both files go back to their
previous bytes. `archive.sourcing.report_filename` is written either way: the accepted and refused
split, with every field path searched, is evidence and outlives the run.

Bytes already on disk are re-used rather than re-fetched (`download_binary` refuses an existing
destination, and `read_digest` re-verifies the sidecar), so an overnight re-run of a half-filled
episode costs no network for the shots that already landed. A file whose row was refused stays on
disk and is reported as `downloaded_not_committed` — an asset with no rights row is not a ledger
entry, and the next run either gives it one or refuses it again.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.sourcing import providers, transport  # noqa: E402
from tools.sourcing.download import (DEFAULT_MAX_BYTES, _open_url, download_binary,  # noqa: E402
                                     read_digest)
from tools.sourcing.providers import ProviderUnavailable  # noqa: E402
from tools.sourcing.transport import RequestShapeError, TransportFailure  # noqa: E402
from workflow import episode as episode_files  # noqa: E402
from workflow.archive import ledger as read_ledger  # noqa: E402
from workflow.archive import paths as archive_paths  # noqa: E402
from workflow.archive import records as read_records  # noqa: E402
from workflow.config import style_contract  # noqa: E402

#: A shot name becomes part of a file name, so anything that is not a name character is folded to
#: a separator. Episode data, not policy: no episode's shot names are spelled here.
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")

#: Substrings of the contract's own `refuse_before_download_when` entries, in the order the run
#: checks them. The reason a run reports is always the contract's full sentence, never this needle.
REFUSAL_NEEDLES = {"episode": "episode directory", "providers": "provider list",
                   "shots": "archive shot"}


class RefuseBeforeDownload(RuntimeError):
    """One of the contract's declared conditions, named in the contract's own words."""

    def __init__(self, condition: str, detail: str = ""):
        super().__init__(condition if not detail else f"{condition}: {detail}")
        self.condition, self.detail = condition, detail


class UnreadableLedger(RuntimeError):
    """The episode's existing archival files do not validate, so nothing may be appended to them."""


class UsageError(RuntimeError):
    """The caller asked for something the contract cannot answer, before any request was made."""


@dataclass
class Run:
    """Everything one sourcing run knows, so no helper has to re-derive the contract."""

    episode: Path
    contract: dict
    sourcing: dict
    usage: dict
    policy: dict
    paths: dict
    rights: dict
    provider_names: list
    query: str
    shot_queries: dict
    only: tuple
    limit: int
    retrieval_date: str
    purpose: str = ""
    carries: str = ""
    carries_defaulted: bool = False
    max_bytes: int = DEFAULT_MAX_BYTES
    dry_run: bool = False
    opener: object = _open_url
    binary_opener: object = _open_url
    prober: object = None
    state: object = None
    searched: list = field(default_factory=list)
    accepted: list = field(default_factory=list)
    refused: list = field(default_factory=list)
    repaired: list = field(default_factory=list)
    downloaded_not_committed: list = field(default_factory=list)

    def query_for(self, name: str) -> str:
        return self.shot_queries.get(name) or self.query


# --------------------------------------------------------------------------- contract readers

def _sourcing(contract: dict) -> dict:
    block = contract["archive"]["sourcing"]
    if not block.get("enabled", False):
        raise RefuseBeforeDownload(
            f"{str(block.get('entry_point') or 'the declared entry point')} is switched off: "
            "archive.sourcing.enabled is false, so the style contract has taken automatic "
            "sourcing out of the run")
    return block


def _conditions(contract: dict) -> list:
    """`refuse_before_download_when`, read without the enabled gate.

    Split from `_sourcing()` because the first of the three conditions is checked before the block
    is even known to be switched on, and a refusal has to be able to name itself.
    """
    return list(contract["archive"]["sourcing"]["refuse_before_download_when"])


def _declared_condition(contract: dict, needle: str) -> str:
    """The contract's own sentence for one refusal condition, refusing a needle it never states."""
    for text in _conditions(contract):
        if needle.casefold() in str(text).casefold():
            return str(text)
    raise ValueError(f"archive.sourcing.refuse_before_download_when states no condition about "
                     f"{needle!r}, and a refusal this file invents is one nobody can read back "
                     "out of the style contract")


def _reason(contract: dict, key: str) -> str:
    """A `refusal_reasons` key, checked against the contract so a typo cannot invent a reason."""
    reasons = _sourcing(contract)["refusal_reasons"]
    if key not in reasons:
        raise ValueError(f"{key!r} is not a key of archive.sourcing.refusal_reasons "
                         f"{sorted(reasons)}; the report states reasons the contract can explain")
    return key


def _refusal(run: Run, key: str, *, detail: str, field_paths=(), **extra) -> dict:
    return {"reason": _reason(run.contract, key), "detail": detail, "why": _reason(run.contract,
                                                                                   key),
            "searched_field_paths": list(field_paths), **extra}


def _archive_layer(contract: dict) -> str:
    """The declared visual layer whose records and rights ledger live under `archive.paths`.

    Not spelled here: the taxonomy is `episode_profile.mix.layers`, and the layer this tool fills is
    the one that owns a `paths` block — a fact about the contract rather than a name in code.
    """
    for layer in episode_files.layers(contract):
        block = contract.get(layer)
        if isinstance(block, dict) and isinstance(block.get("paths"), dict):
            return layer
    raise ValueError("no layer in archive.episode_profile.mix.layers owns a `paths` block, so "
                     "nothing states where its records and rights ledger live")


def _threshold(table, value: float, *, name: str) -> str:
    """The first `below`/`value` rung a number falls under — the contract's own step function.

    The rungs are ordered and each names the member of the contract's enum it applies, so changing
    the house threshold is an edit to `usage` and never to this file.
    """
    for rung in table or []:
        if value < float(rung["below"]):
            return str(rung["value"])
    raise ValueError(f"archive.sourcing.usage.{name} has no rung for {value}; the ladder has to "
                     "reach every measurement the archives can return")


def _licence_matcher():
    """`matched_rule`, wherever the sourcing toolkit keeps it this week.

    #149b moves it into `tools/sourcing/rights.py` as a public name. A copy here would be the
    second engine the #149a review already rejected, and would break the day the move lands.
    """
    try:
        from tools.sourcing import rights as rights_module
    except ImportError:
        rights_module = None
    for module, attribute in ((rights_module, "matched_rule"), (providers, "_matched_rule")):
        found = getattr(module, attribute, None) if module is not None else None
        if callable(found):
            return found
    raise UnreadableLedger("no sourcing module exposes the contract's basis_rules matcher, so no "
                           "rights_basis can be named from the archives' own fields")


# --------------------------------------------------------------------------- payload and fields

def _payload(run: Run, name: str, query: str):
    """The raw search response — what `check_payload` needs and `search()` discards.

    #149b (R1) adds `providers.fetch()` for exactly this. Until it exists the response is read back
    from the run's own cache, which is not a shortcut the contract disapproves of:
    `transport.cache_why` states that the cache is keyed by host, url and date so "the ledger can
    cite the exact raw response it decided on".
    """
    url = providers.search_url(name, query, run.limit, contract=run.contract)
    fetch = getattr(providers, "fetch", None)
    if callable(fetch):
        return fetch(name, query, limit=run.limit, opener=run.opener, contract=run.contract,
                     episode_dir=run.episode, retrieval_date=run.retrieval_date)
    providers.search(name, query, limit=run.limit, opener=run.opener, contract=run.contract,
                     episode_dir=run.episode, retrieval_date=run.retrieval_date, state=run.state)
    cached = transport.read_cache(run.episode, run.policy, url, run.retrieval_date)
    if cached is None:
        where = transport.cache_path(run.episode, run.policy, url, run.retrieval_date)
        raise TransportFailure(f"the cached response at {where} is not on disk, so the raw "
                               f"{name} answer that every search result has to be judged on "
                               f"cannot be read back")
    return cached


def _field(document: dict, entry: dict, key: str, placeholders: dict) -> str:
    """One `item_fields` value as plain text, resolved and flattened by the search client."""
    if not str(entry.get("item_fields", {}).get(key) or ""):
        return ""
    return providers._text(providers._located(document, entry, key, placeholders))


def _path_value(document: dict, entry: dict, path: str) -> str:
    """A contract-named dot path from the document, for the reader of `hints`."""
    if not str(path or ""):
        return ""
    return providers._text(providers._read(document, entry, path))


def _searched_field_paths(entry: dict) -> list:
    """Every evidence path the provider declares, filled or not, in declared priority order.

    `providers.evidence_of()` drops the blank ones, which is right for a candidate and wrong for a
    refusal: the contract's `no_recognized_basis` says the report names every field path searched,
    and a field that came back empty is the one a reader needs to see.
    """
    container = str(entry.get("evidence_read_path") or "")
    paths = []
    for declared in entry.get("evidence_fields") or []:
        path = str(declared.get("path") or "")
        if path:
            paths.append(f"{container}.{path}" if container else path)
    return paths


def _is_endpoint(value) -> bool:
    return bool(value) and urlsplit(str(value)).scheme in {"http", "https"}


def _is_file_url(value) -> bool:
    """An HTTP(S) URL whose last path segment carries an extension — a file, not a page."""
    if not _is_endpoint(value):
        return False
    return bool(PurePosixPath(urlsplit(str(value)).path).suffix)


def _media_url(run: Run, document: dict, entry: dict, candidate: dict, placeholders: dict) -> str:
    """The downloadable file behind an item, from `item_fields.file_url` and nothing invented.

    Two shapes exist in the contract. Wikimedia and NASA name the file itself, so the value is the
    download. Internet Archive names a metadata endpoint, so that endpoint is fetched and the first
    absolute file URL inside it is taken — a generic scan, because typing `files.0.name` would be
    the provider-specific parser the contract rewrite deleted. A provider that names neither leaves
    the ledger with no `file`, which is a `missing_field` refusal and not a guess.
    """
    value = _field(document, entry, "file_url", placeholders)
    if _is_file_url(value):
        return str(value)
    template = str(entry.get("detail_endpoint") or "")
    if template and _is_endpoint(value):
        found = _from_detail_endpoint(run, entry, template, placeholders)
        if found:
            return found
    return ""


def _from_detail_endpoint(run: Run, entry: dict, template: str, placeholders: dict) -> str:
    try:
        url = template.format(**placeholders)
    except (IndexError, KeyError) as missing:
        raise ValueError(f"an archive.sourcing detail_endpoint fills {missing}, which no item "
                         "field supplies") from None
    request = transport.build_request(url, run.contract)
    document = providers._open_json(request, opener=run.opener, contract=run.contract,
                                    state=run.state,
                                    min_interval_seconds=float(entry.get("min_interval_seconds",
                                                                         0.0)))
    return _first_file_url(document)


def _first_file_url(node) -> str:
    """The first absolute URL in a provider document that names a file.

    Deliberately shape-agnostic — no provider's field names appear — so the same scan reads every
    enabled archive's detail document.
    """
    found: list[str] = []

    def visit(current):
        if isinstance(current, dict):
            for value in current.values():
                visit(value)
        elif isinstance(current, (list, tuple)):
            for value in current:
                visit(value)
        elif isinstance(current, str) and _is_file_url(current):
            found.append(current)

    visit(node)
    return found[0]


# --------------------------------------------------------------------------- the basis, as data

def _basis_of(run: Run, entry: dict, evidence: list) -> dict:
    """Name the rights basis the archive's own fields state: no ladder, no gate, no invention.

    Returns `{"basis", "license", "field_path", "raw_value", "annotations"}`, or `{"refusal",
    "detail", "field_paths"}` when no basis can be named at all.
    """
    annotations = []
    accepted = entry.get("accept_from_source")
    if isinstance(accepted, dict) and str(accepted.get("basis") or ""):
        wanted = str(accepted.get("evidence_path") or "")
        row = next((item for item in evidence if _names(item["field_path"], wanted)), None)
        if row is not None:
            annotations.append({"annotation": "accepted_from_source",
                                "basis": str(accepted["basis"]),
                                "field_path": row["field_path"],
                                "why": str(accepted.get("why") or "the basis comes from who made "
                                         "the item, not from a field an uploader filled in")})
            return {"basis": str(accepted["basis"]), "license": str(accepted["basis"]),
                    "field_path": row["field_path"], "raw_value": row["raw_value"],
                    "annotations": annotations}

    match = _licence_matcher()
    refusal_seen = ""
    for row in evidence:
        rule = match(row["raw_value"], entry.get("basis_rules"))
        if not rule:
            continue
        if rule.get("basis"):
            return {"basis": str(rule["basis"]), "license": str(row["raw_value"]),
                    "field_path": row["field_path"], "raw_value": row["raw_value"],
                    "annotations": annotations}
        refusal_seen = refusal_seen or str(rule.get("refusal") or "")
    if refusal_seen:
        return {"refusal": refusal_seen,
                "detail": "the contract's own rule for this value states a refusal and no basis, "
                          "so rights_basis cannot be filled from it; the verdict ladder was not "
                          "run — this is the ledger schema declining the row",
                "field_paths": [row["field_path"] for row in evidence]}
    return {"refusal": "no_recognized_basis",
            "detail": "no declared evidence field carried a value any declared rule recognises",
            "field_paths": _searched_field_paths(entry)}


def _names(field_path: str, wanted: str) -> bool:
    return str(field_path) == wanted or str(field_path).endswith(f".{wanted}")


def _hint_annotations(run: Run, entry: dict, document: dict) -> list:
    """The contract's `hints` this document hits — recorded in the report, never gating.

    Only `hints` is read. `gates`, `contradictions` and `restrictions_gate` are the verdict, and
    the verdict is bypassed by instruction, so this file does not evaluate them at all; gating on a
    hint would be the invention the contract's own `why` already rejects.
    """
    hits = []
    for hint in entry.get("hints") or []:
        paths = hint.get("read")
        paths = list(paths) if isinstance(paths, (list, tuple)) else [paths]
        markers = [str(marker) for marker in hint.get("markers") or []]
        kind = str(hint.get("match") or "")
        for path in paths:
            value = _path_value(document, entry, path)
            if not value:
                continue
            for marker in markers:
                if not _marker_hit(kind, value, marker):
                    continue
                hits.append({"annotation": str(hint.get("annotation") or marker),
                             "field_path": str(path), "marker": marker, "raw_value": value,
                             "why": str(hint.get("why") or "a hint is annotated, never gated")})
                break
            if hits:
                break
    return hits


def _marker_hit(kind: str, value: str, marker: str) -> bool:
    """One `hints`/`match` kind against one value, in the search client's own normalisation.

    `providers._squash` is reused rather than restated: the contract's rule values are written to be
    read by it, and a second normaliser here would be a second engine over the same rules (#149a
    finding F3) that could disagree with the matcher on a scheme or a hyphen.
    """
    lowered, squashed = str(value).casefold(), providers._squash(value)
    needle = str(marker).casefold()
    if kind == "prefix":
        return squashed.startswith(providers._squash(needle))
    if kind == "contains":
        return providers._squash(needle) in squashed
    if kind == "exact":
        return squashed == providers._squash(needle)
    if kind == "token":
        return bool(re.search(rf"(?<![0-9a-z]){re.escape(needle)}(?![0-9a-z])", lowered))
    if kind == "truthy":
        return lowered not in {"", "false", "no", "none", "0"}
    return False


# --------------------------------------------------------------------------- measurement

def _measure(run: Run, path: Path) -> dict:
    """What the bytes actually are, probed through the ingest's own readers.

    Every number the row reports — rate, modulus, span, aspect — comes from here rather than from
    what the provider said about them, which is the same reason `download.read_digest` re-computes
    the checksum instead of quoting the archive.
    """
    if run.prober is None:
        from tools import archive_ingest

        run.prober = archive_ingest
    seconds = float(run.prober.probe_duration(path) or 0.0)
    rate = float(run.prober.probe_fps(path) or 0.0)
    ratio = run.prober.probe_ratio(path)
    return {"seconds": seconds, "rate": rate, "ratio": float(ratio) if ratio else None,
            "frames": seconds * rate if rate > 0 else 0.0}


def _form(run: Run, measured: dict) -> str:
    """clip or still, decided by counting the frames the file holds.

    `form_by_value` is not consulted: on Commons it maps `ns = 6` to `"auto"`, which is not a
    member of `archive_motion.form_enum` (#149a review finding F4, owned by #149d). A frame count
    answers the same question without a vocabulary table that cannot match the provider.
    """
    forms = run.contract["archive"]["archive_motion"]["form_enum"]
    frames = float(run.usage["frame_count_floor"])
    return str(forms[0] if measured["frames"] >= frames else forms[-1])


def _span(run: Run, form: str, measured: dict) -> float:
    """The seconds of the source this run intends to use, capped by what the file actually holds."""
    clip = str(run.contract["archive"]["archive_motion"]["form_enum"][0])
    budget = float(run.usage["clip_seconds"] if form == clip else run.usage["still_seconds"])
    return min(measured["seconds"], budget) if measured["seconds"] > 0 else budget


def _timecode(seconds: float, *, timebase: int) -> str:
    """A non-drop SMPTE label for a span measured from the first frame.

    `:` and never `;`: `workflow/archive.py` refuses drop-frame notation at an integral rate, this
    tool has no evidence about the 1.001 ratios, and the in-point of a source nobody has cut from
    yet is its first frame.
    """
    total = max(1, round(seconds * timebase))
    frames, ticks = total % timebase, total // timebase
    hours, remainder = divmod(ticks, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"


def _year(value: str):
    match = re.search(r"(1[5-9][0-9]{2}|20[0-9]{2})", str(value or ""))
    return int(match.group(1)) if match else None


# --------------------------------------------------------------------------- the row and record

def _next_ids(existing, record_id: dict):
    """`arch-NNN` continued from the highest id already in the ledger, then from this run.

    Continuing is what makes a second run extend the file instead of renumbering rows the timeline
    already cites — the `record_id.why` in the contract, in code.
    """
    prefix, width = str(record_id["prefix"]), int(record_id["width"])
    highest = 0
    for value in existing:
        tail = str(value)[len(prefix):]
        if str(value).startswith(prefix) and tail.isdigit():
            highest = max(highest, int(tail))
    counter = highest

    def supply():
        nonlocal counter
        counter += 1
        return f"{prefix}{counter:0{width}d}"

    return supply


def _fill(template, values: dict, *, name: str) -> str:
    try:
        return str(template).format(**values)
    except (IndexError, KeyError) as missing:
        raise ValueError(f"archive.sourcing.{name} fills {missing}, which this run does not "
                         "have") from None


def _purpose_of_use(run: Run, title: str, source_archive: str) -> str:
    """What the film says it is about, plus whose record this is — or a plain statement that the
    film has not said so yet.

    `purpose_of_use` is the one rights field that is an editorial claim rather than a provider fact,
    so the contract's `override` is the only way an argument reaches the row: `--purpose` wins, and
    what `--purpose` does not supply is filled from the episode's own document fields in the order
    `purpose.document_fields` names them.
    """
    purpose = run.sourcing["purpose"]
    if run.purpose:
        return run.purpose
    fields = list(purpose["document_fields"])
    document = episode_files.document(run.episode)
    stated = next((str(document[key]).strip() for key in fields
                   if str(document.get(key, "")).strip()), "")
    if not stated:
        stated = (f"no editorial purpose stated in {episode_files.EPISODE_DOCUMENT}: "
                  f"{', '.join(fields)} are all empty")
    clause = _fill(purpose["item_clause"], {"title": title, "source_archive": source_archive},
                   name="purpose.item_clause")
    return _fill(purpose["template"], {"slug": run.episode.name,
                                       "purpose_source": f"{stated} — {clause}"},
                 name="purpose.template")


def ledger_row(run: Run, *, ident: str, provider: str, entry: dict, candidate: dict, basis: dict,
               form: str, measured: dict, span: float, media_url: str, page_url: str, title: str,
               attribution: str, source_year: int, file_relative: str, transforms: list,
               obligations: list) -> dict:
    """One rights row: every field from the contract's data or from this run's measurements."""
    usage, rights = run.usage, run.rights
    clip = str(run.contract["archive"]["archive_motion"]["form_enum"][0])
    is_clip = form == clip and measured["rate"] > 0
    rate = measured["rate"] if is_clip else float(run.contract["canvas"]["fps"])
    timebase = max(1, math.ceil(rate))
    source_archive = str(entry["label"])
    values = {"source_archive": source_archive, "asset_id": candidate["asset_id"],
              "attribution": attribution, "title": title, "field_path": basis["field_path"],
              "raw_value": basis["raw_value"], "retrieved_date": run.retrieval_date}
    row = {
        "id": ident,
        "provider": provider,
        "license": basis["license"],
        "url": page_url or candidate["url"],
        "file": file_relative,
        "source_archive": source_archive,
        "rights_basis": basis["basis"],
        "credit_line": _fill(run.sourcing["credit_line_template"], values,
                             name="credit_line_template"),
        "retrieval_url": media_url,
        "retrieved_date": run.retrieval_date,
        "purpose_of_use": _purpose_of_use(run, title, source_archive),
        "third_party_rights": usage["defaults"]["third_party_rights"],
        "in_timecode": _timecode(0.0, timebase=timebase),
        "out_timecode": _timecode(span, timebase=timebase),
        "timebase": timebase,
        "source_frame_rate": round(rate, 6),
        "licence_version": _fill(run.sourcing["licence_version_template"], values,
                                 name="licence_version_template"),
        "obligations": list(obligations),
        "qc_watermark": bool(usage["defaults"]["qc_watermark"]),
        "derivative_transformations": list(transforms),
        "uploaded_as_is": False,
        "source_year": int(source_year),
    }
    unbudgeted = [name for name in rights["required_fields"] if name not in row]
    stale = [name for name in row if name not in rights["required_fields"]]
    if unbudgeted or stale:
        raise ValueError(f"the ledger row and archive.rights.required_fields disagree: "
                         f"{unbudgeted + stale}; the contract lists {list(rights['required_fields'])}")
    return row


def archive_record(run: Run, *, asset: str, ident: str, form: str, measured: dict, aspect: str,
                   carries: str) -> dict:
    """The `archive.json` half: what the shot is, keyed by shot name.

    `light_side` is left out on purpose. The contract allows an archival clip to be flipped to
    agree with the house key, and the flip is a falsification the moment the frame carries readable
    writing — which metadata cannot answer and `archive_ingest.mirror_decision` only asks about with
    a pixel test. Declaring a side here would be a claim about a frame nobody looked at.
    """
    motion = run.contract["archive"]["archive_motion"]
    record = {"asset": asset, "licence": ident, "form": form, "aspect": aspect,
              "treatment": str(run.usage["default_treatment"]), "carries": carries}
    if form == str(motion["form_enum"][0]):
        record["native_fps"] = round(measured["rate"], 6)
        # Declared for every clip, not only the ones outside the validator's rate tolerance: the
        # tolerance is `workflow/archive.py`'s bound and copying it here would be a second copy of
        # a number that is not in the contract at all.
        record["motion_mode"] = _threshold(run.usage["motion_mode_for_rate"], measured["rate"],
                                           name="motion_mode_for_rate")
    return record


def _schema_block(run: Run, row: dict, basis: dict, obligations: list, item: dict) -> dict:
    """The two ledger rules that bind whatever the verdict does, checked before a commit.

    These are not verdicts: `workflow/archive.ledger()` applies them to every row in the file, so a
    row that breaks one cannot be written, and D-043 would refuse the whole run for it. Catching
    them here keeps the refusal per item, with the field path that produced it.
    """
    bases, rights = str(row["rights_basis"]), run.rights
    floor = int(rights["publication_year_floor"])
    if bases in rights["publication_year_floor_for_bases"] and int(row["source_year"]) > floor:
        return _refusal(run, "publication_year_floor",
                        detail=f"{bases} with source_year {row['source_year']} is past the "
                               f"contract floor {floor}, so the row cannot be written and the "
                               "run does not get a partial ledger for it",
                        field_paths=[basis.get("field_path", "")], licence=row["id"], **item)
    if bases in rights["obligations_required_for_bases"] and not obligations:
        return _refusal(run, "missing_field",
                        detail=f"{bases} grants use only on terms and the provider declares no "
                               f"obligations_by_basis entry for it, so obligations cannot be "
                               "stated",
                        field_paths=[basis.get("field_path", "")], licence=row["id"], **item)
    return {}


# --------------------------------------------------------------------------- staging and commit

def _validate(run: Run, rows: list, records: dict) -> str:
    """Validate the merged pair in a staging directory; neither reader needs the media on disk.

    This is the acceptance proof of the task, run before the real files move: the same two
    functions `qc_episode.py` judges an episode with, over exactly the bytes about to be written.
    """
    ledger_name, records_name = run.paths["ledger_filename"], run.paths["records_filename"]
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp)
        for relative, body in ((ledger_name, rows), (records_name, records)):
            path = staging / PurePosixPath(str(relative))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        try:
            read_ledger(staging, run.contract)
            read_records(staging, run.contract)
        except ValueError as error:
            return str(error)
    return ""


def _write(path: Path, body) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _stored(run: Run, key: str, default):
    """The raw bytes of one archival file, for merging, apart from the validator's copy of it.

    `ledger()` hands back each row plus a derived `span_seconds` and `records()` each record plus a
    normalised `native_fps` — facts the readers compute, not fields the episode declared. Extending
    those dictionaries would write them back into the shipped files, so the validators decide
    whether appending is safe and the stored JSON is what actually gets extended.
    """
    path = run.episode / PurePosixPath(str(run.paths[key]))
    if not path.is_file():
        return default
    body = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(body, type(default)):
        raise UnreadableLedger(f"{path} holds {type(body).__name__}, not the "
                               f"{type(default).__name__} this file is defined as, so nothing "
                               "safe can be appended to it")
    return body


def commit(run: Run, existing_rows: list, existing_records: dict, new_rows: list,
           new_records: dict) -> dict:
    """Write both files or neither, then prove it with the validator the gate itself uses."""
    ledger_name = str(run.paths["ledger_filename"])
    records_name = str(run.paths["records_filename"])
    ledger_path = run.episode / PurePosixPath(ledger_name)
    records_path = run.episode / PurePosixPath(records_name)
    merged_records = dict(existing_records)
    merged_records.update(new_records)
    merged_rows = list(existing_rows) + list(new_rows)

    broken = _validate(run, merged_rows, merged_records)
    if broken:
        return {"committed": False,
                "why": f"the merged archival files do not validate, so neither was written: "
                       f"{broken}"}

    backups = {path: (path.read_bytes() if path.is_file() else None)
               for path in (ledger_path, records_path)}
    _write(ledger_path, merged_rows)
    _write(records_path, merged_records)
    try:
        filled = episode_files.archive_sources(run.episode, run.contract)
    except ValueError as error:
        for path, previous in backups.items():
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(previous)
        return {"committed": False,
                "why": f"workflow/episode.archive_sources() refused the episode this run left, so "
                       f"both files were restored to their previous bytes: {error}"}
    return {"committed": True, "round_trip": sorted(filled),
            "files": [ledger_name, records_name]}


# --------------------------------------------------------------------------- one candidate

def _resolve_candidate(run: Run, provider: str, entry: dict, document: dict, *, name: str, uids,
                       used_urls, supply_id, existing_rows, existing_records, new_rows,
                       new_records) -> dict:
    """One candidate to one decision: a row and a record, or a refusal naming what was searched."""
    item = {"shot": name, "utterances": list(uids), "provider": provider}
    candidate = providers.candidate(provider, document, entry)
    item["asset_id"] = candidate["asset_id"]
    placeholders = {"asset_id": candidate["asset_id"],
                    "title": _field(document, entry, "title", {"asset_id": candidate["asset_id"]})}

    media = _media_url(run, document, entry, candidate, placeholders)
    if not media:
        return {"refusal": _refusal(
            run, "missing_field",
            detail=f"{provider}.item_fields.file_url resolves to a document rather than a file, "
                   "and its detail endpoint names no downloadable file either, so the ledger's "
                   "file field cannot be filled",
            field_paths=[f"item_fields.{key}" for key in ("file_url", "page_url")], **item)}
    already = used_urls.get(media)
    if already:
        documented = run.episode / PurePosixPath(str(already["file"]))
        if documented.is_file():
            # Checked before the fetch, not after: re-downloading a file this episode already
            # documents would buy bytes for a row that cannot be written twice.
            return {"refusal": _refusal(
                run, "missing_field",
                detail=f"this is the file {already['licence']} already documents at "
                       f"{already['file']}; sourcing it again would put two rows on one asset",
                field_paths=["item_fields.file_url"], **item)}
        # The row and the record are intact and only the bytes are gone, which is the state a
        # re-run exists to end: land the file where that row already says it is, and write no
        # second row for one asset.
        return _replace_missing_bytes(run, media, already, document, entry, item, name)

    basis = _basis_of(run, entry, list(candidate.get("evidence") or []))
    if basis.get("refusal"):
        return {"refusal": _refusal(run, basis["refusal"], detail=basis["detail"],
                                    field_paths=basis["field_paths"], **item)}

    dated = (_field(document, entry, "date", placeholders)
             or _field(document, entry, "date_fallback", placeholders))
    source_year = _year(dated)
    if source_year is None:
        return {"refusal": _refusal(
            run, "missing_field",
            detail=f"item_fields.date and item_fields.date_fallback both came back without a "
                   f"four-digit year ({dated!r}), and source_year is a required integer",
            field_paths=["item_fields.date", "item_fields.date_fallback"], **item)}

    annotations = _hint_annotations(run, entry, document)
    title, source_archive = placeholders["title"], str(entry["label"])
    attribution = (_field(document, entry, "attribution", placeholders)
                   or _fill(run.sourcing["attribution_fallback"],
                            {"source_archive": source_archive, "asset_id": candidate["asset_id"]},
                            name="attribution_fallback"))

    if run.dry_run:
        return {"would": {**item, "retrieval_url": media, "rights_basis": basis["basis"],
                          "basis_field_path": basis["field_path"], "downloaded": False,
                          "committed": False, "annotations": annotations,
                          "note": "a dry run downloads nothing, so the row's timecodes — which "
                                  "are measured from the bytes — cannot exist yet"}}

    ident = supply_id()
    suffix = PurePosixPath(urlsplit(media).path).suffix.lower()
    file_relative = f"{str(run.paths['source_dir']).rstrip('/')}/{_safe(name)}-{ident}{suffix}"
    destination = run.episode / PurePosixPath(file_relative)

    try:
        if destination.is_file():
            digest, reused = read_digest(destination, run.contract), True
        else:
            digest = download_binary(media, destination, run.binary_opener,
                                     max_bytes=run.max_bytes, contract=run.contract,
                                     state=run.state,
                                     min_interval_seconds=float(entry.get("min_interval_seconds",
                                                                          0.0)))
            reused = False
    except (TransportFailure, ValueError, OSError) as error:
        return {"refusal": _refusal(run, "source_unavailable",
                                    detail=f"{media}: {type(error).__name__}: {error}",
                                    field_paths=[basis["field_path"]], **item)}

    measured = _measure(run, destination)
    if measured["ratio"] is None or (measured["rate"] <= 0 and measured["seconds"] > 0):
        return {"refusal": _refusal(
            run, "missing_field",
            detail=f"{destination.name} probes with no frame size or no usable rate, so "
                   "source_frame_rate, timebase and both timecodes cannot be measured",
            field_paths=[basis["field_path"]], **item)}

    form = _form(run, measured)
    span = _span(run, form, measured)
    aspect = _threshold(run.usage["aspect_by_ratio"], measured["ratio"], name="aspect_by_ratio")
    transformations = run.usage["transformations"]
    chosen = []
    for key in (aspect, str(run.usage["default_treatment"])):
        clause = str(transformations.get(key) or "").strip()
        if clause and clause not in chosen:
            chosen.append(clause)
    if not chosen:
        return {"refusal": _refusal(
            run, "missing_field",
            detail=f"usage.transformations declares no clause for {aspect!r} or "
                   f"{run.usage['default_treatment']!r}, and uploaded_as_is false has to be "
                   "contradicted by something the file a viewer opens can show",
            field_paths=[f"usage.transformations[{key!r}]" for key in (aspect,
                                                                       run.usage["default_treatment"])],
            **item)}

    obligations = list((entry.get("obligations_by_basis") or {}).get(basis["basis"], []))
    row = ledger_row(run, ident=ident, provider=provider, entry=entry, candidate=candidate,
                     basis=basis, form=form, measured=measured, span=span, media_url=media,
                     page_url=candidate["url"], title=title, attribution=attribution,
                     source_year=source_year, file_relative=file_relative, transforms=chosen,
                     obligations=obligations)
    blocked = _schema_block(run, row, basis, obligations, item)
    if blocked:
        run.downloaded_not_committed.append({"file": file_relative, "sha256": digest,
                                             "reason": blocked["reason"], "shot": name})
        return {"refusal": blocked}

    record = archive_record(run, asset=file_relative, ident=ident, form=form, measured=measured,
                            aspect=aspect, carries=run.carries)
    broken = _validate(run, list(existing_rows) + list(new_rows) + [row],
                       {**existing_records, **new_records, name: record})
    if broken:
        refusal = _refusal(
            run, "missing_field",
            detail=f"workflow/archive.py refuses the row this provider's data produces: {broken}",
            field_paths=[basis["field_path"]], **item)
        run.downloaded_not_committed.append({"file": file_relative, "sha256": digest,
                                             "shot": name, "reason": refusal["reason"],
                                             "why": broken})
        return {"refusal": refusal}

    return {"row": row, "record": record, "media": media,
            "accepted": {**item, "licence": ident, "file": file_relative, "retrieval_url": media,
                         "sha256": digest, "reused_on_disk": reused, "rights_basis": basis["basis"],
                         "basis_field_path": basis["field_path"],
                         "basis_raw_value": basis["raw_value"], "form": form, "aspect": aspect,
                         "span_seconds": span, "timebase": row["timebase"],
                         "source_frame_rate": row["source_frame_rate"],
                         "source_year": source_year, "obligations": obligations,
                         "measured": measured, "annotations": annotations, "downloaded": True}}


def _safe(name: str) -> str:
    cleaned = SAFE_NAME_RE.sub("-", str(name)).strip("-")
    return cleaned or "shot"


# --------------------------------------------------------------------------- one shot

def source_shot(run: Run, name: str, uids, supply_id, used_urls, existing_rows, existing_records,
                new_rows, new_records) -> bool:
    """Fill one archival shot from the enabled archives, in contract order. Returns whether it did.

    Candidates are taken in the order the archives returned them and accepted directly — the
    bypass. What still has to be true for an accept is that the row can be *written*: a downloadable
    file, a nameable basis, a measurable frame rate, and a merged pair of files the validators
    accept. An item that fails one of those is refused and the next candidate gets the shot.
    """
    query = run.query_for(name)
    for provider in run.provider_names:
        entry = providers.provider_entry(provider, contract=run.contract)
        try:
            payload = _payload(run, provider, query)
        except (RequestShapeError, TransportFailure, OSError) as error:
            # `OSError` is here because a refused socket and a 404 arrive as `URLError` and
            # `HTTPError`, and the contract says a transport fault is a `source_unavailable`
            # refusal for that item — never a crash, and never a verdict either way.
            key = "request_shape" if isinstance(error, RequestShapeError) else "source_unavailable"
            run.refused.append(_refusal(run, key, detail=f"{type(error).__name__}: {error}",
                                        shot=name, utterances=list(uids), provider=provider,
                                        query=query, field_paths=_searched_field_paths(entry)))
            continue
        try:
            transport.check_payload(payload, entry,
                                    what=f"{provider} search for the archival shot {name}")
        except RequestShapeError as error:
            # Reported apart from "no footage" on purpose: collapsing the two is how a typo in a
            # field list silences a corpus, which is `request_shape`'s whole contract `why`.
            run.refused.append(_refusal(run, "request_shape", detail=str(error), shot=name,
                                        utterances=list(uids), provider=provider, query=query,
                                        field_paths=_searched_field_paths(entry)))
            continue

        documents = [document for document in transport.docs_of(payload, entry)
                     if isinstance(document, dict)]
        run.searched.append({"provider": provider, "label": str(entry["label"]), "query": query,
                             "url": providers.search_url(provider, query, run.limit,
                                                         contract=run.contract),
                             "documents": len(documents)})

        for document in documents[:run.limit]:
            result = _resolve_candidate(run, provider, entry, document, name=name, uids=uids,
                                        used_urls=used_urls, supply_id=supply_id,
                                        existing_rows=existing_rows,
                                        existing_records=existing_records, new_rows=new_rows,
                                        new_records=new_records)
            if result.get("refusal"):
                run.refused.append(result["refusal"])
                continue
            if result.get("would"):
                run.accepted.append(result["would"])
                used_urls[result["would"]["retrieval_url"]] = {"file": result["would"].get("file", "")}
                return True
            new_rows.append(result["row"])
            new_records[name] = result["record"]
            used_urls[result["media"]] = {"file": result["row"]["file"]}
            run.accepted.append(result["accepted"])
            return True
    return False


# --------------------------------------------------------------------------- the run

def pending_shots(run: Run) -> tuple:
    """Which archival shots still need sourcing, and the state of the ones that do not.

    `workflow/episode.archive_sources()` is the round trip this run must survive, and it is useless
    as a queue: it raises the moment a shot has no record, which is the state a sourcer exists to
    end. So the pending set comes from the shot table minus what `records(required=False)` and
    `ledger()` already prove, and `archive_sources()` runs at the end as the acceptance proof
    instead.
    """
    try:
        declared = read_records(run.episode, run.contract, required=False)
        rows = read_ledger(run.episode, run.contract)
    except ValueError as error:
        raise UnreadableLedger(f"{run.episode.name} already holds archival files that do not "
                               f"validate, so nothing may be appended to them: {error}") from None

    layer = _archive_layer(run.contract)
    try:
        table = episode_files.shots(run.episode, run.contract)
    except ValueError as error:
        # No timeline is the third declared condition, not a stack trace: the contract's own
        # sentence is what a reader of the report has to be able to cite.
        raise RefuseBeforeDownload(_declared_condition(run.contract, REFUSAL_NEEDLES["shots"]),
                                   str(error)) from None
    wanted: dict[str, list] = {}
    for uid, entry in table.items():
        if entry[0] == layer:
            wanted.setdefault(entry[1], []).append(uid)
    if not wanted:
        raise RefuseBeforeDownload(_declared_condition(run.contract, REFUSAL_NEEDLES["shots"]),
                                   f"{episode_files.shots_path(run.episode).name} declares no "
                                   f"shot of kind {layer!r}, so there is no footage to find")

    if run.only:
        unknown = [shot for shot in run.only if shot not in wanted]
        if unknown:
            raise UsageError(f"--shot names {unknown}, which are not archival shots of "
                             f"{run.episode.name}; "
                             f"{episode_files.shots_path(run.episode).name} declares "
                             f"{sorted(wanted)}")
        wanted = {shot: uids for shot, uids in wanted.items() if shot in run.only}

    pending = {}
    for name, uids in wanted.items():
        record = declared.get(name)
        row = rows.get(str(record["licence"])) if record else None
        asset = str(record["asset"]) if record else ""
        complete = (record is not None and row is not None and row["file"] == asset
                    and (run.episode / PurePosixPath(asset)).is_file())
        if not complete:
            pending[name] = list(uids)
    return pending, _stored(run, "ledger_filename", []), _stored(run, "records_filename", {})


def execute(run: Run) -> dict:
    """Search, download, commit — and report, whether or not anything landed."""
    pending, existing_rows, existing_records = pending_shots(run)
    unqueried = [name for name in pending if not run.query_for(name)]
    if unqueried:
        raise UsageError(f"nothing states what to search for the archival shots {unqueried}: "
                         "pass --query for the topic, or --shot-query NAME=QUERY for each of them")
    supply_id = _next_ids([row["id"] for row in existing_rows], run.sourcing["record_id"])
    used_urls = {str(row["retrieval_url"]): row for row in existing_rows}
    new_rows, new_records, unfilled = [], {}, []
    for name, uids in pending.items():
        if not source_shot(run, name, uids, supply_id, used_urls, existing_rows, existing_records,
                           new_rows, new_records):
            unfilled.append(name)

    if run.dry_run:
        outcome = {"committed": False,
                   "why": "dry run: nothing downloaded, no file written"}
    elif not new_rows:
        outcome = {"committed": not pending,
                   "why": "" if not pending else "nothing was accepted, so nothing was written"}
    else:
        outcome = commit(run, existing_rows, existing_records, new_rows, new_records)

    return {"entry_point": str(run.sourcing["entry_point"]), "episode": run.episode.name,
            "retrieval_date": run.retrieval_date, "query": run.query,
            "shot_queries": dict(run.shot_queries), "providers": list(run.provider_names),
            "limit": run.limit, "dry_run": run.dry_run,
            "rights_verdicts": "bypassed by instruction — gates, contradictions, restrictions_gate "
                               "and allowed_bases are not evaluated, and every candidate the "
                               "archives return is downloaded. What is still named from contract "
                               "data is rights_basis itself, and the two archive.rights rules the "
                               "ledger validator applies to every row (publication_year_floor, "
                               "obligations_required_for_bases) are checked before any commit, "
                               "because a row they refuse cannot be written at all.",
            "carries": {"value": run.carries, "defaulted": run.carries_defaulted},
            "refused_before_download": None, "pending_shots": sorted(pending),
            "searched": run.searched, "accepted": run.accepted, "refused": run.refused,
            "downloaded_not_committed": run.downloaded_not_committed, "unfilled": unfilled,
            **outcome}


def write_report(run: Run, report: dict) -> Path:
    path = run.episode / PurePosixPath(str(run.sourcing["report_filename"]))
    _write(path, report)
    return path


# --------------------------------------------------------------------------- CLI

def _shot_query_pairs(pairs) -> dict:
    out = {}
    for pair in pairs or ():
        name, separator, query = str(pair).partition("=")
        if not separator or not query.strip() or not name.strip():
            raise UsageError(f"--shot-query wants name=query, got {pair!r}")
        out[name.strip()] = query.strip()
    return out


def build(argv=None, *, limit_default=providers.DEFAULT_LIMIT,
          max_bytes_default=DEFAULT_MAX_BYTES):
    parser = argparse.ArgumentParser(
        description="Find, download and license the footage an episode's archival shots need, "
                    "from the providers the style contract enables.")
    parser.add_argument("--episode", type=Path, required=True,
                        help="episode directory, or a slug under work/ — required, because a tool "
                             "that can guess which film it is sourcing will guess it unattended")
    parser.add_argument("--query", help="the topic every shot without a --shot-query searches on")
    parser.add_argument("--shot-query", action="append", dest="shot_queries", metavar="NAME=QUERY",
                        help="the query for one archival shot (repeatable)")
    parser.add_argument("--shot", action="append", dest="shots", metavar="NAME",
                        help="restrict the run to this archival shot (repeatable)")
    parser.add_argument("--provider", action="append", dest="providers", metavar="NAME",
                        help="restrict the run to these archive.sourcing providers (repeatable)")
    parser.add_argument("--limit", type=int, default=limit_default,
                        help="candidates asked of each provider")
    parser.add_argument("--retrieval-date", help="ISO date this run is made on; defaults to today")
    parser.add_argument("--purpose", help="the editorial purpose written into purpose_of_use, "
                                          "which the contract calls the only way an argument "
                                          "reaches the row")
    parser.add_argument("--carries", help="the archive_carries token each new record declares")
    parser.add_argument("--max-bytes", type=int, default=max_bytes_default,
                        help="download ceiling per asset")
    parser.add_argument("--dry-run", action="store_true",
                        help="search and pick, download and write nothing")
    return parser, parser.parse_args(argv)


def _prepare(args, block: dict, *, opener, binary_opener, prober, state, clock) -> Run:
    """Everything that can refuse before a request is made, in the contract's own order."""
    try:
        episode = episode_files.resolve(ROOT, args.episode)
    except ValueError as error:
        raise RefuseBeforeDownload(_declared_condition(block, REFUSAL_NEEDLES["episode"]),
                                   str(error)) from None
    sourcing = _sourcing(block)

    requested = [str(name) for name in (args.providers or ())]
    unknown = [name for name in requested if name not in sourcing["providers"]]
    if unknown:
        raise UsageError(f"--provider names {unknown}, which archive.sourcing.providers does not "
                         f"declare; the contract offers {sorted(sourcing['providers'])}")
    for name in requested:
        # Declared but switched off is a contract decision, not a typo: `provider_entry` refuses it,
        # and dropping the request quietly would source a different corpus than the one asked for.
        providers.provider_entry(name, contract=block)
    enabled = [name for name, entry in sourcing["providers"].items() if entry.get("enabled", False)]
    provider_names = [name for name in enabled if not requested or name in requested]
    for name in provider_names:
        # Enabled has to mean usable, not merely present: an entry with no endpoint or no query
        # parameter is a contract bug, and `provider_entry` is the one that knows what usable is.
        providers.provider_entry(name, contract=block)
    if not provider_names:
        raise RefuseBeforeDownload(
            _declared_condition(block, REFUSAL_NEEDLES["providers"]),
            "archive.sourcing.providers holds no enabled provider"
            + (f", and none of the requested {requested} is one" if requested else ""))

    shot_queries = _shot_query_pairs(args.shot_queries)
    only = tuple(str(name) for name in (args.shots or ()))
    topic = str(args.query or "").strip()
    if not topic and not shot_queries:
        raise UsageError("--query is required (or a --shot-query for every shot): the contract "
                         "states no topic for an episode, and a run that guesses one sources "
                         "footage for a film nobody is making")

    retrieval_date = str(args.retrieval_date or clock().isoformat()).strip()
    try:
        date.fromisoformat(retrieval_date)
    except ValueError:
        raise UsageError(f"--retrieval-date {retrieval_date!r} is not an ISO date; the cache key "
                         "and the ledger both compare it as one, and a public-domain claim is only "
                         "true as of a day") from None

    carries_options = list(block["archive"]["division_of_labour"]["archive_carries"])
    carries = str(args.carries or "").strip()
    carries_defaulted = not carries
    carries = carries or carries_options[0]
    if carries not in carries_options:
        raise UsageError(f"--carries {carries!r} is outside "
                         f"archive.division_of_labour.archive_carries {carries_options}")

    return Run(episode=episode, contract=block, sourcing=sourcing, usage=sourcing["usage"],
               policy=transport.transport_policy(block), paths=archive_paths(block),
               rights=block["archive"]["rights"], provider_names=provider_names, query=topic,
               shot_queries=shot_queries, only=only, limit=int(args.limit),
               retrieval_date=retrieval_date, purpose=str(args.purpose or "").strip(),
               carries=carries, carries_defaulted=carries_defaulted,
               max_bytes=int(args.max_bytes), dry_run=bool(args.dry_run), opener=opener,
               binary_opener=binary_opener, prober=prober,
               state=state if state is not None else transport.RateState())


def _refusal_report(run, args, condition: dict, error) -> dict:
    """The evidence a refused run still leaves behind.

    With an episode directory there is a file to write, and the contract's three conditions are
    exactly what it says; without one there is nowhere to put it, which is the condition itself.
    """
    if run is None:
        return {"episode": str(args.episode), "refused_before_download": condition,
                "accepted": [], "refused": [], "unfilled": [], "committed": False,
                "why": str(error)}
    return {"entry_point": str(run.sourcing["entry_point"]), "episode": run.episode.name,
            "retrieval_date": run.retrieval_date, "query": run.query, "dry_run": run.dry_run,
            "providers": list(run.provider_names), "refused_before_download": condition,
            "rights_verdicts": "bypassed by instruction; this run refused before any request, so "
                               "nothing was fetched and nothing was decided",
            "carries": {"value": run.carries, "defaulted": run.carries_defaulted},
            "searched": run.searched, "accepted": run.accepted, "refused": run.refused,
            "downloaded_not_committed": run.downloaded_not_committed, "unfilled": [],
            "committed": False, "why": str(error)}


def main(argv=None, *, contract=None, opener=_open_url, binary_opener=_open_url, prober=None,
         state=None, clock=date.today) -> int:
    parser, args = build(argv)
    block = contract if contract is not None else style_contract(ROOT)
    run = None
    try:
        run = _prepare(args, block, opener=opener, binary_opener=binary_opener, prober=prober,
                       state=state, clock=clock)
        report = execute(run)
    except RefuseBeforeDownload as error:
        report = _refusal_report(run, args, {"condition": error.condition,
                                             "detail": error.detail}, error)
        print(f"refused before download — {error}", file=sys.stderr)
        if run is not None:
            print(f"evidence in {write_report(run, report)}", file=sys.stderr)
        return 1
    except UsageError as error:
        print(error, file=sys.stderr)
        return 2
    except UnreadableLedger as error:
        print(error, file=sys.stderr)
        return 1
    except (ProviderUnavailable, TransportFailure, ValueError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1

    written = write_report(run, report)
    print(f"{run.episode.name}: {len(report['accepted'])} asset(s) accepted, "
          f"{len(report['refused'])} refusal(s), {len(report['unfilled'])} shot(s) unfilled; "
          f"evidence in {written}")
    if run.dry_run:
        # A dry run is asked for by somebody who wants to read a plan, so the plan is the verdict:
        # it succeeds when every archival shot has a file chosen for it, and fails when one does
        # not. Nothing being committed is the point of the flag, not a failure.
        print("dry run: nothing downloaded, no archival file written")
        return 1 if report["unfilled"] else 0
    if not report["committed"]:
        print(f"not committed: {report['why']}", file=sys.stderr)
        return 1
    return 0 if not report["unfilled"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
