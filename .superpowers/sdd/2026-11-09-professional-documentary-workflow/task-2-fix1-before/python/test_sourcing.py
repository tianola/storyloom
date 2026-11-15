import json
import tempfile
import unittest
from pathlib import Path
from tools.sourcing.manifest import append_asset, mark_purchased, purchase_list, validate_asset

VALID = {
    "id": "a0001", "file": "assets/archival/carrington.jpg", "kind": "photo",
    "provider": "wikimedia", "asset_id": "File:Carrington_Richard_1859.jpg",
    "url": "https://commons.wikimedia.org/wiki/File:Carrington_Richard_1859.jpg",
    "watermarked": False, "license_status": "free", "license_type": "PD",
    "attribution": "", "shots": ["s012"], "downloaded_at": "2026-11-09", "notes": ""
}

class ManifestTests(unittest.TestCase):
    def test_rejects_noncommercial_and_missing_attribution(self):
        for license_type in ("CC-BY-NC", "CC-BY-NC-SA"):
            with self.subTest(license_type=license_type), self.assertRaises(ValueError):
                validate_asset({**VALID, "license_type": license_type})
        with self.assertRaises(ValueError):
            validate_asset({**VALID, "license_type": "CC-BY", "attribution": ""})

    def test_purchase_list_contains_only_preview_and_purchase_preserves_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "license-manifest.json"
            path.write_text("[]\n")
            preview = {**VALID, "license_status": "preview", "license_type": "preview-comp", "watermarked": True}
            append_asset(path, preview)
            self.assertEqual([a["id"] for a in purchase_list(path)], ["a0001"])
            updated = mark_purchased(path, "a0001")
            self.assertEqual(updated["file"], preview["file"])
            self.assertFalse(updated["watermarked"])
            self.assertEqual(purchase_list(path), [])

    def test_requires_exact_schema_and_valid_field_types(self):
        for field in VALID:
            with self.subTest(missing=field), self.assertRaises(ValueError):
                validate_asset({key: value for key, value in VALID.items() if key != field})
        with self.assertRaises(ValueError):
            validate_asset({**VALID, "unexpected": True})
        for field, value in (
            ("kind", "audio"), ("license_status", "unknown"),
            ("license_type", "CC-BY-NC-ND"), ("watermarked", "false"),
            ("shots", "s012"), ("downloaded_at", "2026-11-09T00:00:00"),
            ("url", "file:///tmp/carrington.jpg"),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_asset({**VALID, field: value})

    def test_rejects_credential_parameters_in_source_urls(self):
        for parameter in ("api_key", "apikey", "api-key", "key", "token", "access_token", "auth"):
            with self.subTest(parameter=parameter), self.assertRaises(ValueError):
                validate_asset({**VALID, "url": f"https://example.com/asset?{parameter}=not-a-real-credential"})

    def test_rejects_unsafe_paths_and_shot_ids(self):
        for file_value in (
            "/tmp/carrington.jpg", "C:/media/carrington.jpg",
            "assets\\archival\\carrington.jpg", "assets/../secret.jpg",
            "./assets/carrington.jpg", "",
        ):
            with self.subTest(file=file_value), self.assertRaises(ValueError):
                validate_asset({**VALID, "file": file_value})
        for shot in ("s12", "S012", "s012/../x", "../s012", "shot-12"):
            with self.subTest(shot=shot), self.assertRaises(ValueError):
                validate_asset({**VALID, "shots": [shot]})

    def test_rejects_case_insensitive_duplicate_ids_without_rewriting_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "license-manifest.json"
            path.write_text("[]\n", encoding="utf-8")
            append_asset(path, VALID)
            with self.assertRaises(ValueError):
                append_asset(path, {**VALID, "id": "A0001", "asset_id": "File:Other.jpg"})
            self.assertEqual(len(json.loads(path.read_text(encoding="utf-8"))), 1)

    def test_rejects_case_insensitive_duplicate_provider_asset_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "license-manifest.json"
            path.write_text("[]\n", encoding="utf-8")
            append_asset(path, VALID)
            with self.assertRaises(ValueError):
                append_asset(path, {
                    **VALID, "id": "a0002",
                    "asset_id": "file:carrington_richard_1859.jpg",
                })

    def test_enforces_editorial_context_and_remarc_paid_policy(self):
        editorial = {
            **VALID, "provider": "getty", "license_status": "preview",
            "license_type": "editorial", "watermarked": True, "notes": "",
        }
        with self.assertRaises(ValueError):
            validate_asset(editorial)
        validate_asset({**editorial, "notes": "Editorial context: historical news analysis of the depicted event."})
        remarc = {
            **VALID, "provider": "bbc-remarc", "kind": "sfx",
            "license_status": "free", "license_type": "CC0",
        }
        with self.assertRaises(ValueError):
            validate_asset(remarc)
        validate_asset({
            **remarc, "license_status": "preview", "license_type": "preview-comp",
            "watermarked": True, "notes": "Commercial licence required through Pro Sound Effects.",
        })

    def test_purchase_changes_only_gate_fields_and_preserves_editorial_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "license-manifest.json"
            path.write_text("[]\n", encoding="utf-8")
            paid = {
                **VALID, "license_status": "preview", "license_type": "preview-comp",
                "watermarked": True, "notes": "Replace with clean HD.",
            }
            append_asset(path, paid)
            updated = mark_purchased(path, "A0001")
            self.assertEqual(updated, {
                **paid, "license_status": "purchased", "license_type": "paid-standard",
                "watermarked": False,
            })

            editorial = {
                **VALID, "id": "a0002", "provider": "getty", "asset_id": "123",
                "license_status": "preview", "license_type": "editorial", "watermarked": True,
                "notes": "Editorial context: documentary reporting on a newsworthy historical event.",
            }
            append_asset(path, editorial)
            updated_editorial = mark_purchased(path, "a0002")
            self.assertEqual(updated_editorial["license_type"], "editorial")
            self.assertEqual(updated_editorial["file"], editorial["file"])
            with self.assertRaises(ValueError):
                mark_purchased(path, "a0002")


import hashlib
import io
import os
import subprocess
import sys
from unittest import mock
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request

from tools.sourcing.download import download_binary
from tools.sourcing.providers import (
    parse_internet_archive,
    parse_pexels,
    parse_wikimedia,
    search_internet_archive,
    search_pexels,
    search_wikimedia,
)


class FakeResponse:
    def __init__(self, chunks, final_url="https://example.com/media", error=None):
        self.chunks = list(chunks)
        self.final_url = final_url
        self.error = error
        self.read_sizes = []
        self.closed = False

    def read(self, size=-1):
        self.read_sizes.append(size)
        if size == -1:
            data = b"".join(self.chunks)
            self.chunks.clear()
            return data
        if self.chunks:
            return self.chunks.pop(0)
        if self.error is not None:
            raise self.error
        return b""

    def geturl(self):
        return self.final_url

    def close(self):
        self.closed = True


class DownloadTests(unittest.TestCase):
    def test_download_uses_timeout_chunks_and_atomic_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "nested/media.bin"
            response = FakeResponse([b"media"])
            calls = []

            def opener(url, timeout):
                calls.append((url, timeout))
                return response

            with self.assertLogs("tools.sourcing.download", level="INFO") as logs:
                result = download_binary("https://example.com/media", destination, opener=opener)
            self.assertEqual(result, destination)
            self.assertEqual(destination.read_bytes(), b"media")
            self.assertEqual(calls, [("https://example.com/media", 60)])
            self.assertEqual(response.read_sizes, [1024 * 1024, 1024 * 1024])
            self.assertTrue(response.closed)
            self.assertIn(hashlib.sha256(b"media").hexdigest(), "\n".join(logs.output))
            self.assertFalse(Path(str(destination) + ".partial").exists())

    def test_failed_chunk_leaves_no_destination_or_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "media.bin"
            response = FakeResponse([b"media"], error=OSError("connection lost"))
            with self.assertRaisesRegex(OSError, "connection lost"):
                download_binary("https://example.com/media", destination, opener=lambda url, timeout: response)
            self.assertFalse(destination.exists())
            self.assertFalse(Path(str(destination) + ".partial").exists())
            self.assertTrue(response.closed)

    def test_existing_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "media.bin"
            destination.write_bytes(b"original")
            opened = False

            def opener(url, timeout):
                nonlocal opened
                opened = True
                return FakeResponse([b"replacement"])

            with self.assertRaises(FileExistsError):
                download_binary("https://example.com/media", destination, opener=opener)
            self.assertFalse(opened)
            self.assertEqual(destination.read_bytes(), b"original")
            self.assertFalse(Path(str(destination) + ".partial").exists())

    def test_rejects_unsafe_initial_and_redirect_schemes(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "media.bin"
            with self.assertRaises(ValueError):
                download_binary("ftp://example.com/media", destination, opener=lambda url, timeout: self.fail("opened"))
            response = FakeResponse([b"media"], final_url="file:///etc/passwd")
            with self.assertRaises(ValueError):
                download_binary("https://example.com/media", destination, opener=lambda url, timeout: response)
            self.assertFalse(destination.exists())
            self.assertFalse(Path(str(destination) + ".partial").exists())

    def test_enforces_explicit_maximum_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "media.bin"
            response = FakeResponse([b"12345"])
            with self.assertRaisesRegex(ValueError, "maximum"):
                download_binary(
                    "https://example.com/media", destination,
                    opener=lambda url, timeout: response, max_bytes=4,
                )
            self.assertFalse(destination.exists())
            self.assertFalse(Path(str(destination) + ".partial").exists())


WIKIMEDIA_PAYLOAD = {
    "batchcomplete": "",
    "query": {"pages": [{
        "pageid": 123, "ns": 6, "title": "File:Carrington Richard 1859.jpg",
        "imagerepository": "local",
        "imageinfo": [{
            "timestamp": "2020-01-01T00:00:00Z", "user": "Archivist",
            "size": 2000, "width": 1600, "height": 1000,
            "url": "https://upload.wikimedia.org/carrington-full.jpg",
            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Carrington_Richard_1859.jpg",
            "thumburl": "https://upload.wikimedia.org/thumb/carrington.jpg",
            "thumbwidth": 1280, "thumbheight": 800,
            "extmetadata": {
                "LicenseShortName": {"value": "CC BY-SA 4.0", "source": "commons-desc"},
                "Artist": {"value": "<span>Richard Carrington</span>"},
                "Credit": {"value": "Royal Astronomical Society"},
                "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0/"},
                "UsageTerms": {"value": "Creative Commons Attribution-Share Alike 4.0"},
            },
        }],
    }]},
}

INTERNET_ARCHIVE_PAYLOAD = {
    "responseHeader": {"status": 0, "QTime": 1, "params": {"q": "Carrington telegraph", "rows": "5"}},
    "response": {"numFound": 1, "start": 0, "docs": [{
        "identifier": "carrington-telegraph-1859", "title": "Carrington telegraph",
        "description": "Archival telegraph footage", "mediatype": "movies",
        "creator": ["Archive"], "date": "1859", "year": 1859,
        "licenseurl": "https://creativecommons.org/publicdomain/mark/1.0/",
    }]},
}

PEXELS_PAYLOAD = {
    "page": 1, "per_page": 5, "total_results": 1,
    "next_page": "https://api.pexels.com/v1/search?page=2",
    "photos": [{
        "id": 456, "width": 1920, "height": 1080,
        "url": "https://www.pexels.com/photo/solar-storm-456/",
        "photographer": "Solar Photographer",
        "photographer_url": "https://www.pexels.com/@solar", "photographer_id": 99,
        "avg_color": "#000000",
        "src": {
            "original": "https://images.pexels.com/photos/456/original.jpg",
            "large2x": "https://images.pexels.com/photos/456/large2x.jpg",
            "large": "https://images.pexels.com/photos/456/large.jpg",
            "medium": "https://images.pexels.com/photos/456/medium.jpg",
            "small": "https://images.pexels.com/photos/456/small.jpg",
            "portrait": "https://images.pexels.com/photos/456/portrait.jpg",
            "landscape": "https://images.pexels.com/photos/456/landscape.jpg",
            "tiny": "https://images.pexels.com/photos/456/tiny.jpg",
        },
        "liked": False, "alt": "Solar storm over a landscape",
    }],
}


class ProviderTests(unittest.TestCase):
    def assert_normalized(self, result, provider):
        for key in ("provider", "asset_id", "url", "preview_url", "kind", "license_review"):
            self.assertIn(key, result)
        self.assertEqual(result["provider"], provider)
        self.assertTrue(result["asset_id"])
        self.assertTrue(result["url"].startswith("https://"))
        self.assertTrue(result["preview_url"].startswith("https://"))
        self.assertTrue(result["license_review"]["required"])
        self.assertIn("name", result["license_review"])
        self.assertIn("attribution", result["license_review"])

    def test_provider_parser_fixtures_normalize_review_metadata(self):
        wikimedia = parse_wikimedia(WIKIMEDIA_PAYLOAD)[0]
        self.assert_normalized(wikimedia, "wikimedia")
        self.assertEqual(wikimedia["asset_id"], "File:Carrington Richard 1859.jpg")
        self.assertEqual(wikimedia["preview_url"], "https://upload.wikimedia.org/thumb/carrington.jpg")
        self.assertEqual(wikimedia["license_review"]["attribution"], "Richard Carrington")

        archive = parse_internet_archive(INTERNET_ARCHIVE_PAYLOAD)[0]
        self.assert_normalized(archive, "internet-archive")
        self.assertEqual(archive["asset_id"], "carrington-telegraph-1859")
        self.assertEqual(archive["url"], "https://archive.org/details/carrington-telegraph-1859")
        self.assertEqual(archive["kind"], "video")

        pexels = parse_pexels(PEXELS_PAYLOAD)[0]
        self.assert_normalized(pexels, "pexels")
        self.assertEqual(pexels["asset_id"], "456")
        self.assertEqual(pexels["preview_url"], "https://images.pexels.com/photos/456/large.jpg")

    def test_provider_searches_use_mocked_http_and_never_persist_pexels_key(self):
        cases = (
            ("wikimedia", WIKIMEDIA_PAYLOAD, search_wikimedia, "gsrlimit"),
            ("internet-archive", INTERNET_ARCHIVE_PAYLOAD, search_internet_archive, "rows"),
            ("pexels", PEXELS_PAYLOAD, search_pexels, "per_page"),
        )
        secret = "unit-test-only-not-a-credential"
        for provider, payload, search, limit_parameter in cases:
            with self.subTest(provider=provider):
                seen = []

                def opener(request, timeout):
                    seen.append((request, timeout))
                    return FakeResponse([json.dumps(payload).encode("utf-8")], final_url=request.full_url)

                with mock.patch.dict(os.environ, {"PEXELS_API_KEY": secret}):
                    results = search("Carrington event", limit=5, opener=opener)
                self.assertEqual(len(results), 1)
                request, timeout = seen[0]
                self.assertIsInstance(request, Request)
                self.assertEqual(timeout, 60)
                query = parse_qs(urlsplit(request.full_url).query)
                self.assertEqual(query[limit_parameter], ["5"])
                self.assertEqual(query["query" if provider == "pexels" else "q" if provider == "internet-archive" else "gsrsearch"], ["Carrington event"])
                self.assertNotIn(secret, request.full_url)
                self.assertNotIn(secret, json.dumps(results))
                if provider == "pexels":
                    self.assertEqual(request.get_header("Authorization"), secret)

    def test_pexels_requires_environment_key_at_call_time_and_cli_is_clear(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "PEXELS_API_KEY is required"):
                search_pexels("solar storm", opener=lambda request, timeout: self.fail("network opened"))

        repo = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env.pop("PEXELS_API_KEY", None)
        completed = subprocess.run(
            [sys.executable, "-m", "tools.sourcing.providers", "pexels", "solar storm", "--limit", "5"],
            cwd=repo, env=env, capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("PEXELS_API_KEY is required", completed.stdout + completed.stderr)


class ManifestReportTests(unittest.TestCase):
    def run_report(self, episode):
        return subprocess.run(
            [sys.executable, "tools/manifest_report.py", "--episode", str(episode)],
            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=False,
        )

    def test_report_groups_previews_and_blocks_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = Path(tmp)
            (episode / "assets").mkdir()
            manifest = episode / "assets/license-manifest.json"
            manifest.write_text("[]\n", encoding="utf-8")
            first = {
                **VALID, "provider": "wikimedia", "license_status": "preview",
                "license_type": "preview-comp", "watermarked": True, "notes": "Replace with clean HD.",
            }
            second = {
                **VALID, "id": "a0002", "provider": "shutterstock", "asset_id": "98765",
                "file": "assets/stock/storm.jpg", "url": "https://www.shutterstock.com/image/98765",
                "license_status": "preview", "license_type": "preview-comp", "watermarked": True,
                "shots": ["s020", "s021"], "notes": "Purchase standard licence.",
            }
            append_asset(manifest, first)
            append_asset(manifest, second)
            append_asset(manifest, {**VALID, "id": "a0003", "asset_id": "File:Free.jpg"})

            completed = self.run_report(episode)
            self.assertEqual(completed.returncode, 1, completed.stderr)
            self.assertEqual(completed.stdout.strip(), "UPLOAD BLOCKED: 2 preview assets")
            report = (episode / "dist/license-purchase-list.md").read_text(encoding="utf-8")
            self.assertLess(report.index("## shutterstock"), report.index("## wikimedia"))
            for text in (
                "a0001", "File:Carrington_Richard_1859.jpg", first["url"], first["file"],
                "s012", "Replace with clean HD.", "a0002", "98765", "s020, s021",
            ):
                self.assertIn(text, report)
            self.assertNotIn("File:Free.jpg", report)

    def test_report_clears_upload_gate_when_no_previews_remain(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = Path(tmp)
            (episode / "assets").mkdir()
            manifest = episode / "assets/license-manifest.json"
            manifest.write_text("[]\n", encoding="utf-8")
            append_asset(manifest, VALID)
            completed = self.run_report(episode)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stdout.strip(), "LICENSE GATE CLEAR")
            self.assertTrue((episode / "dist/license-purchase-list.md").is_file())


if __name__ == "__main__":
    unittest.main()
