import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflow.config import style_contract  # noqa: E402
from tools.sourcing.manifest import append_asset, mark_purchased, purchase_list, validate_asset  # noqa: E402

CONTRACT = style_contract(ROOT)
SOURCING = CONTRACT["archive"]["sourcing"]

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
import threading
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock
from urllib.parse import parse_qs, urlsplit
from urllib.request import FTPHandler, Request
from urllib.response import addinfourl

from tools.sourcing import providers, transport
from tools.sourcing.download import download_binary


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


class QuietHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def start_local_server(test_case, handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    test_case.addCleanup(thread.join)
    test_case.addCleanup(server.server_close)
    test_case.addCleanup(server.shutdown)
    return f"http://127.0.0.1:{server.server_port}"


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
            self.assertEqual(result, hashlib.sha256(b"media").hexdigest())
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

    def test_rejects_ftp_redirect_before_opening_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "media.bin"
            target_url = "ftp://example.invalid/media.bin"
            redirect_paths = []

            class RedirectHandler(QuietHandler):
                def do_GET(self):
                    redirect_paths.append(self.path)
                    self.send_response(302)
                    self.send_header("Location", target_url)
                    self.end_headers()

            initial_url = start_local_server(self, RedirectHandler) + "/start"
            opened_targets = []

            def ftp_open(handler, request):
                opened_targets.append(request.full_url)
                return addinfourl(io.BytesIO(b"disallowed"), Message(), request.full_url)

            with mock.patch.object(FTPHandler, "ftp_open", ftp_open):
                with self.assertRaisesRegex(ValueError, "HTTP"):
                    download_binary(initial_url, destination)

            self.assertEqual(redirect_paths, ["/start"])
            self.assertEqual(opened_targets, [])
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

NASA_PAYLOAD = {
    "collection": {"items": [{
        "data": [{
            "nasa_id": "artemis-ii-apollo-17", "title": "Apollo 17 launch",
            "date_created": "1972-12-07", "photographer": "NASA",
            "media_type": "video", "keywords": ["launch", "rc_a2300"],
        }],
        "links": [
            {"rel": "preview", "href": "https://images-assets.nasa.gov/video/preview.jpg"},
            {"rel": "canonical", "href": "https://images-assets.nasa.gov/video/master.mp4"},
        ],
    }]},
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

    def fake_opener(self, payload, calls):
        def opener(request, timeout):
            calls.append((request, timeout))
            return FakeResponse([json.dumps(payload).encode("utf-8")], final_url=request.full_url)

        return opener

    def test_the_dispatcher_normalises_each_provider_from_the_contract(self):
        """The same shape, read from the contract: no per-provider parser is left to call."""
        cases = (
            ("wikimedia", WIKIMEDIA_PAYLOAD, "File:Carrington Richard 1859.jpg",
             "https://upload.wikimedia.org/thumb/carrington.jpg", "Richard Carrington", "photo",
             "extmetadata.LicenseShortName"),
            ("internet-archive", INTERNET_ARCHIVE_PAYLOAD, "carrington-telegraph-1859",
             "https://archive.org/services/img/carrington-telegraph-1859", "Archive", "video",
             "licenseurl"),
            ("nasa", NASA_PAYLOAD, "artemis-ii-apollo-17",
             "https://images-assets.nasa.gov/video/preview.jpg", "NASA", "video", "nasa_id"),
        )
        for provider, payload, asset_id, preview_url, attribution, kind, evidence_leaf in cases:
            with self.subTest(provider=provider):
                result = providers.parse(provider, payload, contract=CONTRACT)[0]
                self.assert_normalized(result, provider)
                self.assertEqual(result["asset_id"], asset_id)
                self.assertEqual(result["preview_url"], preview_url)
                self.assertEqual(result["license_review"]["attribution"], attribution)
                self.assertEqual(result["kind"], kind)
                self.assertIn(evidence_leaf, result["evidence"][0]["field_path"])
                self.assertTrue(result["evidence"][0]["raw_value"])

    def test_the_internet_archive_page_url_comes_from_the_contract_template(self):
        result = providers.parse("internet-archive", INTERNET_ARCHIVE_PAYLOAD, contract=CONTRACT)[0]
        self.assertEqual(result["url"], "https://archive.org/details/carrington-telegraph-1859")

    def test_provider_searches_use_mocked_http_and_never_a_credential(self):
        cases = (
            ("wikimedia", WIKIMEDIA_PAYLOAD, "gsrlimit", "gsrsearch"),
            ("internet-archive", INTERNET_ARCHIVE_PAYLOAD, "rows", "q"),
            ("nasa", NASA_PAYLOAD, "page_size", "q"),
        )
        for provider, payload, limit_parameter, query_parameter in cases:
            with self.subTest(provider=provider):
                seen = []

                def opener(request, timeout):
                    seen.append((request, timeout))
                    return FakeResponse([json.dumps(payload).encode("utf-8")],
                                        final_url=request.full_url)

                results = providers.search(provider, "Carrington event", limit=5,
                                           opener=opener, contract=CONTRACT)
                self.assertEqual(len(results), 1)
                request, timeout = seen[0]
                self.assertIsInstance(request, Request)
                self.assertEqual(timeout, 60)
                query = parse_qs(urlsplit(request.full_url).query)
                self.assertEqual(query[limit_parameter], ["5"])
                self.assertEqual(query[query_parameter], ["Carrington event"])
                self.assertIsNone(request.get_header("Authorization"))
                self.assertEqual(request.get_header("User-agent"), SOURCING["user_agent"])
                self.assertEqual(transport.host_of(request.full_url),
                                 urlsplit(SOURCING["providers"][provider]["search_endpoint"]).hostname)

    def test_an_unexpected_response_shape_is_not_read_as_an_empty_result(self):
        """A wrong `fl[]` list echoes back JSON with no docs; `transport.check_payload` says so."""
        entry = providers.provider_entry("internet-archive", contract=CONTRACT)
        with self.assertRaises(transport.RequestShapeError):
            transport.check_payload({"nothing": "here"}, entry, what="internet-archive search")
        self.assertEqual(providers.parse("internet-archive", {"response": {"numFound": 0, "docs": []}},
                                        contract=CONTRACT), [])

    def test_a_noncommercial_licence_is_flagged_by_the_contract_rules(self):
        """Prelinger is not blanket PD: a by-nc-sa `licenseurl` must not read as clean.

        Both directions are pinned, because a matcher that always says yes and one that always
        says no both pass a one-sided test.
        """
        cases = (
            ("https://creativecommons.org/licenses/by-nc-sa/2.0/", True),
            ("https://creativecommons.org/publicdomain/mark/1.0/", False),
            ("https://rightsstatements.org/vocab/NoC-US/1.0/", False),
        )
        for licence_url, expected in cases:
            with self.subTest(licence_url=licence_url):
                payload = {"response": {"docs": [{
                    "identifier": "prelinger-film-1952", "mediatype": "movies",
                    "licenseurl": licence_url,
                }]}}
                result = providers.parse("internet-archive", payload, contract=CONTRACT)[0]
                self.assertEqual(result["license_review"]["noncommercial"], expected)
                self.assertEqual(result["evidence"][0]["raw_value"], licence_url)

    def test_the_commons_machine_licence_token_is_the_primary_evidence(self):
        """`License` decides first and `LicenseShortName` is only the fallback (#149 fact 3)."""
        payload = {"query": {"pages": [{
            "title": "File:Apollo 17.jpg", "ns": 6,
            "imageinfo": [{"descriptionurl": "https://commons.example/Apollo_17",
                          "extmetadata": {
                              "LicenseShortName": {"value": "Public domain"},
                              "License": {"value": "CC BY-NC 4.0"},
                          }}],
        }]}}
        result = providers.parse("wikimedia", payload, contract=CONTRACT)[0]
        self.assertEqual(result["evidence"][0]["field_path"],
                         "imageinfo.0.extmetadata.License")
        self.assertTrue(result["license_review"]["noncommercial"])

    def test_an_unknown_provider_is_refused_by_name(self):
        """No fall-through to a default: a provider the contract does not carry is an error."""
        def opener(request, timeout):
            raise AssertionError("an unknown provider still reached the network")

        with self.assertRaisesRegex(providers.ProviderUnavailable, "gettyimages"):
            providers.search("gettyimages", "apollo", opener=opener, contract=CONTRACT)

    def test_a_disabled_provider_is_refused_by_name(self):
        contract = json.loads(json.dumps(CONTRACT))
        contract["archive"]["sourcing"]["providers"]["nasa"]["enabled"] = False

        def opener(request, timeout):
            raise AssertionError("a disabled provider still reached the network")

        with self.assertRaisesRegex(providers.ProviderUnavailable, "nasa"):
            providers.search("nasa", "apollo", opener=opener, contract=contract)

    def test_the_declared_field_list_and_maxlag_travel_in_the_query(self):
        cases = ("internet-archive", "wikimedia")
        for provider in cases:
            with self.subTest(provider=provider):
                seen = []

                def opener(request, timeout):
                    seen.append(request.full_url)
                    return FakeResponse([b"{}"], final_url=request.full_url)

                providers.search(provider, "apollo", limit=1, opener=opener, contract=CONTRACT)
                query = parse_qs(urlsplit(seen[0]).query, keep_blank_values=True)
                entry = SOURCING["providers"][provider]
                if entry.get("fields_param"):
                    self.assertEqual(query[entry["fields_param"]], entry["fields"])
                if entry.get("sends_maxlag"):
                    self.assertEqual(query[SOURCING["transport"]["maxlag_parameter"]],
                                     [str(SOURCING["transport"]["maxlag_value"])])

    def test_search_hands_the_provider_interval_to_the_shared_retry_helper(self):
        """Etiquette is one mechanism: the declared spacing reaches `retry_call`, not a sleep here."""
        seen = []
        original = transport.retry_call

        def spy(invoke, **kwargs):
            seen.append(kwargs)
            return original(invoke, **kwargs)

        self.addCleanup(setattr, transport, "retry_call", original)
        transport.retry_call = spy
        providers.search("wikimedia", "apollo", limit=1,
                         opener=lambda request, timeout: FakeResponse([b"{}"], final_url=request.full_url),
                         contract=CONTRACT, sleep=lambda seconds: None)
        transport.retry_call = spy
        providers.search("internet-archive", "apollo", limit=1,
                         opener=lambda request, timeout: FakeResponse([b"{}"], final_url=request.full_url),
                         contract=CONTRACT, sleep=lambda seconds: None)
        self.assertEqual([call["channel"] for call in seen], ["json", "json"])
        self.assertEqual([call["min_interval_seconds"] for call in seen],
                         [SOURCING["providers"]["wikimedia"]["min_interval_seconds"],
                          SOURCING["providers"]["internet-archive"]["min_interval_seconds"]])
        self.assertTrue(all(call.get("state") is not None for call in seen),
                        "min_interval_seconds is a promise only a shared state can keep")

    def test_the_cli_refuses_a_provider_the_contract_does_not_offer(self):
        completed = subprocess.run(
            [sys.executable, "-m", "tools.sourcing.providers", "gettyimages", "apollo",
             "--limit", "1"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(completed.returncode, 2, completed.stderr)
        self.assertIn("gettyimages", completed.stdout + completed.stderr)


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
