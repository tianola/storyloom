"""Task #149 Deliverable 3 — transport: the digest, one shared retry, one cache.

The brief is specific about what is broken today: `download_binary` digests every chunk it writes
and then *logs* the digest, so the ledger would record what the provider claimed rather than what
landed; and neither `_open_url` nor `_open_json` retries anything, so a 429 from Commons — which
the research measured at over ~1 request a second — is a crash rather than a wait.

Every rule here is a number the contract owns, and each test reads the same block the production
code does, so revising a bound is an edit to `workflow/style.json` and never a test edit.
"""
import ast
import hashlib
import json
import sys
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from workflow.config import style_contract  # noqa: E402
from tools.sourcing import download as D  # noqa: E402
from tools.sourcing import providers as P  # noqa: E402
from tools.sourcing import transport as T  # noqa: E402

CONTRACT = style_contract(ROOT)
SOURCING = CONTRACT["archive"]["sourcing"]
POLICY = SOURCING["transport"]


def http_error(code, url="https://commons.wikimedia.org/w/api.php", headers=None):
    message = Message()
    for name, value in (headers or {}).items():
        message[name] = value
    return HTTPError(url, code, f"status {code}", message, None)


def fake_response(payload, final_url="https://example.invalid/x.json"):
    return FakeBinary([json.dumps(payload).encode("utf-8")], final_url=final_url)


class FakeBinary:
    """A response object shaped like the one download_binary and _open_json already accept."""

    def __init__(self, chunks, final_url="https://example.invalid/media.bin", error=None):
        self.chunks = list(chunks)
        self.final_url = final_url
        self.error = error
        self.closed = False

    def read(self, size=-1):
        if self.chunks:
            return self.chunks.pop(0)
        if self.error is not None:
            raise self.error
        return b""

    def geturl(self):
        return self.final_url

    def close(self):
        self.closed = True


class Recorder:
    """Injected clock / sleep / rng, so a retry test measures policy instead of wall time."""

    def __init__(self, now=1000.0, jitter=0.5):
        self.now = now
        self.slept = []
        self.clock_calls = 0
        self.jitter = jitter

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds

    def monotonic(self):
        self.clock_calls += 1
        return self.now

    def random(self):
        return self.jitter


class DigestTests(unittest.TestCase):
    def test_download_returns_the_sha256_of_the_bytes_that_landed(self):
        payload = b"archive footage bytes"
        expected = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "media.bin"
            result = D.download_binary("https://example.invalid/m", destination,
                                       opener=lambda url, timeout: FakeBinary([payload]))
            self.assertEqual(result, expected,
                             "download_binary must hand back the digest it computed")

    def test_download_writes_a_sidecar_named_from_the_contract(self):
        suffix = POLICY["sidecar_suffix"]
        payload = b"archive footage bytes"
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "media.bin"
            digest = D.download_binary("https://example.invalid/m", destination,
                                       opener=lambda url, timeout: FakeBinary([payload]))
            sidecar = Path(str(destination) + suffix)
            self.assertTrue(sidecar.is_file(), f"{sidecar} was never written")
            self.assertEqual(sidecar.read_text(encoding="utf-8").strip(), digest)

    def test_a_partial_download_leaves_no_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "media.bin"
            broken = FakeBinary([b"half"], error=OSError("connection lost"))
            with self.assertRaises(OSError):
                D.download_binary("https://example.invalid/m", destination,
                                  opener=lambda url, timeout: broken)
            self.assertFalse(Path(str(destination) + POLICY["sidecar_suffix"]).exists())
            self.assertFalse(destination.exists())
            self.assertFalse(Path(str(destination) + ".partial").exists())

    def test_reading_a_sidecar_back_recomputes_the_bytes_and_refuses_a_lie(self):
        payload = b"what the provider sent"
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "media.bin"
            D.download_binary("https://example.invalid/m", destination,
                              opener=lambda url, timeout: FakeBinary([payload]))
            self.assertEqual(D.read_digest(destination, CONTRACT), hashlib.sha256(payload).hexdigest())
            destination.write_bytes(b"what reached the disk instead")
            with self.assertRaisesRegex(ValueError, "sha256"):
                D.read_digest(destination, CONTRACT)

    def test_a_digest_the_provider_published_is_compared_not_trusted(self):
        """§7.2: IA publishes md5/sha1/crc32 per file; disagreeing bytes are a refusal."""
        payload = b"the bytes that landed"
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "media.bin"
            digest = D.download_binary("https://example.invalid/m", destination,
                                       opener=lambda url, timeout: FakeBinary([payload]))
            self.assertTrue(D.digest_matches(destination, digest, CONTRACT))
            self.assertFalse(D.digest_matches(destination, "0" * 64, CONTRACT))


