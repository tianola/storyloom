"""The archival layer as data: one record per archival shot, one rights row per archival asset.

Two files, both read by the build before anything is encoded:

  `archive.json`          what the shot is — source path, native rate, aspect treatment,
                          cohesion treatment, which side its light comes from.
  `assets/archive-licence.json`
                          what we may do with it — every field `workflow/style.json` calls
                          `rights.required_fields`, each with its kind in `rights.field_types`,
                          ending in a rights *basis* rather than a purchase status.

These rules are metadata, and the contract's `enforcement_policy` puts metadata on the
blocking side: an archival shot whose rights cannot be stated in one row is not a shot with
a warning on it, it is a shot that must not reach a master. Retyping each bound here is what
the style contract exists to prevent, so every enum and field list below is read from it.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qsl, urlsplit

MODE_LADDER = ["off", "warn", "closed"]
ALLOWED_SCOPES = frozenset({"episode", "act", "sequence"})
CATCH_ALL_REASONS = frozenset({"other", "misc", "miscellaneous", "na", "none", "general"})


def _normalise(value: str) -> str:
    return re.sub(r"[-_ ]", "", str(value)).casefold()


def _query_names(contract: dict) -> frozenset:
    """The URL parameter names that may not appear in a published ledger row.

    Read from the contract rather than written here: the words that name a credential are
    exactly the strings a scanner flags, and a validator carrying its own copy of them looks
    like a leak. Underscores and hyphens are stripped on both sides so `access_token`,
    `access-token` and `accesstoken` are all refused by one entry.
    """
    return frozenset(_normalise(name)
                     for name in contract["archive"]["rights"]["credential_query_names"])


def paths(contract: dict) -> dict:
    """Where the archival layer lives inside an episode, read rather than remembered."""
    declared = contract["archive"].get("paths")
    if not declared:
        raise ValueError("style.json archive.paths is missing, so the archival layer has no "
                         "declared source or render directory")
    return declared


def profile(contract: dict) -> dict:
    """The archival layer as an episode-level obligation, read from the contract.

    Missing is refused rather than treated as `off`. That distinction is the whole mechanism of
    a default: a block that is only consulted when present can be deleted by a later refactor
    while every call site keeps working, and the episode that ships is silently 3D-only — the
    divergence between the stated style and the finished film that the style contract exists to
    prevent.

    The bounds are checked against each other rather than against constants, so revising the
    house numbers is an edit to `style.json` and never a test edit. What is *not* revisable in
    data is the ladder's shape, the archive's place in the taxonomy, and the opt-out's inability
    to silence the gate — those three are what keep a future convenience from quietly unmaking
    the default.
    """
    declared = contract["archive"].get("episode_profile")
    if not declared:
        raise ValueError(
            "style.json archive.episode_profile is missing, so nothing states that an episode "
            "owes the film an archival layer; the layer would fall back to being an option a "
            "build can fall out of unnoticed")

    modes = list(declared["modes"])
    if modes != MODE_LADDER:
        raise ValueError(f"archive.episode_profile.modes must be the rollout ladder "
                         f"{MODE_LADDER} in order, got {modes}; the order is what makes "
                         "narrowing and widening decidable")
    mode = declared["mode"]
    if mode not in modes:
        raise ValueError(f"archive.episode_profile.mode {mode!r} is not a rung of the ladder "
                         f"{modes}")
    meanings = declared.get("mode_meaning") or {}
    undefined = [rung for rung in modes if not str(meanings.get(rung, "")).strip()]
    if undefined:
        raise ValueError(f"archive.episode_profile.mode_meaning leaves {undefined} undefined; "
                         "an undocumented rung is the rung someone picks when a build annoys "
                         "them")

    mix = declared["mix"]
    layers = list(mix["layers"])
    if not layers or len(set(layers)) != len(layers) or not all(str(k).strip() for k in layers):
        raise ValueError(f"archive.episode_profile.mix.layers must be a non-empty list of "
                         f"distinct layer names, got {layers}")
    if "archive" not in layers:
        raise ValueError("archive.episode_profile.mix.layers omits `archive`, so the profile "
                         "describes a film with no archival layer")
    if not str(mix.get("measured_on", "")).strip():
        raise ValueError("archive.episode_profile.mix.measured_on must say what the share is a "
                         "share of; a gate that cannot name its unit cannot be checked")
    for bound in ("min_share", "min_per_act"):
        values = mix[bound]
        unbudgeted = [layer for layer in layers if layer not in values]
        unknown = [key for key in values if key != "basis" and key not in layers]
        if unbudgeted or unknown:
            raise ValueError(
                f"archive.episode_profile.mix.{bound} and mix.layers disagree: "
                f"{unbudgeted} have no bound, {unknown} are not a declared layer. A layer that "
                "escapes the taxonomy is how a new visual kind stops being judged without "
                "anything appearing to change")
        for layer in layers:
            number = float(values[layer])
            if bound == "min_share" and not 0.0 <= number <= 1.0:
                raise ValueError(f"mix.min_share[{layer!r}] is {number}, outside 0..1")
            if bound == "min_per_act" and number < 0:
                raise ValueError(f"mix.min_per_act[{layer!r}] is {number}")

    act = mix["act_seconds"]
    if (not isinstance(act, list) or len(act) != 2 or not 0 < float(act[0]) <= float(act[1])):
        raise ValueError(f"archive.episode_profile.mix.act_seconds must be [low, high] with "
                         f"0 < low <= high, got {act}; per-act obligations only mean something "
                         "once the act boundaries are declared")

    opt = declared["opt_out"]
    absent = [field for field in ("reason", "scope", "approved_by", "expires", "enabled")
              if field not in opt["required_fields"]]
    if absent:
        raise ValueError(f"archive.episode_profile.opt_out.required_fields omits {absent}; a "
                         "record without a reason, an owner and an expiry is an unlogged "
                         "exception, which is how a house style dies")
    reasons = list(opt["reason_enum"])
    catch_all = [name for name in reasons
                 if re.sub(r"[-_ ]", "", name).casefold() in CATCH_ALL_REASONS]
    if not reasons or catch_all:
        raise ValueError(f"archive.episode_profile.opt_out.reason_enum must be a closed list "
                         f"with no catch-all, got {reasons} ({catch_all} make the record a "
                         "formality — any convenience becomes a reason)")
    scopes = list(opt["scope_values"])
    if not scopes or not set(scopes) <= ALLOWED_SCOPES or "episode" not in scopes:
        raise ValueError(f"archive.episode_profile.opt_out.scope_values must be a non-empty "
                         f"subset of {sorted(ALLOWED_SCOPES)} including `episode`, got {scopes}")
    if opt["silences_gate"]:
        raise ValueError("archive.episode_profile.opt_out.silences_gate is true: an opt-out "
                         "may downgrade the gate, never mute it, or the exemption also deletes "
                         "the evidence that the film was made without the layer")
    return declared


@dataclass(frozen=True)
class Finding:
    """One rule the profile would apply, and what the current mode does about it."""

    code: str
    severity: str
    message: str


def resolve_mode(contract: dict, episode_document: dict | None) -> tuple[str, list[Finding]]:
    """The mode this episode is judged in, plus the finding its own record produced.

    The contract states the default; `episode.json` may narrow it or excuse itself from it, and
    nothing else. Widening is refused rather than quietly accepted, because an episode document
    that could pick `off` would make the pipeline-wide default a suggestion again — the exact
    state this file was added to leave behind.

    An opt-out lowers `closed` to `warn` and adds a finding of its own instead of removing the
    ones the episode would otherwise get. `opt_out.silences_gate` is checked in `profile()` for
    the same reason: the exemption has to stay visible in the report that outlives the build.
    """
    declared = profile(contract)
    mode = declared["mode"]
    record = (episode_document or {}).get("archive")
    if record is None:
        return mode, []
    if not isinstance(record, dict):
        raise ValueError(f"the episode's archive record must be an object, got "
                         f"{type(record).__name__}; a bare string or list cannot carry a "
                         "reason, an approver or an expiry, which is the whole record")

    findings: list[Finding] = []
    if "mode" in record:
        asked = record["mode"]
        if asked not in MODE_LADDER:
            raise ValueError(f"episode archive.mode {asked!r} is not a rung of the ladder "
                             f"{MODE_LADDER}")
        if MODE_LADDER.index(asked) < MODE_LADDER.index(mode):
            raise ValueError(
                f"this episode asks for archive mode {asked!r}, looser than the contract's "
                f"{mode!r}. An episode may hold itself to a stricter rung; loosening the "
                "pipeline-wide default is an edit to style.json, where it can be read and "
                "argued about, not a line in one episode's file")
        mode = asked

    if record.get("enabled", True):
        return mode, findings

    opt = declared["opt_out"]
    absent = [name for name in opt["required_fields"]
              if name != "enabled" and not str(record.get(name, "")).strip()]
    if absent:
        raise ValueError(f"archive opt-out record is missing {absent}; a reason, a scope, a "
                         "named approver and an expiry are what make an exemption reviewable by "
                         "someone who was not in the room")
    if record["reason"] not in opt["reason_enum"]:
        raise ValueError(f"archive opt-out reason {record['reason']!r} is outside the closed "
                         f"enum {list(opt['reason_enum'])}")
    if record["scope"] not in opt["scope_values"]:
        raise ValueError(f"archive opt-out scope {record['scope']!r} is not one of "
                         f"{list(opt['scope_values'])}")
    try:
        expires = date.fromisoformat(record["expires"])
    except ValueError:
        raise ValueError(f"archive opt-out expires {record['expires']!r} is not an ISO date; "
                         "an expiry that cannot be compared is an exemption that never ends")
    if expires < date.today():
        raise ValueError(f"archive opt-out expires={expires.isoformat()} has already passed; "
                         "the record has to be renewed, which is the moment someone re-decides "
                         "it")

    if mode == "closed":
        mode = "warn"
    findings.append(Finding(
        "archive_layer_opted_out", "warning",
        f"the archival layer is waived for this episode — reason {record['reason']}, "
        f"scope {record['scope']}, approved by {record['approved_by']}, "
        f"expires {expires.isoformat()}"))
    return mode, findings


def _seconds_by_layer(shots, layers) -> tuple[dict, dict, dict]:
    """Sum screen seconds per layer and collect their start points, refusing a shot list that
    cannot describe a film.

    `shots` is the shape the QC gate already has: `{"layer", "start", "seconds"}` per shot. The
    unit is seconds and the field is named for it, because a share computed over counts is a
    different claim — see `mix.measured_on`.
    """
    if not shots:
        raise ValueError("the archival mix needs the shot list; an empty list means the "
                         "timeline was never written, and reporting that as a missing visual "
                         "layer would blame the layer for the assembler")
    declared = set(layers)
    by_seconds: dict[str, float] = {layer: 0.0 for layer in layers}
    by_starts: dict[str, list[float]] = {layer: [] for layer in layers}
    unknown: dict[str, float] = {}
    for shot in shots:
        layer = str(shot["layer"])
        seconds = float(shot["seconds"])
        start = float(shot["start"])
        if seconds < 0 or start < 0:
            raise ValueError(f"shot on layer {layer!r} declares start {start} for "
                             f"{seconds} s; a negative span is not a shot")
        if layer not in declared:
            unknown[layer] = unknown.get(layer, 0.0) + seconds
            continue
        by_seconds[layer] += seconds
        by_starts[layer].append(start)
    return by_seconds, by_starts, unknown


def mix_findings(shots, contract: dict, *, mode: str | None = None) -> list[Finding]:
    """What the profile owes this film, stated as findings instead of a verdict.

    `off` reports nothing — that is what the rung means. `warn` reports here and refuses nowhere;
    the refusal is `require_mix`'s job, so the two rungs can never disagree about the number they
    compared. A film with no archival seconds produces one finding rather than three, because the
    share and the per-act counts are consequences of the same absence and a report that states one
    fact three ways invites the reader to negotiate with the numbers.
    """
    declared = profile(contract)
    mix = declared["mix"]
    mode = declared["mode"] if mode is None else mode
    if mode not in MODE_LADDER:
        raise ValueError(f"mode {mode!r} is not a rung of the ladder {MODE_LADDER}")
    if mode == "off":
        return []

    severity = "warning"
    layers = list(mix["layers"])
    by_seconds, by_starts, unknown = _seconds_by_layer(shots, layers)

    findings = [Finding(
        "layer_unknown", severity,
        f"{name} carries {seconds:.1f} s of screen time and no entry in "
        f"archive.episode_profile.mix, so the mix below is measured without it; either the "
        f"taxonomy in mix.layers has to name it or the assembler has to stop emitting it")
        for name, seconds in sorted(unknown.items())]

    total = sum(by_seconds.values())
    if total <= 0:
        raise ValueError("the shot list carries no screen seconds at all; refusing to compute a "
                         "share over a zero-length film")
    archive_seconds = by_seconds["archive"]
    floor = float(mix["min_share"]["archive"])
    if archive_seconds <= 0 and floor <= 0 and int(mix["min_per_act"]["archive"]) <= 0:
        return findings     # no floor: archive is evidence where there is some, not a quota
    if archive_seconds <= 0:
        findings.append(Finding(
            "archive_layer_missing", severity,
            f"the film has no archival screen time — 0.0 s of {total:.1f} s across "
            f"{layers}; the profile treats this as the layer being absent, not as a small share"))
        return findings

    share = archive_seconds / total
    if share < floor:
        findings.append(Finding(
            "archive_share_low", severity,
            f"archival screen time is {share:.3f} of {total:.1f} s, under the profile floor "
            f"{floor} ({archive_seconds:.1f} s)"))

    _low, high = (float(value) for value in mix["act_seconds"])
    required = int(mix["min_per_act"]["archive"])
    first = min(float(shot["start"]) for shot in shots)
    last = max(float(shot["start"]) + float(shot["seconds"]) for shot in shots)
    acts = max(1, math.ceil((last - first) / high))
    span = (last - first) / acts
    for index in range(acts):
        lo, hi = first + index * span, first + (index + 1) * span
        # The final act is closed at both ends so a shot that runs to the last frame of the film
        # is not reported as belonging to no act at all.
        hits = [start for start in by_starts["archive"]
                if (lo <= start < hi) or (index == acts - 1 and start == hi)]
        if len(hits) < required:
            findings.append(Finding(
                "archive_act_missing", severity,
                f"the span {lo:.1f}-{hi:.1f} s holds {len(hits)} archival shot(s) and the "
                f"profile requires {required} per act; a layer that abandons the end of the "
                "argument is not a voice, it is an opening titles texture"))
    return findings


def require_mix(shots, contract: dict, *, mode: str | None = None) -> list[Finding]:
    """Refuse the build when the rung says refuse, and report the same findings when it does not.

    One function computes and one decides, so `warn` is provably the refusal `closed` would have
    made rather than a softer paraphrase of it.
    """
    declared = profile(contract)
    mode = declared["mode"] if mode is None else mode
    findings = mix_findings(shots, contract, mode=mode)
    if mode == "closed" and findings:
        raise ValueError(
            "archive.episode_profile refuses this episode in closed mode: "
            + "; ".join(f"{finding.code}: {finding.message}" for finding in findings))
    return findings


def key_side(contract: dict) -> str:
    """Which side of the frame our 3D key comes from.

    An archival clip is allowed to be flipped to agree with it, and the flip is a falsification
    the moment the frame carries readable writing — so the side has to be a declared value that
    the beats and the ingest can both read, not an opinion in a comment.
    """
    return contract["lighting"]["key_side"]


def relative_posix_problem(value) -> str | None:
    """'empty', 'unsafe' (a backslash, an absolute path or a '..'), or None for a safe relative
    POSIX path. Shared by the archive and episode loaders, which word their own messages."""
    if not isinstance(value, str) or not value.strip():
        return "empty"
    if "\\" in value or PurePosixPath(value).is_absolute() or ".." in PurePosixPath(value).parts:
        return "unsafe"
    return None


def _relative_posix(value: str, field: str, name: str) -> str:
    problem = relative_posix_problem(value)
    if problem == "empty":
        raise ValueError(f"{name}: {field} must be a non-empty path")
    if problem:
        raise ValueError(f"{name}: {field} must be an episode-relative POSIX path, got {value!r}")
    return value


def _http_url(value: str, field: str, name: str, banned: frozenset) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{name}: {field} must be an HTTP(S) URL, got {value!r}")
    if parsed.username or parsed.password:
        raise ValueError(f"{name}: {field} must not carry credentials in its authority")
    names = {_normalise(key) for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}
    if names & banned:
        raise ValueError(f"{name}: {field} must not carry a credential parameter "
                         f"(found {sorted(names & banned)})")
    return value


TIMECODE_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})([:;])(\d{2})$")


def _drop_frames_per_minute(timebase: int, source_frame_rate: float) -> int:
    """How many frame numbers one drop-minute skips, derived rather than tabulated.

    A minute of 29.97 material records 1798.2 frames while the label counts to 1800, so two
    numbers are dropped a minute — the same arithmetic for 59.94 against a 60 modulus gives
    four. A rate that needs no dropping is a rate drop-frame was never defined for, which is
    why an integral rate under `;` notation is refused instead of silently read as a plain
    count: the operator who wrote it thought one thing and the label says another.
    """
    return round(60.0 * (timebase - source_frame_rate))


def _timecode_seconds(value: str, *, field: str, ident: str, timebase: int,
                      source_frame_rate: float) -> float:
    """The real second a SMPTE label names, at the rate the material was actually cut.

    `timebase` is the label's modulus and `source_frame_rate` is the tape; they differ exactly
    when the label is drop-frame, and collapsing them into one field is what makes a 60-second
    quotation and a 59.99-second one indistinguishable in the ledger.
    """
    matched = TIMECODE_RE.match(value) if isinstance(value, str) else None
    if not matched:
        raise ValueError(f"rights row {ident}: {field} {value!r} is not a SMPTE timecode; the "
                         "form is HH:MM:SS:FF or HH:MM:SS;FF with a semicolon before the frames")
    hours, minutes, seconds, separator, frames = matched.groups()
    hours, minutes, seconds, frames = (int(part) for part in (hours, minutes, seconds, frames))
    if minutes > 59 or seconds > 59:
        raise ValueError(f"rights row {ident}: {field} {value!r} is not a time of day")
    if frames >= timebase:
        raise ValueError(f"rights row {ident}: {field} {value!r} counts to {frames} in a "
                         f"modulus of {timebase}; the frame number is the label's own unit and "
                         "a value at or above it is a carry nobody applied")

    index = ((hours * 60 + minutes) * 60 + seconds) * timebase + frames
    if separator == ";":
        drops = _drop_frames_per_minute(timebase, source_frame_rate)
        if not drops:
            raise ValueError(f"rights row {ident}: {field} {value!r} uses drop-frame notation "
                             f"(;) at an integral source_frame_rate {source_frame_rate}. "
                             "Drop-frame exists for the 1.001 ratios only; at this rate nothing "
                             "is dropped, so the semicolon is a claim about a count that does "
                             "not happen")
        whole_minutes = hours * 60 + minutes
        index -= drops * (whole_minutes - whole_minutes // 10)
    return index / source_frame_rate


def _check_type_table(required, kinds: dict) -> None:
    unbudgeted = [field for field in required if field not in kinds]
    stale = [name for name in kinds if name not in required]
    if unbudgeted or stale:
        raise ValueError(
            "archive.rights.required_fields and field_types disagree: "
            f"{unbudgeted} have no declared type, {stale} are typed but not required. A field "
            "validated by guesswork is validated by whoever remembers it, and defaulting to "
            "text silently inverts the two rules that read a boolean and a list")


def _stated(row: dict, field: str, kind: str, ident: str, swept: frozenset,
            placeholders: frozenset, none_values: frozenset):
    """One required field's value, refused by name if it is blank, the wrong kind, or a gap."""
    value = row[field]
    if kind in {"text", "url", "path", "date", "timecode"}:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"rights row {ident}: {field} must be a non-empty string, got "
                             f"{value!r}")
        if field in swept and _normalise(value) in placeholders:
            raise ValueError(f"rights row {ident}: {field} {value!r} is an unresolved "
                             "placeholder, which states less than a blank cell because it claims "
                             "somebody looked")
        return value.strip()
    if kind == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"rights row {ident}: {field} must be true or false, got {value!r}; "
                             "a blank here is a question about the master nobody answered")
        return value
    if kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"rights row {ident}: {field} must be an integer, got {value!r}")
        return value
    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise ValueError(f"rights row {ident}: {field} must be a positive number, got "
                             f"{value!r}")
        return float(value)
    if kind == "list":
        if not isinstance(value, list) or not all(
                isinstance(item, str) and item.strip() for item in value):
            raise ValueError(f"rights row {ident}: {field} must be a list of non-empty strings, "
                             f"got {value!r}; an entry that is blank documents nothing, and an "
                             "empty list is a declaration only where a basis imposes no duty")
        return [item.strip() for item in value]
    if kind == "none_or_list":
        if _normalise(value) in none_values:
            return "none"
        if isinstance(value, list) and value and all(
                isinstance(item, str) and item.strip() for item in value):
            return [item.strip() for item in value]
        raise ValueError(f"rights row {ident}: {field} must be an explicit "
                         f"{sorted(none_values)} or a non-empty list of what else is encumbered "
                         f"in the frame, got {value!r}. A rights-unknown row is a stop, not a "
                         "warning: an agency's clearance answers for the agency alone")
    raise ValueError(f"rights row {ident}: {field} declares the unknown type {kind!r}")


