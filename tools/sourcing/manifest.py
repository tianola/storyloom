"""Validation and purchase-state transitions for episode licence manifests."""

from datetime import date
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from urllib.parse import parse_qsl, urlsplit

FIELDS = {
    "id", "file", "kind", "provider", "asset_id", "url", "watermarked",
    "license_status", "license_type", "attribution", "shots", "downloaded_at", "notes",
}
KINDS = {"photo", "video", "music", "sfx", "screenshot"}
LICENSE_STATUSES = {"preview", "free", "purchased", "fair-dealing-review"}
LICENSE_TYPES = {"preview-comp", "CC0", "CC-BY", "CC-BY-SA", "PD", "editorial", "paid-standard"}
SHOT_ID = re.compile(r"s[0-9]{3}")


def _require_text(asset, field, *, allow_empty=False):
    value = asset[field]
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{field} must be {'a string' if allow_empty else 'a non-empty string'}")
    return value


def _validate_file(value):
    if "\\" in value or PureWindowsPath(value).drive:
        raise ValueError("file must be a repository-relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or not value or path.as_posix() != value:
        raise ValueError("file must be a repository-relative POSIX path")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("file must not contain unsafe path segments")


def validate_asset(asset: dict) -> dict:
    """Return a shallow copy after enforcing the exact section 5.1 schema."""
    if not isinstance(asset, dict) or set(asset) != FIELDS:
        raise ValueError("asset must contain exactly the licence-manifest fields")

    _require_text(asset, "id")
    file_value = _require_text(asset, "file")
    _validate_file(file_value)
    kind = _require_text(asset, "kind")
    _require_text(asset, "provider")
    _require_text(asset, "asset_id")
    url = _require_text(asset, "url")
    license_status = _require_text(asset, "license_status")
    license_type = _require_text(asset, "license_type")
    attribution = _require_text(asset, "attribution", allow_empty=True)
    notes = _require_text(asset, "notes", allow_empty=True)
    _require_text(asset, "downloaded_at")

    if kind not in KINDS:
        raise ValueError(f"unknown kind: {kind}")
    if license_status not in LICENSE_STATUSES:
        raise ValueError(f"unknown license_status: {license_status}")
    if license_type not in LICENSE_TYPES or "NC" in license_type.upper():
        raise ValueError(f"unknown or banned license_type: {license_type}")
    if not isinstance(asset["watermarked"], bool):
        raise ValueError("watermarked must be a boolean")
    parsed_url = urlsplit(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError("url must be an HTTP(S) source URL")
    if parsed_url.username or parsed_url.password:
        raise ValueError("url must not contain credentials")
    credential_parameters = {"api_key", "apikey", "key", "token", "access_token", "auth", "authorization"}
    query_parameters = {
        name.casefold().replace("-", "_")
        for name, _ in parse_qsl(parsed_url.query, keep_blank_values=True)
    }
    if query_parameters & credential_parameters:
        raise ValueError("url must not contain credential parameters")

    shots = asset["shots"]
    if not isinstance(shots, list) or any(not isinstance(shot, str) or not SHOT_ID.fullmatch(shot) for shot in shots):
        raise ValueError("shots must be a list of s[0-9]{3} shot IDs")
    downloaded_at = asset["downloaded_at"]
    try:
        if date.fromisoformat(downloaded_at).isoformat() != downloaded_at:
            raise ValueError("downloaded_at must be an ISO date")
    except (TypeError, ValueError) as exc:
        raise ValueError("downloaded_at must be an ISO date") from exc

    if license_type in {"CC-BY", "CC-BY-SA"} and not attribution.strip():
        raise ValueError(f"{license_type} requires attribution")
    if license_type == "editorial" and "editorial" not in notes.casefold():
        raise ValueError("editorial media requires explicit editorial context in notes")

    provider_key = re.sub(r"[^a-z0-9]", "", asset["provider"].casefold())
    remarc_providers = {"bbcremarc", "bbcremarcsoundeffects", "bbcsoundeffects", "bbcsoundeffectsremarc"}
    if provider_key in remarc_providers and kind in {"music", "sfx"} and license_status == "free":
        raise ValueError("BBC RemArc audio is not free for commercial use")
    return dict(asset)


def _load(path):
    assets = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(assets, list):
        raise ValueError("licence manifest must be a JSON list")
    seen = set()
    seen_provider_assets = set()
    for asset in assets:
        validate_asset(asset)
        key = asset["id"].casefold()
        if key in seen:
            raise ValueError(f"duplicate asset ID: {asset['id']}")
        seen.add(key)
        provider_key = (asset["provider"].casefold(), asset["asset_id"].casefold())
        if provider_key in seen_provider_assets:
            raise ValueError(f"duplicate provider asset ID: {asset['asset_id']}")
        seen_provider_assets.add(provider_key)
    return assets


def _write(path, assets):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(json.dumps(assets, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def append_asset(path: Path, asset: dict) -> dict:
    """Validate and append one asset without allowing ambiguous IDs."""
    candidate = validate_asset(asset)
    assets = _load(path)
    if any(existing["id"].casefold() == candidate["id"].casefold() for existing in assets):
        raise ValueError(f"duplicate asset ID: {candidate['id']}")
    if any(
        existing["provider"].casefold() == candidate["provider"].casefold()
        and existing["asset_id"].casefold() == candidate["asset_id"].casefold()
        for existing in assets
    ):
        raise ValueError(f"duplicate provider asset ID: {candidate['asset_id']}")
    assets.append(candidate)
    _write(path, assets)
    return candidate


def mark_purchased(path: Path, asset_id: str) -> dict:
    """Mark one preview purchased while retaining its clean-file destination."""
    assets = _load(path)
    key = asset_id.casefold()
    for index, asset in enumerate(assets):
        if asset["id"].casefold() != key:
            continue
        if asset["license_status"] != "preview":
            raise ValueError(f"asset is not a preview: {asset['id']}")
        updated = dict(asset)
        updated["license_status"] = "purchased"
        if asset["license_type"] == "preview-comp":
            updated["license_type"] = "paid-standard"
        updated["watermarked"] = False
        validate_asset(updated)
        assets[index] = updated
        _write(path, assets)
        return updated
    raise KeyError(asset_id)


def purchase_list(path: Path) -> list[dict]:
    """Return every still-used preview asset that blocks upload."""
    return [asset for asset in _load(path) if asset["license_status"] == "preview"]