class SharedRetryTests(unittest.TestCase):
    def test_the_retry_helper_is_the_one_both_openers_call(self):
        seen = []
        original = T.retry_call

        def spy(invoke, **kwargs):
            seen.append(kwargs.get("channel", "?"))
            return original(invoke, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            payload = b"bytes"
            self.addCleanup(setattr, T, "retry_call", original)
            T.retry_call = spy
            P._open_json(P._request("https://example.invalid/api"),
                         opener=lambda request, timeout: fake_response({}), contract=CONTRACT)
            D.download_binary("https://example.invalid/m", Path(tmp) / "m.bin",
                              opener=lambda url, timeout: FakeBinary([payload]), contract=CONTRACT)
        self.assertEqual(sorted(seen), sorted(["json", "binary"]),
                         "one retry helper, shared by both openers")

    def test_the_backoff_ladder_is_exactly_as_long_as_the_declared_retries(self):
        self.assertEqual(len(POLICY["backoff_seconds"]), POLICY["max_retries"],
                         "a ladder rung nobody can reach is a bound that is not measured")

    def test_a_429_is_retried_on_the_contract_backoff_with_bounded_jitter(self):
        attempts = []

        def invoke():
            attempts.append(len(attempts) + 1)
            if len(attempts) <= POLICY["max_retries"]:
                raise http_error(429)
            return "payload"

        recorder = Recorder(jitter=0.5)
        result = T.retry_call(invoke, contract=CONTRACT, host="commons.wikimedia.org",
                              sleep=recorder.sleep, monotonic=recorder.monotonic,
                              rng=recorder.random)
        self.assertEqual(result, "payload")
        self.assertEqual(len(attempts), POLICY["max_retries"] + 1)
        bound = POLICY["backoff_seconds"]
        self.assertEqual(len(recorder.slept), len(bound))
        for slept, base in zip(recorder.slept, bound):
            self.assertGreaterEqual(slept, base)
            self.assertLessEqual(slept, base * (1.0 + POLICY["jitter_fraction"]) + 1e-9)

    def test_the_last_allowed_attempt_is_a_refusal_not_a_sixth_request(self):
        attempts = []

        def invoke():
            attempts.append(1)
            raise http_error(429)

        recorder = Recorder()
        with self.assertRaises(T.TransientFailure):
            T.retry_call(invoke, contract=CONTRACT, host="x.invalid", sleep=recorder.sleep,
                         monotonic=recorder.monotonic, rng=lambda: 0.0)
        self.assertEqual(len(attempts), POLICY["max_retries"] + 1)
        self.assertEqual(len(recorder.slept), POLICY["max_retries"],
                         "the last attempt failed outright; it bought no further wait")

    def test_a_retry_after_header_beats_the_backoff(self):
        declared = POLICY["retry_after_header"]
        attempts = []

        def invoke():
            attempts.append(1)
            if len(attempts) == 1:
                raise http_error(429, headers={declared: "3"})
            return "payload"

        recorder = Recorder()
        T.retry_call(invoke, contract=CONTRACT, host="x.invalid", sleep=recorder.sleep,
                     monotonic=recorder.monotonic, rng=lambda: 0.0)
        self.assertEqual(recorder.slept, [3.0])

    def test_403_is_not_transient_and_400_and_404_are_never_retried(self):
        for code in [403] + list(POLICY["never_retry_status"]):
            with self.subTest(code=code):
                attempts = []

                def invoke(_code=code):
                    attempts.append(1)
                    raise http_error(_code)

                with self.assertRaises(HTTPError):
                    T.retry_call(invoke, contract=CONTRACT, host="x.invalid",
                                 sleep=lambda s: None, monotonic=Recorder().monotonic,
                                 rng=lambda: 0.0)
                self.assertEqual(len(attempts), 1, f"{code} was retried")

    def test_a_503_is_transient_like_a_429(self):
        attempts = []

        def invoke():
            attempts.append(1)
            if len(attempts) == 1:
                raise http_error(503)
            return "payload"

        recorder = Recorder()
        self.assertEqual(T.retry_call(invoke, contract=CONTRACT, host="x.invalid",
                                      sleep=recorder.sleep, monotonic=recorder.monotonic,
                                      rng=lambda: 0.0), "payload")
        self.assertEqual(len(recorder.slept), 1)


class EtiquetteTests(unittest.TestCase):
    def test_commons_waits_the_declared_interval_between_calls(self):
        provider = SOURCING["providers"]["wikimedia"]
        interval = provider["min_interval_seconds"]
        recorder = Recorder()
        state = T.RateState(monotonic=recorder.monotonic)
        urls = [f"https://commons.wikimedia.org/w/api.php?i={n}" for n in range(3)]
        for url in urls:
            T.retry_call(lambda u=url: "ok", contract=CONTRACT, host="commons.wikimedia.org",
                         sleep=recorder.sleep, monotonic=recorder.monotonic,
                         rng=recorder.random, state=state, min_interval_seconds=interval)
        self.assertEqual(len(recorder.slept), 2,
                         "the interval is between calls, not before the first one")
        self.assertTrue(all(wait >= interval for wait in recorder.slept), recorder.slept)

    def test_commons_sends_the_declared_maxlag_parameter(self):
        opener_calls = []

        def opener(request, timeout):
            opener_calls.append(request.full_url)
            return fake_response({"query": {"pages": []}})

        P.search("wikimedia", "apollo", limit=2, opener=opener, contract=CONTRACT)
        query = parse_qs(urlsplit(opener_calls[0]).query)
        parameter = SOURCING["transport"]["maxlag_parameter"]
        self.assertEqual(query[parameter], [str(SOURCING["transport"]["maxlag_value"])])

    def test_every_request_carries_the_contract_user_agent(self):
        seen = []

        def opener(request, timeout):
            seen.append(request.get_header("User-agent"))
            return fake_response({"query": {"pages": []}})

        P.search("wikimedia", "apollo", limit=1, opener=opener, contract=CONTRACT)
        self.assertEqual(seen, [SOURCING["user_agent"]])

    def test_the_transport_is_serial_only(self):
        self.assertEqual(POLICY["parallelism"], 1)
        for rel in ("tools/sourcing/transport.py", "tools/sourcing/download.py",
                    "tools/sourcing/providers.py"):
            with self.subTest(rel=rel):
                source = (ROOT / rel).read_text(encoding="utf-8")
                tree = ast.parse(source)
                imported = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imported.update(alias.name for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imported.add(node.module)
                self.assertFalse({"threading", "concurrent.futures", "multiprocessing"} & imported,
                                 f"{rel} parallelises a polite API")


class CacheTests(unittest.TestCase):
    def test_a_response_is_cached_by_host_url_and_retrieval_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = Path(tmp)
            calls = []

            def opener(request, timeout):
                calls.append(request.full_url)
                return fake_response({"response": {"numFound": 0, "docs": []}})

            first = P.search("internet-archive", "apollo", limit=1, opener=opener,
                             contract=CONTRACT, episode_dir=episode, retrieval_date="2026-11-13")
            second = P.search("internet-archive", "apollo", limit=1, opener=opener,
                              contract=CONTRACT, episode_dir=episode, retrieval_date="2026-11-13")
            self.assertEqual(len(calls), 1, "the same day re-ran the query over the network")
            self.assertEqual(first, second)

    def test_the_cache_does_not_cross_a_retrieval_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            episode = Path(tmp)
            calls = []

            def opener(request, timeout):
                calls.append(request.full_url)
                return fake_response({"response": {"numFound": 0, "docs": []}})

            P.search("internet-archive", "apollo", limit=1, opener=opener, contract=CONTRACT,
                     episode_dir=episode, retrieval_date="2026-11-13")
            P.search("internet-archive", "apollo", limit=1, opener=opener, contract=CONTRACT,
                     episode_dir=episode, retrieval_date="2026-11-14")
            self.assertEqual(len(calls), 2)

    def test_the_cache_key_names_the_three_fields_the_contract_declares(self):
        self.assertEqual(POLICY["cache_key_fields"], ["host", "url", "retrieval_date"])


class CredentialPathTests(unittest.TestCase):
    def test_no_request_ever_carries_an_authorization_header(self):
        """§6: a code path that can carry a credential is the failure being avoided."""
        seen = []

        def opener(request, timeout):
            seen.append(request.get_header("Authorization"))
            return fake_response({"query": {"pages": []}})

        for provider in SOURCING["providers"]:
            with self.subTest(provider=provider):
                P.search(provider, "apollo", limit=1, opener=opener, contract=CONTRACT)
        self.assertEqual(set(seen), {None})

    def test_an_environment_credential_is_never_read_by_the_sourcing_client(self):
        source = "".join((ROOT / rel).read_text(encoding="utf-8") for rel in
                         ("tools/sourcing/providers.py", "tools/sourcing/transport.py",
                          "tools/sourcing/download.py"))
        tree = ast.parse(source)
        reads = [ast.unparse(node) for node in ast.walk(tree)
                 if isinstance(node, ast.Subscript)
                 and ast.unparse(node.value).endswith("environ")
                 and isinstance(node.slice, ast.Constant)]
        self.assertEqual(reads, [], f"the client reaches for an environment credential: {reads}")


if __name__ == "__main__":
    unittest.main()
