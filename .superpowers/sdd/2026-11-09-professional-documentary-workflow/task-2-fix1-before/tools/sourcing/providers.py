"""Search adapters for Wikimedia Commons, Internet Archive, and Pexels."""

import argparse
from html import unescape
from html.parser import HTMLParser
import json
import os
import re
import sys
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

TIMEOUT_SECONDS = 60
USER_AGENT = "LongformDocumentarySourcing/1.0"


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _plain_text(value):
    if isinstance(value, dict):
        value = value.get("value", "")
    parser = _TextParser()
    parser.feed(str(value or ""))
    return unescape("".join(parser.parts)).strip()


def _noncommercial(*values):
    text = " ".join(str(value).casefold() for value in values)
    return bool(re.search(r"(?:by[ -]?nc|/by-nc)", text))


def _review(name, *, url="", attribution="", noncommercial=False):
    return {
        "required": True,
        "name": name or "Unspecified",
        "url": url,
        "attribution": attribution,
        "noncommercial": noncommercial,
    }


def parse_wikimedia(payload: dict) -> list[dict]:
    pages = payload.get("query", {}).get("pages", [])
    if isinstance(pages, dict):
        pages = list(pages.values())
    results = []
    for page in pages:
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        metadata = info.get("extmetadata", {})
        license_name = _plain_text(metadata.get("LicenseShortName") or metadata.get("UsageTerms"))
        license_url = _plain_text(metadata.get("LicenseUrl"))
        artist = _plain_text(metadata.get("Artist")) or _plain_text(metadata.get("Credit"))
        results.append({
            "provider": "wikimedia",
            "asset_id": str(page["title"]),
            "url": info.get("descriptionurl") or info["url"],
            "preview_url": info.get("thumburl") or info["url"],
            "kind": "photo",
            "license_review": _review(
                license_name, url=license_url, attribution=artist,
                noncommercial=_noncommercial(license_name, license_url),
            ),
        })
    return results


def parse_internet_archive(payload: dict) -> list[dict]:
    results = []
    kinds = {"movies": "video", "audio": "music", "texts": "screenshot", "image": "photo"}
    for document in payload.get("response", {}).get("docs", []):
        identifier = str(document["identifier"])
        license_url = str(document.get("licenseurl") or "")
        creator = document.get("creator") or ""
        if isinstance(creator, list):
            creator = ", ".join(str(value) for value in creator)
        results.append({
            "provider": "internet-archive",
            "asset_id": identifier,
            "url": f"https://archive.org/details/{identifier}",
            "preview_url": f"https://archive.org/services/img/{identifier}",
            "kind": kinds.get(document.get("mediatype"), "photo"),
            "license_review": _review(
                license_url or "Unspecified", url=license_url, attribution=str(creator),
                noncommercial=_noncommercial(license_url),
            ),
        })
    return results


def parse_pexels(payload: dict) -> list[dict]:
    results = []
    for photo in payload.get("photos", []):
        sources = photo.get("src", {})
        results.append({
            "provider": "pexels",
            "asset_id": str(photo["id"]),
            "url": photo["url"],
            "preview_url": sources.get("large") or sources.get("medium") or sources["original"],
            "kind": "photo",
            "license_review": _review(
                "Pexels License", url="https://www.pexels.com/license/",
                attribution=f"Photo by {photo.get('photographer', 'Pexels contributor')} on Pexels",
            ),
        })
    return results


def _open_json(request: Request, opener):
    response = opener(request, timeout=TIMEOUT_SECONDS)
    try:
        final_url = response.geturl() if hasattr(response, "geturl") else request.full_url
        if urlsplit(final_url).scheme not in {"http", "https"}:
            raise ValueError("provider redirected to a non-HTTP(S) URL")
        return json.loads(response.read().decode("utf-8"))
    finally:
        close = getattr(response, "close", None)
        if close is not None:
            close()


def _request(url, headers=None):
    return Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT, **(headers or {})})


def search_wikimedia(query: str, limit: int = 5, opener=urlopen) -> list[dict]:
    parameters = {
        "action": "query", "format": "json", "formatversion": "2",
        "generator": "search", "gsrsearch": query, "gsrnamespace": "6", "gsrlimit": str(limit),
        "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": "1280",
    }
    url = "https://commons.wikimedia.org/w/api.php?" + urlencode(parameters)
    return parse_wikimedia(_open_json(_request(url), opener))


def search_internet_archive(query: str, limit: int = 5, opener=urlopen) -> list[dict]:
    parameters = {
        "q": query, "fl[]": ["identifier", "title", "mediatype", "licenseurl", "creator"],
        "rows": str(limit), "page": "1", "output": "json",
    }
    url = "https://archive.org/advancedsearch.php?" + urlencode(parameters, doseq=True)
    return parse_internet_archive(_open_json(_request(url), opener))


def search_pexels(query: str, limit: int = 5, opener=urlopen) -> list[dict]:
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        raise ValueError("PEXELS_API_KEY is required")
    parameters = {"query": query, "per_page": str(limit), "page": "1"}
    url = "https://api.pexels.com/v1/search?" + urlencode(parameters)
    request = _request(url, {"Authorization": api_key})
    return parse_pexels(_open_json(request, opener))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Search supported media providers without storing credentials.")
    subparsers = parser.add_subparsers(dest="provider", required=True)
    for provider in ("wikimedia", "internet-archive", "pexels"):
        command = subparsers.add_parser(provider)
        command.add_argument("query")
        command.add_argument("--limit", type=int, default=5)
    args = parser.parse_args(argv)
    if args.provider == "pexels" and not os.environ.get("PEXELS_API_KEY"):
        print("PEXELS_API_KEY is required", file=sys.stderr)
        return 2
    searches = {
        "wikimedia": search_wikimedia,
        "internet-archive": search_internet_archive,
        "pexels": search_pexels,
    }
    results = searches[args.provider](args.query, limit=args.limit)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