def ledger(episode: Path, contract: dict) -> dict[str, dict]:
    """The rights rows, keyed by id. No file is not a breach: an episode may carry no archive.

    Each row comes back carrying `span_seconds`, the real duration between its timecodes. The
    arithmetic belongs here because the fields it reads belong here, and the QC gate needs the
    measured seconds — not a second parser that could disagree with this one.
    """
    path = Path(episode) / paths(contract)["ledger_filename"]
    if not path.is_file():
        return {}
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"{path} must hold a JSON list of rights rows")

    rights = contract["archive"]["rights"]
    required = rights["required_fields"]
    kinds = rights["field_types"]
    bases = rights["rights_basis_enum"]
    banned = _query_names(contract)
    source_dir = paths(contract)["source_dir"]
    swept = frozenset(rights["placeholder_checked_fields"])
    placeholders = frozenset(_normalise(name) for name in rights["unresolved_placeholders"])
    none_values = frozenset(_normalise(name) for name in rights["third_party_none_values"])
    year_gated = rights["publication_year_floor_for_bases"]
    floor = int(rights["publication_year_floor"])
    duty_bases = rights["obligations_required_for_bases"]
    quote_bases = rights["quotation_ceiling_for_bases"]
    quote_ceiling = float(rights["fair_use_quotation_max_seconds"])

    _check_type_table(required, kinds)
    seen, by_id = set(), {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{path}: every rights row must be an object, got {type(row).__name__}")
        ident = str(row.get("id", "")).strip() or "?"
        absent = [field for field in required if field not in row]
        if absent:
            raise ValueError(f"rights row {ident} is missing {absent}; the contract lists "
                             f"{list(required)}")
        stated = {field: _stated(row, field, kinds[field], ident, swept, placeholders,
                                 none_values) for field in required}
        if ident in seen:
            raise ValueError(f"duplicate rights row id: {ident}")
        seen.add(ident)
        basis = row["rights_basis"]
        if basis not in bases:
            raise ValueError(f"rights row {ident} declares rights_basis {basis!r}, outside "
                             f"the contract enum {list(bases)}")
        for field in ("url", "retrieval_url"):
            _http_url(row[field], field, ident, banned)
        try:
            if date.fromisoformat(row["retrieved_date"]).isoformat() != row["retrieved_date"]:
                raise ValueError
        except ValueError:
            raise ValueError(f"rights row {ident} has retrieved_date "
                             f"{row['retrieved_date']!r}; an ISO date is required, because a "
                             "public-domain claim is only true as of a day") from None
        _relative_posix(row["file"], "file", ident)
        if not row["file"].startswith(source_dir.rstrip("/") + "/"):
            raise ValueError(f"rights row {ident} points at {row['file']!r}, outside the "
                             f"declared archival source directory {source_dir!r}")
        if basis == "fair_use_quotation" and not row["credit_line"].strip():
            raise ValueError(f"rights row {ident}: fair_use_quotation requires a credit_line, "
                             "which is both the on-screen source card and the evidence that the "
                             "quotation stays subordinate to our own narration")

        timebase = stated["timebase"]
        rate = stated["source_frame_rate"]
        if timebase < 1:
            raise ValueError(f"rights row {ident}: timebase {timebase} is not a frame modulus")
        if timebase > math.ceil(rate):
            raise ValueError(f"rights row {ident} labels at timebase {timebase} a source running "
                             f"at {rate} fps; that counts frames nobody recorded, so every span "
                             "and every in-point the row reports is a different frame")
        start = _timecode_seconds(row["in_timecode"], field="in_timecode", ident=ident,
                                 timebase=timebase, source_frame_rate=rate)
        end = _timecode_seconds(row["out_timecode"], field="out_timecode", ident=ident,
                               timebase=timebase, source_frame_rate=rate)
        span = end - start
        if span <= 0:
            raise ValueError(f"rights row {ident}: out_timecode {row['out_timecode']!r} is not "
                             f"after in_timecode {row['in_timecode']!r}; a record of a span that "
                             "did not happen documents no use")

        if basis in quote_bases and span > quote_ceiling:
            raise ValueError(f"rights row {ident}: a {basis} spans {span:.2f} s, over the "
                             f"contract ceiling {quote_ceiling} s. Past that length the use is "
                             "not a quotation that needs a credit_line, it is a different "
                             "argument, and this row has not made it")
        if basis in duty_bases and not stated["obligations"]:
            raise ValueError(f"rights row {ident}: {basis} grants use only on terms, and "
                             "obligations is empty. Recording the licence without the duty is "
                             "how a compliant file gets published non-compliantly")
        if basis in year_gated and stated["source_year"] > floor:
            raise ValueError(f"rights row {ident}: {basis} with source_year "
                             f"{stated['source_year']} is past the contract floor {floor}; the "
                             "term has not run, so the claim is not yet true")
        if stated["source_year"] > date.today().year:
            raise ValueError(f"rights row {ident}: source_year {stated['source_year']} is in the "
                             f"future (this run is {date.today().year}), so no record was made "
                             "in it")
        if not stated["uploaded_as_is"] and not stated["derivative_transformations"]:
            raise ValueError(f"rights row {ident} says uploaded_as_is false and lists no "
                             "derivative_transformations; one of the two is the claim the "
                             "viewer's file contradicts")
        if stated["uploaded_as_is"] and stated["derivative_transformations"]:
            raise ValueError(f"rights row {ident} says uploaded_as_is true while declaring "
                             f"{stated['derivative_transformations']}; the pair is the only "
                             "statement in the row about whether the file a viewer sees is the "
                             "file the archive holds")

        by_id[ident] = dict(row, span_seconds=span)
    return by_id


def records(episode: Path, contract: dict, *, required: bool = True) -> dict[str, dict]:
    """One record per archival shot, validated against the contract's enums.

    `required=False` asks the question the gate needs to ask first — does this episode have an
    archival layer at all — without turning its absence into a failure.
    """
    archive = contract["archive"]
    canvas_fps = float(contract["canvas"]["fps"])
    aspects = archive["archive_aspect"]["treatment_enum"]
    treatments = archive["cohesion"]["treatment_enum"]
    modes = archive["archive_motion"]["motion_mode_enum"]
    forms = archive["archive_motion"]["form_enum"]
    sides = archive["cohesion"]["light_direction"]["light_side_enum"]
    division = archive["division_of_labour"]
    carries_field = division["carries_field"]
    carries_archive = division["archive_carries"]
    carries_animation = division["animation_carries"]
    declared_paths = paths(contract)
    source_dir = declared_paths["source_dir"]
    records_name = declared_paths["records_filename"]
    ledger_name = declared_paths["ledger_filename"]

    path = Path(episode) / records_name
    if not path.is_file():
        if required:
            raise ValueError(f"{path} is missing; an episode with archival shots declares them "
                             f"in {records_name}")
        return {}
    declared = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(declared, dict):
        raise ValueError(f"{path} must hold a JSON object keyed by shot name")
    rows = ledger(episode, contract)

    out = {}
    for name, record in declared.items():
        if not isinstance(record, dict):
            raise ValueError(f"archival shot {name} is not an object in {path}")
        for field in ("asset", "licence", "form", "aspect", "treatment"):
            if not str(record.get(field, "")).strip():
                raise ValueError(f"archival shot {name} declares no {field}")
        # The animation-side answer is checked before the "outside the enum" one on purpose: a
        # clip that belongs to the animation is the contract's forbidden case, and reporting it as
        # an unknown token would hide the one refusal an editor actually needs to read.
        carries = str(record.get(carries_field, "")).strip()
        if not carries:
            raise ValueError(f"archival shot {name} declares no {carries_field}; the division of "
                             f"labour asks which of these the record is carrying: "
                             f"{list(carries_archive)}")
        if carries in carries_animation:
            raise ValueError(f"archival shot {name} declares {carries_field} {carries!r} - "
                             f"{carries_animation[carries]} - which is what the animation carries, "
                             f"not what the archive does. The contract forbids exactly this: "
                             f"{division['forbidden']}")
        if carries not in carries_archive:
            raise ValueError(f"archival shot {name} declares {carries_field} {carries!r}, outside "
                             f"the contract's {list(carries_archive)}")
        form = record["form"]
        if form not in forms:
            raise ValueError(f"archival shot {name} has form {form!r}, expected one of "
                             f"{list(forms)}")
        if record["aspect"] not in aspects:
            raise ValueError(f"archival shot {name} has aspect {record['aspect']!r}, outside "
                             f"the contract enum {list(aspects)}; the third state — an "
                             "accidental edge crop of a 4:3 frame — is the one the contract "
                             "rejects")
        if record["treatment"] not in treatments:
            raise ValueError(f"archival shot {name} has treatment {record['treatment']!r}, "
                             f"outside the contract enum {list(treatments)}")
        side = record.get("light_side")
        if side is not None and side not in sides:
            raise ValueError(f"archival shot {name} declares light_side {side!r}, expected one "
                             f"of {list(sides)}")

        asset = _relative_posix(record["asset"], "asset", name)
        if not asset.startswith(source_dir.rstrip("/") + "/"):
            raise ValueError(f"archival shot {name} reads {asset!r}, outside the declared "
                             f"archival source directory {source_dir!r}")

        row = rows.get(str(record["licence"]))
        if row is None:
            raise ValueError(f"archival shot {name} cites licence {record['licence']!r}, which "
                             f"is not a row in {ledger_name}; an archival shot with no "
                             "resolved rights row is not a warning, it is a stop")
        if row["file"] != asset:
            raise ValueError(f"archival shot {name} reads {asset!r} but rights row "
                             f"{row['id']} documents {row['file']!r}; the shot and its "
                             "documented rights have to be the same file")

        native = record.get("native_fps")
        if form == "clip":
            if native is None:
                raise ValueError(f"archival clip {name} declares no native_fps; the frame rate "
                                 "the container reports is a production fact, and guessing it "
                                 "is how the comic fast-walk tell ships")
            native = float(native)
            if native <= 0:
                raise ValueError(f"archival clip {name} declares native_fps {native}")
            if abs(native - canvas_fps) > 0.05 and record.get("motion_mode") not in modes:
                raise ValueError(f"archival clip {name} runs at {native} fps against a "
                                 f"{canvas_fps} fps canvas and declares no motion_mode; the "
                                 f"contract enum is {list(modes)} and undeclared is the only "
                                 "failure it names")
        elif native is not None:
            raise ValueError(f"archival still {name} declares native_fps {native}; a still has "
                             "no rate to reinterpret")
        if record.get("motion_mode") is not None and record["motion_mode"] not in modes:
            raise ValueError(f"archival shot {name} declares motion_mode "
                             f"{record['motion_mode']!r}, outside {list(modes)}")

        out[name] = dict(record, native_fps=native)
    return out
