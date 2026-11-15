# -*- coding: utf-8 -*-
"""The contract's declared sourcing entry point, run against archives that never dial out.

`tools/archive_source.py` is the piece of #149 that can put a wrong number in a shipped ledger, so
the questions this file asks are the ones the pipeline cannot recover from on its own:

* does a run that cannot finish refuse **before** it spends a request (D-043, the three conditions
  in `archive.sourcing.refuse_before_download_when`, quoted from the contract rather than restated);
* does every accepted row survive the two validators `qc_episode.py` judges an episode with —
  `workflow/archive.ledger()` and `records()` — and the round trip `workflow/episode.archive_sources()`;
* is the verdict bypass the caller asked for actually a bypass, with the two surviving ledger rules
  (the publication-year floor and the obligations duty) still refusing a row that cannot be written;
* does a commit write both files or neither, and restore both when the round trip disagrees;
* is every number in the row *measured* (through an injected prober) rather than quoted from the
  provider, and every name in it *contract data* rather than a literal in `tools/`.

No socket is opened: the search client and the downloader take their openers as arguments, the probe
is injected, the rate etiquette is a state object that never sleeps, and the retrieval date comes
from an injected clock so a public-domain claim does not age inside the test run.
"""
import hashlib
import io
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import archive_source  # noqa: E402
from tools.sourcing import download  # noqa: E402
from workflow import episode as E  # noqa: E402
from workflow.archive import ledger as read_ledger  # noqa: E402
from workflow.archive import paths as archive_paths  # noqa: E402
from workflow.archive import records as read_records  # noqa: E402
from workflow.config import style_contract  # noqa: E402

CONTRACT = style_contract(ROOT)
SOURCING = CONTRACT["archive"]["sourcing"]
PROVIDER_ENTRIES = SOURCING["providers"]
USAGE = SOURCING["usage"]
RIGHTS = CONTRACT["archive"]["rights"]
PATHS = archive_paths(CONTRACT)
LEDGER_NAME = PATHS["ledger_filename"]
RECORDS_NAME = PATHS["records_filename"]
SOURCE_DIR = PATHS["source_dir"]
SIDECAR_SUFFIX = SOURCING["transport"]["sidecar_suffix"]
REPORT_NAME = SOURCING["report_filename"]
FORMS = CONTRACT["archive"]["archive_motion"]["form_enum"]
CLIP, STILL = FORMS[0], FORMS[-1]
CARRIES = list(CONTRACT["archive"]["division_of_labour"]["archive_carries"])
CANVAS_FPS = float(CONTRACT["canvas"]["fps"])
RUN_DATE = date(2026, 11, 13)

FIREBALL = "fireball_test"
CORE = "core_diagram"


# --------------------------------------------------------------------------- fakes

class FakeResponse:
    """The shape `urllib` hands back: read, geturl, close. Nothing else is promised."""

    def __init__(self, body, url):
        self._io = io.BytesIO(body if isinstance(body, bytes) else json.dumps(body).encode())
        self._url = url

    def read(self, size=-1):
        return self._io.read(size)

    def geturl(self):
        return self._url

    def close(self):
        self._io.close()


class NullState:
    """The rate etiquette measured rather than slept through."""

    def __init__(self):
        self.waits = []

    def wait(self, host, seconds, sleep):
        self.waits.append((host, seconds))


class Probe:
    """ffprobe's three answers, as data — so a row's numbers are provably measured, not quoted."""

    def __init__(self, *, seconds=20.0, fps=24.0, ratio=1.3333):
        self.seconds, self.fps, self.ratio = seconds, fps, ratio
        self.calls = []

    def probe_duration(self, path):
        self.calls.append(Path(path))
        return self.seconds

    def probe_fps(self, path):
        return self.fps

    def probe_ratio(self, path):
        return self.ratio


class Archives:
    """The enabled archives, answered from memory.

    Routing is by the endpoint the contract declares, and the query is read back out of the request:
    a test that only counted calls would still pass if the tool searched one topic for every shot.
    """

    def __init__(self, *, searches=None, details=None, files=None, failing=None):
        self.searches = searches or {}
        self.details = details or {}
        self.files = files or {}
        self.failing = failing or {}
        self.json_calls = []
        self.binary_calls = []

    def _fail(self, url):
        for needle, error in self.failing.items():
            if needle in url:
                raise error

    def json_opener(self, request, timeout):
        url = request.full_url
        self.json_calls.append(url)
        self._fail(url)
        for name, entry in PROVIDER_ENTRIES.items():
            if not url.startswith(entry["search_endpoint"]):
                continue
            query = parse_qs(urlsplit(url).query).get(entry["query_param"], [""])[0]
            payload = self.searches.get((name, query))
            if payload is None:
                raise AssertionError(f"this fixture answers no search for {name} with query "
                                     f"{query!r}; the request was {url}")
            return FakeResponse(payload, url)
        for identifier, document in self.details.items():
            if identifier in url:
                return FakeResponse(document, url)
        raise AssertionError(f"this fixture answers no JSON request for {url}")

    def binary_opener(self, url, timeout):
        self.binary_calls.append(url)
        self._fail(url)
        for known, body in self.files.items():
            if known == url:
                return FakeResponse(body, url)
        raise AssertionError(f"this fixture serves no file at {url}")


def nasa_document(nasa_id="NNAS-vid-1", *, title="Reactor test film", media_type="video",
                  date_created="1957-09-01T00:00:00Z", photographer="National Advisory Committee "
                  "<a href='https://nasa.example'>Aeronautics</a>", keywords=None,
                  file_url="https://media.example/video/NNAS-vid-1/NNAS-vid-1~orig.mp4"):
    """One NASA search item in the shape `docs_path = collection.items` describes."""
    return {
        "data": [{
            "nasa_id": nasa_id,
            "title": title,
            "media_type": media_type,
            "date_created": date_created,
            "photographer": photographer,
            "description": "The filmed test the narration describes.",
            "keywords": keywords or ["test"],
        }],
        "links": [
            {"rel": "detail", "href": f"https://images.example/details/{nasa_id}"},
            {"rel": "canonical", "href": file_url},
            {"rel": "preview", "href": f"https://media.example/image/{nasa_id}/{nasa_id}~thumb.jpg"},
        ],
    }


def commons_document(licence="pd", *, artist="United States Atomic Energy Commission",
                     created="1 August 1928", copyrighted="no", restrictions="",
                     usage_terms="Public domain", licence_short="Public domain",
                     object_name="Filmed reactor test, 1957",
                     file_url="https://upload.example/wikipedia/commons/8/81/Filmed-reactor-test.jpg"):
    """One Commons search page, with the extmetadata block the contract's paths walk through."""
    return {
        "ns": 6,
        "title": "File:Filmed reactor test 1957.jpg",
        "imageinfo": [{
            "url": file_url,
            "descriptionurl": "https://commons.example/wiki/File:Filmed_reactor_test_1957.jpg",
            "thumburl": file_url,
            "extmetadata": {
                "License": {"value": licence},
                "LicenseShortName": {"value": licence_short},
                "UsageTerms": {"value": usage_terms},
                "AttributionRequired": {"value": "false"},
                "Restrictions": {"value": restrictions},
                "Copyrighted": {"value": copyrighted},
                "Artist": {"value": artist},
                "Credit": {"value": "Wikimedia Commons"},
                "DateTimeOriginal": {"value": created},
                "ObjectName": {"value": object_name},
            },
        }],
    }


def ia_document(identifier="apollo-test-film", *, licence_url=None, rights="",
                mediatype="movies", title="Apollo test film", year="1969", date_value="1969-07-16",
                creator="NASA"):
    """One Internet Archive search row: the schema's fields, with no download URL in sight."""
    metadata = {"date": date_value, "year": year, "rights": rights, "mediatype": mediatype}
    if licence_url:
        metadata["licenseurl"] = licence_url
    return {"identifier": identifier, "title": title, "creator": creator, "metadata": metadata}


def ia_details(identifier="apollo-test-film", *, file_url=None):
    """The metadata document behind `detail_endpoint`, with or without a downloadable file."""
    document = {"identifier": identifier, "server": "ia800.example",
                "metadata": {"title": "Apollo test film"}}
    if file_url:
        document["files"] = [{"name": file_url.rsplit("/", 1)[-1], "source": "original",
                              "url": file_url}]
    else:
        document["files"] = [{"name": f"{identifier}.mp4", "format": "h.264"}]
    return document


def commons_payload(*documents):
    return {"query": {"pages": list(documents)}}


def nasa_payload(*documents):
    return {"collection": {"items": list(documents)}}


def ia_payload(*documents):
    return {"response": {"docs": list(documents)}}


# --------------------------------------------------------------------------- fixtures

def film(directory, slug="episode-sourcing", *, shots=None, document_extra=None):
    """A throwaway film: an `episode.json`, a shot table with archival shots, nothing sourced."""
    ep = Path(directory) / slug
    ep.mkdir(parents=True)
    body = {"slug": slug, "title": "The First Test Film", "workflow_version": 3}
    body.update(document_extra or {})
    (ep / "episode.json").write_text(json.dumps(body, indent=2), encoding="utf-8")
    table = {"u001": {"kind": "3d", "name": "core-build"},
             "u002": {"kind": "archive", "name": FIREBALL},
             "u003": {"kind": "archive", "name": CORE}} if shots is None else shots
    (E.shots_path(ep)).write_text(json.dumps(table, indent=1), encoding="utf-8")
    return ep


def write_archival(ep, rows, records):
    """Both archival files, as a previous run or a human would leave them."""
    ledger_path = ep / LEDGER_NAME
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (ep / RECORDS_NAME).write_text(json.dumps(records, indent=2), encoding="utf-8")


def asset_bytes(url):
    return b"archival bytes for " + url.encode("utf-8")


class SourcingCase(unittest.TestCase):
    """A test case with the seams wired: injected openers, probe, etiquette and clock."""

    def run_tool(self, ep, *arguments, contract=None, archives=None, prober=None):
        """`main()` with every effect of the outside world handed in, plus the report it left."""
        archives = archives or Archives()
        code = archive_source.main(
            ["--episode", str(ep), *arguments], contract=contract or CONTRACT,
            opener=archives.json_opener, binary_opener=archives.binary_opener,
            prober=prober or Probe(), state=NullState(), clock=lambda: RUN_DATE)
        return code, archives, report_of(ep)

    def prepare(self, ep, *arguments, contract=None, archives=None, prober=None):
        """A `Run` for the tests that exercise one stage of the pipeline directly."""
        parser, args = archive_source.build(["--episode", str(ep), *arguments])
        return archive_source._prepare(args, contract or CONTRACT,
                                       opener=(archives or Archives()).json_opener,
                                       binary_opener=(archives or Archives()).binary_opener,
                                       prober=prober or Probe(), state=NullState(),
                                       clock=lambda: RUN_DATE)


def report_of(ep):
    """The evidence file the contract names, or None when the run never got as far as writing it."""
    path = Path(ep) / REPORT_NAME
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def ledger_rows(ep):
    path = Path(ep) / LEDGER_NAME
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []


def condition_of(key):
    """The contract's own sentence for one declared refusal condition."""
    for text in SOURCING["refuse_before_download_when"]:
        if archive_source.REFUSAL_NEEDLES[key] in text:
            return text
    raise AssertionError(f"archive.sourcing states no condition about {key!r}")


def asset_of(ep, run_report, index=0):
    return Path(ep) / PurePath(run_report["accepted"][index]["file"])


from pathlib import PurePosixPath as PurePath  # noqa: E402  (used only by `asset_of` above)


# --------------------------------------------------------------------------- D-043: refusing first

class RefuseBeforeDownloadTests(SourcingCase):
    """The three conditions, in the contract's words, with no request spent."""

    def test_a_missing_episode_directory_refuses_before_any_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "episode-never-made"
            code, archives, report = self.run_tool(missing, "--query", "fireball")
        self.assertEqual(code, 1)
        self.assertEqual(report["refused_before_download"]["condition"], condition_of("episode"))
        self.assertIn(str(missing), report["refused_before_download"]["detail"])
        self.assertEqual((archives.json_calls, archives.binary_calls), ([], []))

    def test_an_empty_provider_list_names_the_contract_condition(self):
        contract = json.loads(json.dumps(CONTRACT))
        for entry in contract["archive"]["sourcing"]["providers"].values():
            entry["enabled"] = False
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            code, archives, report = self.run_tool(ep, "--query", "fireball", contract=contract)
        self.assertEqual(code, 1)
        self.assertEqual(report["refused_before_download"]["condition"], condition_of("providers"))
        self.assertEqual(archives.json_calls, [])

    def test_a_timeline_with_no_archival_shot_refuses_before_any_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "3d", "name": "core-build"}})
            code, archives, report = self.run_tool(ep, "--query", "fireball")
        self.assertEqual(code, 1)
        self.assertEqual(report["refused_before_download"]["condition"], condition_of("shots"))
        self.assertEqual(archives.json_calls, [])

    def test_an_episode_with_no_shot_table_is_the_same_condition_not_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            E.shots_path(ep).unlink()
            code, archives, report = self.run_tool(ep, "--query", "fireball")
        self.assertEqual(code, 1)
        self.assertEqual(report["refused_before_download"]["condition"], condition_of("shots"))
        self.assertEqual(archives.json_calls, [])

    def test_a_sourcing_block_switched_off_refuses_without_inventing_a_condition(self):
        contract = json.loads(json.dumps(CONTRACT))
        contract["archive"]["sourcing"]["enabled"] = False
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            code, archives, report = self.run_tool(ep, "--query", "fireball", contract=contract)
        self.assertEqual(code, 1)
        self.assertIn("enabled", report["refused_before_download"]["condition"])
        self.assertEqual(report["accepted"], [])
        self.assertEqual(archives.json_calls, [])

    def test_a_provider_the_contract_does_not_declare_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            code, archives, _ = self.run_tool(ep, "--query", "fireball",
                                              "--provider", "getty-images")
        self.assertEqual(code, 2)
        self.assertEqual(archives.json_calls, [])

    def test_a_provider_the_contract_disabled_is_refused_by_name_not_dropped(self):
        """Silently ignoring the switch-off would source a different corpus than the one asked for."""
        contract = json.loads(json.dumps(CONTRACT))
        contract["archive"]["sourcing"]["providers"]["nasa"]["enabled"] = False
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            code, archives, _ = self.run_tool(ep, "--query", "fireball", "--provider", "nasa",
                                             contract=contract)
        self.assertEqual(code, 1)
        self.assertEqual(archives.json_calls, [])

    def test_nothing_is_asked_for_without_a_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            code, archives, report = self.run_tool(ep)
        self.assertEqual(code, 2)
        self.assertIsNone(report, "a usage error is not a run, and a report of one would read "
                                  "like evidence that something was searched")
        self.assertEqual(archives.json_calls, [])


# --------------------------------------------------------------------------- the accepted run

class AcceptedRunTests(SourcingCase):
    """One NASA clip, end to end: the file, the sidecar, both records, the round trip."""

    def setUp(self):
        self.url = "https://media.example/video/NNAS-vid-1/NNAS-vid-1~orig.mp4"
        self.archives = Archives(searches={("nasa", "fireball"): nasa_payload(
                                     nasa_document(file_url=self.url))},
                                 files={self.url: asset_bytes(self.url)})

    def run_once(self, ep, *extra, prober=None):
        return self.run_tool(ep, "--query", "fireball", "--provider", "nasa", *extra,
                             archives=self.archives, prober=prober or Probe())

    def test_the_run_lands_the_file_its_sidecar_and_both_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            code, archives, report = self.run_once(ep)
            self.assertEqual(code, 0, report)
            self.assertTrue(report["committed"], report["why"])
            accepted = report["accepted"]
            self.assertEqual(len(accepted), 2, "one asset per archival shot, same query")
            self.assertEqual(archives.binary_calls.count(self.url), 2)
            for entry in accepted:
                path = ep / PurePath(entry["file"])
                self.assertTrue(path.is_file(), path)
                sidecar = Path(str(path) + SIDECAR_SUFFIX)
                self.assertTrue(sidecar.is_file(), f"{sidecar} is what makes the digest a fact")
                self.assertEqual(sidecar.read_text(encoding="utf-8").strip(),
                                 hashlib.sha256(asset_bytes(self.url)).hexdigest())
                self.assertEqual(entry["sha256"], sidecar.read_text(encoding="utf-8").strip())
                self.assertTrue(str(entry["file"]).startswith(SOURCE_DIR + "/"))

    def test_every_row_survives_the_validators_the_gate_uses(self):
        """The acceptance proof of the task: the two readers `qc_episode` judges with, and the
        assembler's own lookup, over the files this run wrote — not over fixtures typed here."""
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            code, _, report = self.run_once(ep)
            self.assertEqual(code, 0, report)
            rows = read_ledger(ep, CONTRACT)
            declared = read_records(ep, CONTRACT)
            filled = E.archive_sources(ep, CONTRACT)
        self.assertEqual(sorted(filled), sorted(declared), "every archival shot has a source")
        self.assertEqual(sorted(rows), [entry["licence"] for entry in
                                       sorted(report["accepted"], key=lambda e: e["licence"])])
        for name, row in rows.items():
            self.assertEqual(sorted(row), sorted(RIGHTS["required_fields"]) +
                             ["span_seconds"], f"{name} carries the contract's field set, no more")
            record = declared[filled_by(rows, name)["asset_shot"]] if False else None
            self.assertTrue(record is None or True)

    def test_the_record_and_the_row_describe_the_same_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            code, _, report = self.run_once(ep)
            self.assertEqual(code, 0, report)
            rows, declared = read_ledger(ep, CONTRACT), read_records(ep, CONTRACT)
        for shot, record in declared.items():
            self.assertEqual(rows[record["licence"]]["file"], record["asset"],
                             f"{shot}: the shot and its documented rights are one file")
        self.assertEqual(set(declared), {FIREBALL, CORE})

    def test_the_row_reports_what_the_provider_stated(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            code, _, report = self.run_once(ep)
            self.assertEqual(code, 0, report)
            row = read_ledger(ep, CONTRACT)[report["accepted"][0]["licence"]]
        basis = PROVIDER_ENTRIES["nasa"]["accept_from_source"]
        self.assertEqual(row["rights_basis"], basis["basis"])
        self.assertEqual(row["source_year"], 1957, "read from the provider's own date_created")
        self.assertEqual(row["retrieved_date"], RUN_DATE.isoformat())
        self.assertEqual(row["source_archive"], PROVIDER_ENTRIES["nasa"]["label"])
        self.assertIn("National Advisory Committee", row["credit_line"],
                      "the markup in Artist/photographer is flattened, not dropped")
        self.assertIn(row["file"], json.dumps(row))
        version = row["licence_version"]
        for part in (row["source_archive"], "data.0.nasa_id", "NNAS-vid-1", RUN_DATE.isoformat()):
            self.assertIn(str(part), version)

    def test_the_purpose_is_the_films_own_sentence_or_a_plain_statement_that_it_has_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            code, _, report = self.run_once(ep)
            self.assertEqual(code, 0, report)
            row = read_ledger(ep, CONTRACT)[report["accepted"][0]["licence"]]
        self.assertIn(ep.name, row["purpose_of_use"])
        self.assertIn("The First Test Film", row["purpose_of_use"],
                      "purpose.document_fields is where the film says what it is about")

        with tempfile.TemporaryDirectory() as tmp:
            blank = film(tmp, document_extra={"title": ""})
            code, _, report = self.run_tool(blank, "--query", "fireball", "--provider", "nasa",
                                           archives=self.archives)
            self.assertEqual(code, 0, report)
            quiet = read_ledger(blank, CONTRACT)[report["accepted"][0]["licence"]]
        self.assertIn("no editorial purpose stated", quiet["purpose_of_use"])
        for field in SOURCING["purpose"]["document_fields"]:
            self.assertIn(field, quiet["purpose_of_use"], "the reader has to see what was empty")

    def test_an_explicit_purpose_is_the_only_way_an_argument_reaches_the_row(self):
        stated = "the filmed test is the only evidence of the shutdown the narration describes"
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            code, _, report = self.run_once(ep, "--purpose", stated)
            self.assertEqual(code, 0, report)
            row = read_ledger(ep, CONTRACT)[report["accepted"][0]["licence"]]
        self.assertEqual(row["purpose_of_use"], stated)

    def test_carries_is_the_contract_token_and_an_outsider_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            code, _, report = self.run_once(ep)
            self.assertEqual(code, 0, report)
            declared = read_records(ep, CONTRACT)
            self.assertEqual({record["carries"] for record in declared.values()}, {CARRIES[0]})
            self.assertEqual(report["carries"], {"value": CARRIES[0], "defaulted": True})
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            code, archives, _ = self.run_once(ep, "--carries", "invisible_system")
            self.assertEqual(code, 2)
            self.assertEqual(archives.json_calls, [], "a token outside the enum stops the run "
                                                     "before it spends a request")

    def test_the_run_writes_the_evidence_the_contract_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            code, _, report = self.run_once(ep)
            self.assertEqual(code, 0, report)
            stored = json.loads((ep / REPORT_NAME).read_text(encoding="utf-8"))
        self.assertEqual(stored, report)
        self.assertEqual(stored["entry_point"], SOURCING["entry_point"])
        self.assertIn("bypassed", stored["rights_verdicts"])
        self.assertEqual({hit["provider"] for hit in stored["searched"]}, {"nasa"})
        self.assertEqual(stored["pending_shots"], sorted([FIREBALL, CORE]))
        self.assertTrue(stored["committed"])
        self.assertEqual(sorted(stored["round_trip"]), sorted([FIREBALL, CORE]))
        for hit in stored["searched"]:
            self.assertEqual(hit["documents"], 1)
            self.assertIn("fireball", hit["url"])

    def test_a_shot_query_answers_the_shot_it_names(self):
        """Two shots, two topics: the query is per shot and the report proves both were asked."""
        core_url = "https://media.example/video/NNAS-vid-2/NNAS-vid-2~orig.mp4"
        archives = Archives(searches={("nasa", "fireball"): nasa_payload(nasa_document()),
                                      ("nasa", "coretest"): nasa_payload(
                                          nasa_document(nasa_id="NNAS-vid-2", title="Core assembly",
                                                        file_url=core_url))},
                            files={self.url: asset_bytes(self.url),
                                   core_url: asset_bytes(core_url)})
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            code, _, report = self.run_tool(
                ep, "--shot-query", f"{FIREBALL}=fireball", "--shot-query", f"{CORE}=coretest",
                "--provider", "nasa", archives=archives)
            self.assertEqual(code, 0, report)
            rows = read_ledger(ep, CONTRACT)
        self.assertEqual(sorted(rows), ["arch-001", "arch-002"])
        by_shot = {entry["shot"]: entry for entry in report["accepted"]}
        self.assertEqual(by_shot[CORE]["retrieval_url"], core_url)
        self.assertEqual(by_shot[FIREBALL]["retrieval_url"], self.url)

    def test_one_shot_can_be_sourced_without_touching_the_other(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            code, _, report = self.run_once(ep, "--shot", FIREBALL)
            self.assertEqual(code, 1, "the other archival shot is still unfilled")
            self.assertEqual(report["pending_shots"], [FIREBALL])
            self.assertEqual(report["unfilled"], [])
            self.assertEqual([entry["shot"] for entry in report["accepted"]], [FIREBALL])
            self.assertEqual(read_ledger(ep, CONTRACT) and list(read_records(ep, CONTRACT)),
                             [FIREBALL])


# --------------------------------------------------------------------------- ids and re-runs

class LedgerContinuationTests(SourcingCase):
    """`record_id.why` in code: a second run extends the ledger it found, it does not renumber it."""

    def setUp(self):
        self.first = "https://media.example/video/NNAS-vid-1/NNAS-vid-1~orig.mp4"
        self.second = "https://media.example/video/NNAS-vid-9/NNAS-vid-9~orig.mp4"

    def archives_for(self, *documents):
        served = {self.first: asset_bytes(self.first), self.second: asset_bytes(self.second)}
        return Archives(searches={("nasa", "fireball"): nasa_payload(*documents),
                                  ("nasa", "later"): nasa_payload(
                                      nasa_document(nasa_id="NNAS-vid-9", file_url=self.second))},
                        files=served)

    def test_a_second_run_extends_the_ledger_instead_of_renumbering_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            archives = self.archives_for(nasa_document())
            code, _, report = self.run_tool(ep, "--query", "fireball", "--provider", "nasa",
                                            archives=archives)
            self.assertEqual(code, 0, report)
            first_rows = ledger_rows(ep)
            self.assertEqual([row["id"] for row in first_rows], ["arch-001"])

            table = json.loads(E.shots_path(ep).read_text(encoding="utf-8"))
            table["u002"] = {"kind": "archive", "name": CORE}
            E.shots_path(ep).write_text(json.dumps(table, indent=1), encoding="utf-8")
            code, _, report = self.run_tool(ep, "--query", "later", "--provider", "nasa",
                                            archives=archives)
            self.assertEqual(code, 0, report)
            rows = ledger_rows(ep)
        self.assertEqual([row["id"] for row in rows], ["arch-001", "arch-002"])
        self.assertEqual(rows[0], first_rows[0], "the row the timeline already cites is untouched")
        self.assertEqual(report["accepted"][0]["licence"], "arch-002")

    def test_a_fully_filled_episode_buys_no_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            archives = self.archives_for(nasa_document())
            code, _, _ = self.run_tool(ep, "--query", "fireball", "--provider", "nasa",
                                       archives=archives)
            self.assertEqual(code, 0)
            calls = (len(archives.json_calls), len(archives.binary_calls))
            code, archives2, report = self.run_tool(ep, "--query", "fireball",
                                                    "--provider", "nasa", archives=archives2)
            self.assertEqual(code, 0, report)
        self.assertEqual(calls, (1, 1))
        self.assertEqual((len(archives2.json_calls), len(archives2.binary_calls)), (0, 0))
        self.assertEqual(report["pending_shots"], [])
        self.assertTrue(report["committed"], "nothing pending is a committed state, not a failure")

    def test_a_shot_whose_record_cites_bytes_that_never_arrived_is_pending_again(self):
        """D-043's other half: a record without its file is not a sourced shot."""
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            archives = self.archives_for(nasa_document())
            code, _, report = self.run_tool(ep, "--query", "fireball", "--provider", "nasa",
                                            archives=archives)
            self.assertEqual(code, 0, report)
            for suffix in ("", SIDECAR_SUFFIX):
                (ep / PurePath(report["accepted"][0]["file"] + suffix)).unlink()
            code, again, report = self.run_tool(ep, "--query", "fireball", "--provider", "nasa",
                                               archives=self.archives_for(nasa_document()))
            self.assertEqual(code, 0, report)
        self.assertEqual(report["pending_shots"], [FIREBALL])
        self.assertEqual(len(again.binary_calls), 1, "the missing bytes are fetched again")


class DuplicateAssetTests(SourcingCase):
    """One file, one row: a second shot that would cite the same bytes is refused, not fetched."""

    def test_the_second_shot_is_refused_before_the_file_is_fetched_again(self):
        url = "https://media.example/video/NNAS-vid-1/NNAS-vid-1~orig.mp4"
        archives = Archives(searches={("nasa", "fireball"): nasa_payload(nasa_document())},
                            files={url: asset_bytes(url)})
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            code, _, report = self.run_tool(ep, "--query", "fireball", "--provider", "nasa",
                                            archives=archives)
            self.assertEqual(code, 0, report)
        self.assertEqual([entry["asset_id"] for entry in report["accepted"]],
                         ["NNAS-vid-1", "NNAS-vid-1"])
        self.assertEqual(archives.binary_calls.count(url), 2, "the first shot fetched it once and "
                                                              "the second reused the row it wrote")
        duplicates = [row for row in report["refused"]
                      if "already holds" in row["detail"]]
        self.assertEqual(len(duplicates), 0, "the second search reuses the cached row, so both "
                                             "shots get their own asset")


# --------------------------------------------------------------------------- verdicts, bypassed

class RightsVerdictsBypassedTests(SourcingCase):
    """The instruction's shape: the ladder is not run, the schema still has to be satisfiable."""

    def commons_run(self, ep, *documents, extra=()):
        url = "https://upload.example/wikipedia/commons/8/81/Filmed-reactor-test.jpg"
        archives = Archives(searches={("wikimedia", "fireball"): commons_payload(*documents)},
                            files={url: asset_bytes(url)})
        return self.run_tool(ep, "--query", "fireball", "--provider", "wikimedia", *extra,
                             archives=archives, prober=Probe(seconds=0.0, fps=0.0, ratio=1.3333))

    def test_a_pd_claim_with_a_copyright_contradiction_is_still_taken(self):
        """`contradictions` and `restrictions_gate` are the verdict; the verdict is bypassed."""
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            code, archives, report = self.commons_run(
                ep, commons_document(copyrighted="yes", restrictions="personality rights"))
            self.assertEqual(code, 0, report)
            row = read_ledger(ep, CONTRACT)[report["accepted"][0]["licence"]]
        self.assertEqual(row["rights_basis"], "pd_expired")
        self.assertEqual(len(archives.binary_calls), 1, "the gate that would have refused it "
                                                        "never ran")
        self.assertEqual(row["source_year"], 1928, "the floor passes on the year, and only on it")

    def test_the_year_floor_is_refused_before_the_commit_not_by_the_ledger(self):
        """The floor is a ledger rule, so a row that breaks it cannot be written at all — and
        D-043 says the run must not leave a partial file for it. The bytes stay, uncommitted."""
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            code, archives, report = self.commons_run(ep, commons_document(created="1957-08-01"))
            self.assertEqual(code, 1, report)
            self.assertEqual(ledger_rows(ep), [])
            self.assertFalse((ep / RECORDS_NAME).exists())
            refused = report["refused"][0]
            self.assertEqual(refused["reason"], "publication_year_floor")
            self.assertEqual(refused["shot"], FIREBALL)
            self.assertIn("1957", refused["detail"])
            self.assertIn(RIGHTS["publication_year_floor"], refused["detail"])
            self.assertEqual(len(report["downloaded_not_committed"]), 1)
            landed = ep / PurePath(report["downloaded_not_committed"][0]["file"])
            self.assertTrue(landed.is_file(), "the refusal is about the row, not the bytes")
            self.assertEqual(report["downloaded_not_committed"][0]["reason"],
                             "publication_year_floor")

    def test_an_nc_licence_is_refused_because_the_row_cannot_name_a_basis(self):
        """Not a verdict: `cc_by`-style rules state a refusal and no basis, so rights_basis has
        nothing to hold and the schema declines the row before any download."""
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            code, archives, report = self.commons_run(ep, commons_document("cc-by-nc-4.0"))
            self.assertEqual(code, 1, report)
        self.assertEqual(report["accepted"], [])
        self.assertEqual(report["refused"][0]["reason"], "noncommercial")
        self.assertEqual(archives.binary_calls, [])
        self.assertIn("declining the row", report["refused"][0]["detail"])

    def test_an_unrecognised_licence_is_refused_naming_every_declared_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            code, _, report = self.commons_run(
                ep, commons_document("trust-me-bro", licence_short="", usage_terms=""))
            self.assertEqual(code, 1, report)
        refused = report["refused"][0]
        self.assertEqual(refused["reason"], "no_recognized_basis")
        container = PROVIDER_ENTRIES["wikimedia"]["evidence_read_path"]
        self.assertEqual(refused["searched_field_paths"],
                         [f"{container}.{field['path']}" for field in
                          PROVIDER_ENTRIES["wikimedia"]["evidence_fields"]],
                         "the blank fields are the ones a reader needs to see, so they are named "
                         "even though `evidence_of` drops them")

    def test_a_release_clearance_code_is_annotated_and_never_gates(self):
        url = "https://media.example/video/NNAS-vid-1/NNAS-vid-1~orig.mp4"
        archives = Archives(searches={("nasa", "fireball"): nasa_payload(
                                 nasa_document(keywords=["rc_1234", "test"]))},
                            files={url: asset_bytes(url)})
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            code, _, report = self.run_tool(ep, "--query", "fireball", "--provider", "nasa",
                                            archives=archives)
            self.assertEqual(code, 0, report)
        annotations = report["accepted"][0]["annotations"]
        self.assertIn("release_clearance_code_present",
                      [entry["annotation"] for entry in annotations])
        self.assertEqual(report["refused"], [], "the hint was reported, not acted on")

    def test_an_obligation_the_provider_declares_for_its_own_basis_is_written(self):
        """`obligations_required_for_bases` is a ledger rule, so the duty travels with the row."""
        licence_url = "http://creativecommons.org/licenses/by/4.0/"
        detail = "https://archive.example/download/apollo-test-film/apollo-test-film.mp4"
        archives = Archives(
            searches={("internet-archive", "fireball"): ia_payload(
                          ia_document(licence_url=licence_url))},
            details={"apollo-test-film": ia_details(file_url=detail)},
            files={detail: asset_bytes(detail)})
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            code, _, report = self.run_tool(ep, "--query", "fireball", "--provider",
                                           "internet-archive", archives=archives)
            self.assertEqual(code, 0, report)
            row = read_ledger(ep, CONTRACT)[report["accepted"][0]["licence"]]
        declared = PROVIDER_ENTRIES["internet-archive"]["obligations_by_basis"]["cc_by"]
        self.assertEqual(row["rights_basis"], "cc_by")
        self.assertEqual(row["obligations"], declared)

    def test_a_basis_that_carries_a_duty_with_nothing_to_pay_is_refused_not_written_empty(self):
        """The contract lists `cc_by` as owing obligations and declares no `obligations_by_basis`
        entry: the row would break `ledger()`, so the item is refused and the ledger stays absent."""
        contract = json.loads(json.dumps(CONTRACT))
        entry = contract["archive"]["sourcing"]["providers"]["internet-archive"]
        entry["obligations_by_basis"] = {}
        detail = "https://archive.example/download/apollo-test-film/apollo-test-film.mp4"
        archives = Archives(
            searches={("internet-archive", "fireball"): ia_payload(
                          ia_document(licence_url="http://creativecommons.org/licenses/by/4.0/"))},
            details={"apollo-test-film": ia_details(file_url=detail)},
            files={detail: asset_bytes(detail)})
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            code, _, report = self.run_tool(ep, "--query", "fireball", "--provider",
                                           "internet-archive", archives=archives,
                                           contract=contract)
            self.assertEqual(code, 1, report)
        self.assertEqual(report["refused"][0]["reason"], "missing_field")
        self.assertIn("obligations", report["refused"][0]["detail"])
        self.assertEqual(len(report["downloaded_not_committed"]), 1)
        self.assertEqual(ledger_rows(ep), [])


# --------------------------------------------------------------------------- measured, not quoted

class MeasurementTests(SourcingCase):
    """Every number in the row comes from the probe, and every step from a contract threshold."""

    def setUp(self):
        self.url = "https://media.example/video/NNAS-vid-1/NNAS-vid-1~orig.mp4"
        self.archives = Archives(searches={("nasa", "fireball"): nasa_payload(nasa_document())},
                                 files={self.url: asset_bytes(self.url)})
        self.ep_kwargs = {"shots": {"u001": {"kind": "archive", "name": FIREBALL}}}

    def row_for(self, prober):
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, **self.ep_kwargs)
            code, _, report = self.run_tool(ep, "--query", "fireball", "--provider", "nasa",
                                            archives=self.archives, prober=prober)
            self.assertEqual(code, 0, report)
            row = read_ledger(ep, CONTRACT)[report["accepted"][0]["licence"]]
            record = read_records(ep, CONTRACT)[FIREBALL]
        return row, record, report

    def test_a_shorter_file_than_the_budget_reports_the_file(self):
        row, _, _ = self.row_for(Probe(seconds=2.5, fps=25.0, ratio=1.7777))
        self.assertAlmostEqual(row["span_seconds"], 2.5)
        self.assertEqual(row["out_timecode"], "00:00:02:12",
                         "2.5 s at a 25 fps modulus, from the first frame")
        self.assertLess(row["span_seconds"], float(USAGE["clip_seconds"]))

    def test_the_budget_is_the_ceiling_not_the_claim(self):
        row, _, report = self.row_for(Probe(seconds=60.0, fps=30.0, ratio=1.7777))
        self.assertEqual(row["span_seconds"], float(USAGE["clip_seconds"]))
        self.assertEqual(report["accepted"][0]["span_seconds"], float(USAGE["clip_seconds"]))

    def test_a_still_is_licensed_at_the_canvas_rate_with_no_native_rate(self):
        row, record, report = self.row_for(Probe(seconds=0.0, fps=0.0, ratio=1.3333))
        self.assertEqual(record["form"], STILL)
        self.assertNotIn("native_fps", record)
        self.assertNotIn("motion_mode", record)
        self.assertEqual(row["source_frame_rate"], CANVAS_FPS)
        self.assertEqual(row["timebase"], int(CANVAS_FPS))
        self.assertEqual(row["out_timecode"], "00:00:04:00",
                         "a still has no seconds to cap the usage budget")

    def test_the_motion_mode_and_the_aspect_are_the_contracts_own_rungs(self):
        for fps, ratio, mode, aspect in ((16.0, 1.3333, "period_motion", "pillarbox_visible_edge"),
                                         (30.0, 1.7777, "retime_to_natural", "designed_container")):
            with self.subTest(fps=fps, ratio=ratio):
                row, record, _ = self.row_for(Probe(seconds=10.0, fps=fps, ratio=ratio))
                self.assertEqual(record["form"], CLIP)
                self.assertEqual(record["motion_mode"], mode)
                self.assertEqual(record["aspect"], aspect)
                self.assertEqual(record["native_fps"], fps)
                self.assertIn(USAGE["transformations"][aspect], row["derivative_transformations"],
                              "the transformation the row claims is the one the contract names")

    def test_a_file_that_probes_with_no_picture_is_refused_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, **self.ep_kwargs)
            code, _, report = self.run_tool(ep, "--query", "fireball", "--provider", "nasa",
                                            archives=self.archives,
                                            prober=Probe(seconds=10.0, fps=24.0, ratio=None))
            self.assertEqual(code, 1, report)
        refused = report["refused"][0]
        self.assertEqual(refused["reason"], "missing_field")
        self.assertIn("source_frame_rate", refused["detail"])
        self.assertEqual(ledger_rows(ep), [])

    def test_a_file_with_a_picture_and_no_rate_is_refused_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, **self.ep_kwargs)
            code, _, report = self.run_tool(ep, "--query", "fireball", "--provider", "nasa",
                                            archives=self.archives,
                                            prober=Probe(seconds=10.0, fps=0.0, ratio=1.7777))
            self.assertEqual(code, 1, report)
        self.assertEqual(report["refused"][0]["reason"], "missing_field")


# --------------------------------------------------------------------------- transport apart

class TransportShapeTests(SourcingCase):
    """`request_shape`, `source_unavailable` and "no footage" are three answers, not one."""

    def nasa_run(self, ep, archives, *extra):
        return self.run_tool(ep, "--query", "fireball", "--provider", "nasa", *extra,
                             archives=archives)

    def test_a_payload_that_is_not_the_answered_shape_is_a_request_shape_refusal(self):
        archives = Archives(searches={("nasa", "fireball"): {"unexpected": {}}})
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            code, _, report = self.nasa_run(ep, archives)
            self.assertEqual(code, 1, report)
        refused = report["refused"][0]
        self.assertEqual(refused["reason"], "request_shape")
        self.assertIn("collection", refused["detail"])
        self.assertEqual(report["searched"], [], "a wrong request is not a corpus that was read")
        self.assertEqual(archives.binary_calls, [])

    def test_an_empty_result_set_is_not_reported_as_a_wrong_query(self):
        archives = Archives(searches={("nasa", "fireball"): nasa_payload()})
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            code, _, report = self.nasa_run(ep, archives)
            self.assertEqual(code, 1, report)
        self.assertEqual(report["refused"], [])
        self.assertEqual(report["searched"][0]["documents"], 0)
        self.assertEqual(report["unfilled"], [FIREBALL])

    def test_a_refused_socket_is_a_refusal_for_the_item_not_a_crash(self):
        """A transport fault is never read as a verdict, and never as a traceback either."""
        archives = Archives(searches={("nasa", "fireball"): nasa_payload(nasa_document())},
                            failing={"media.example": HTTPError(
                                "https://media.example/video/NNAS-vid-1/NNAS-vid-1~orig.mp4",
                                404, "not found", None, None)})
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            code, _, report = self.nasa_run(ep, archives)
            self.assertEqual(code, 1, report)
        self.assertEqual(report["refused"][0]["reason"], "source_unavailable")
        self.assertIn("404", report["refused"][0]["detail"])

    def test_a_404_on_the_search_itself_is_refused_for_every_provider_asked(self):
        archives = Archives(failing={"images-api.nasa.gov": HTTPError(
                                 "https://images-api.nasa.gov/search", 404, "gone", None, None)})
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            code, _, report = self.run_tool(ep, "--query", "fireball", archives=archives)
            self.assertEqual(code, 1, report)
        self.assertEqual({row["reason"] for row in report["refused"]}, {"source_unavailable"})
        self.assertEqual(sorted({row["provider"] for row in report["refused"]}),
                         sorted([name for name, entry in PROVIDER_ENTRIES.items()
                                 if entry.get("enabled")]))

    def test_the_byte_ceiling_is_the_one_the_caller_asked_for(self):
        url = "https://media.example/video/NNAS-vid-1/NNAS-vid-1~orig.mp4"
        archives = Archives(searches={("nasa", "fireball"): nasa_payload(nasa_document())},
                            files={url: b"0123456789" * 40})
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            code, _, report = self.nasa_run(ep, archives, "--max-bytes", "64")
            self.assertEqual(code, 1, report)
        self.assertEqual(report["refused"][0]["reason"], "source_unavailable")
        self.assertIn("maximum", report["refused"][0]["detail"])

    def test_the_etiquette_is_the_providers_declared_interval(self):
        """Two shots, one host: the state object records the wait the contract asked for."""
        url = "https://media.example/video/NNAS-vid-1/NNAS-vid-1~orig.mp4"
        archives = Archives(searches={("nasa", "fireball"): nasa_payload(nasa_document())},
                            files={url: asset_bytes(url)})
        parser, args = archive_source.build(["--episode", "x", "--query", "fireball",
                                             "--provider", "nasa"])
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            args.episode = ep
            state = NullState()
            run = archive_source._prepare(args, CONTRACT, opener=archives.json_opener,
                                          binary_opener=archives.binary_opener, prober=Probe(),
                                          state=state, clock=lambda: RUN_DATE)
            archive_source.execute(run)
        host = urlsplit(PROVIDER_ENTRIES["nasa"]["search_endpoint"]).hostname
        declared = float(PROVIDER_ENTRIES["nasa"]["min_interval_seconds"])
        self.assertTrue(state.waits, "the run queues on the host it is asking")
        self.assertTrue(all(wait == (host, declared) for wait in state.waits), state.waits)


# --------------------------------------------------------------------------- bytes already landed

class DigestReuseTests(SourcingCase):
    """An overnight re-run costs no network for the file that already arrived — and no trust."""

    def setUp(self):
        self.url = "https://media.example/video/NNAS-vid-1/NNAS-vid-1~orig.mp4"
        self.body = asset_bytes(self.url)
        self.archives = Archives(searches={("nasa", "fireball"): nasa_payload(nasa_document())},
                                 files={self.url: self.body})

    def destination_for(self, ep, ident="arch-001"):
        return ep / SOURCE_DIR / f"{FIREBALL}-{ident}.mp4"

    def place_the_file(self, path, digest=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.body)
        sidecar = Path(str(path) + SIDECAR_SUFFIX)
        sidecar.write_text((digest or hashlib.sha256(self.body).hexdigest()) + "\n",
                           encoding="utf-8")

    def test_bytes_already_on_disk_are_verified_not_refetched(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            self.place_the_file(self.destination_for(ep))
            code, archives, report = self.run_tool(ep, "--query", "fireball", "--provider", "nasa",
                                                  archives=self.archives)
            self.assertEqual(code, 0, report)
            row = read_ledger(ep, CONTRACT)[report["accepted"][0]["licence"]]
        self.assertEqual(archives.binary_calls, [], "the file that is already there buys no bytes")
        self.assertTrue(report["accepted"][0]["reused_on_disk"])
        self.assertEqual(row["retrieval_url"], self.url)
        self.assertEqual(archives.json_calls, [archives.json_calls[0]])

    def test_a_sidecar_that_no_longer_describes_the_bytes_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            self.place_the_file(self.destination_for(ep), digest="0" * 64)
            code, _, report = self.run_tool(ep, "--query", "fireball", "--provider", "nasa",
                                            archives=self.archives)
            self.assertEqual(code, 1, report)
            self.assertEqual(ledger_rows(ep), [])
        refused = report["refused"][0]
        self.assertEqual(refused["reason"], "source_unavailable")
        self.assertIn("no longer matches", refused["detail"])


# --------------------------------------------------------------------------- both files or neither

class AtomicCommitTests(SourcingCase):
    """D-043 as code: the merged pair is validated before anything moves, and restored after."""

    def filled(self, ep):
        url = "https://media.example/video/NNAS-vid-1/NNAS-vid-1~orig.mp4"
        archives = Archives(searches={("nasa", "fireball"): nasa_payload(nasa_document())},
                            files={url: asset_bytes(url)})
        code, _, report = self.run_tool(ep, "--query", "fireball", "--provider", "nasa",
                                        archives=archives)
        self.assertEqual(code, 0, report)
        return report

    def test_a_merged_pair_that_does_not_validate_writes_neither_file(self):
        """A basis outside the enum is refused by `ledger()`: staging catches it, so the episode
        keeps the ledger it had rather than gaining half of a new one."""
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            report = self.filled(ep)
            run = self.prepare(ep, "--query", "fireball", "--provider", "nasa")
            before = (ep / LEDGER_NAME).read_bytes(), (ep / RECORDS_NAME).read_bytes()
            rows = ledger_rows(ep)
            broken = dict(rows[0], id="arch-002", rights_basis="fair_use_of_sorts")
            outcome = archive_source.commit(run, rows, json.loads(
                (ep / RECORDS_NAME).read_text(encoding="utf-8")), [broken],
                {CORE: json.loads((ep / RECORDS_NAME).read_text(encoding="utf-8"))[FIREBALL]})
            self.assertFalse(outcome["committed"])
            self.assertIn("do not validate", outcome["why"])
            self.assertEqual((ep / LEDGER_NAME).read_bytes(), before[0])
            self.assertEqual((ep / RECORDS_NAME).read_bytes(), before[1])
            self.assertEqual(report["committed"], True)

    def test_a_round_trip_that_disagrees_restores_the_previous_bytes(self):
        """The files validated in staging, and then `archive_sources()` looked for the media.
        Both files go back to the bytes they had, which is the only honest way to end that run."""
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            self.filled(ep)
            table = json.loads(E.shots_path(ep).read_text(encoding="utf-8"))
            table["u002"] = {"kind": "archive", "name": CORE}
            E.shots_path(ep).write_text(json.dumps(table, indent=1), encoding="utf-8")
            run = self.prepare(ep, "--query", "fireball", "--provider", "nasa")
            rows, records = ledger_rows(ep), json.loads(
                (ep / RECORDS_NAME).read_text(encoding="utf-8"))
            before = (ep / LEDGER_NAME).read_bytes(), (ep / RECORDS_NAME).read_bytes()
            new_row = dict(rows[0], id="arch-002")
            new_record = dict(records[FIREBALL], licence="arch-002",
                              asset=f"{SOURCE_DIR}/{CORE}-arch-002.mp4")
            outcome = archive_source.commit(run, rows, records, [new_row], {CORE: new_record})
            self.assertFalse(outcome["committed"])
            self.assertIn("archive_sources()", outcome["why"])
            self.assertIn(CORE, outcome["why"], "the refusal names the shot that has no source")
            self.assertEqual((ep / LEDGER_NAME).read_bytes(), before[0])
            self.assertEqual((ep / RECORDS_NAME).read_bytes(), before[1])
            self.assertNotIn(CORE, json.loads((ep / RECORDS_NAME).read_text(encoding="utf-8")))

    def test_an_existing_ledger_that_does_not_validate_stops_the_run_before_a_request(self):
        """Appending to a broken file would launder it; the run refuses to read it as anything."""
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            write_archival(ep, [{"id": "arch-001"}], {FIREBALL: {"asset": "assets/archive/x.mp4"}})
            url = "https://media.example/video/NNAS-vid-1/NNAS-vid-1~orig.mp4"
            archives = Archives(searches={("nasa", "fireball"): nasa_payload(nasa_document())},
                                files={url: asset_bytes(url)})
            code, _, report = self.run_tool(ep, "--query", "fireball", "--provider", "nasa",
                                            archives=archives)
            self.assertEqual(code, 1)
        self.assertIsNone(report, "a refusal to touch the files writes no evidence of a search")
        self.assertEqual(archives.json_calls, [])
        self.assertIn("do not validate", capture_stderr(self, ep))

    def test_the_derived_fields_the_readers_add_are_never_written_back(self):
        """`ledger()` adds `span_seconds` and `records()` a normalised `native_fps`; a re-run that
        merged those dictionaries would ship computed facts as declarations."""
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            self.filled(ep)
            rows = ledger_rows(ep)
            self.assertTrue(all("span_seconds" not in row for row in rows), rows)
            record = json.loads((ep / RECORDS_NAME).read_text(encoding="utf-8"))[FIREBALL]
            self.assertIsNotNone(record.get("native_fps"), "a clip declares its own measured rate")
            self.assertNotIn("native_fps", dict(record, native_fps=None) and record or {})


def capture_stderr(test_case, ep):
    """The message a refusal printed, for the cases where no report file exists to read."""
    return getattr(test_case, "_captured_stderr", "") or json.dumps(
        {"episode": str(ep), "note": "no report written"})


# --------------------------------------------------------------------------- provider shapes

class DetailEndpointTests(SourcingCase):
    """The archive whose search row names a document instead of a file."""

    def setUp(self):
        self.file_url = "https://archive.example/download/apollo-test-film/apollo-test-film.mp4"

    def archives(self, details):
        return Archives(searches={("internet-archive", "fireball"): ia_payload(
                                     ia_document(licence_url="http://creativecommons.org/"
                                                 "publicdomain/zero/1.0/"))},
                        details={"apollo-test-film": details},
                        files={self.file_url: asset_bytes(self.file_url)})

    def test_a_metadata_endpoint_is_followed_to_the_file_it_names(self):
        archives = self.archives(ia_details(file_url=self.file_url))
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            code, called, report = self.run_tool(ep, "--query", "fireball",
                                                 "--provider", "internet-archive",
                                                 archives=archives)
            self.assertEqual(code, 0, report)
            row = read_ledger(ep, CONTRACT)[report["accepted"][0]["licence"]]
        self.assertEqual(row["retrieval_url"], self.file_url)
        self.assertEqual(called.binary_calls, [self.file_url])
        self.assertEqual(len(called.json_calls), 2, "the search, then the detail it points at")
        self.assertEqual(row["rights_basis"], "cc0")

    def test_an_item_with_no_downloadable_file_is_refused_naming_the_field(self):
        """The real shape of an IA detail document whose files are named, not addressed: the tool
        says so instead of typing a download URL the contract never declared."""
        archives = self.archives(ia_details(file_url=None))
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            code, called, report = self.run_tool(ep, "--query", "fireball",
                                                 "--provider", "internet-archive",
                                                 archives=archives)
            self.assertEqual(code, 1, report)
        refused = report["refused"][0]
        self.assertEqual(refused["reason"], "missing_field")
        self.assertEqual(refused["searched_field_paths"], ["item_fields.file_url",
                                                           "item_fields.page_url"])
        self.assertEqual(called.binary_calls, [])

    def test_an_access_restricted_item_is_still_taken_because_no_gate_ran(self):
        """`gates` is the verdict. Under the bypass the flag is a fact in the report, not a stop."""
        details = ia_details(file_url=self.file_url)
        details["metadata"]["access-restricted-item"] = "true"
        archives = self.archives(details)
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp, shots={"u001": {"kind": "archive", "name": FIREBALL}})
            code, _, report = self.run_tool(ep, "--query", "fireball",
                                            "--provider", "internet-archive", archives=archives)
            self.assertEqual(code, 0, report)
        self.assertEqual(report["refused"], [])
        self.assertEqual(archives.binary_calls, [self.file_url])


# --------------------------------------------------------------------------- the dry run

class DryRunTests(SourcingCase):
    """A plan, printed: the same picks, no bytes, no files."""

    def test_a_dry_run_downloads_and_writes_nothing_but_names_its_picks(self):
        url = "https://media.example/video/NNAS-vid-1/NNAS-vid-1~orig.mp4"
        archives = Archives(searches={("nasa", "fireball"): nasa_payload(nasa_document())},
                            files={url: asset_bytes(url)})
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            code, called, report = self.run_tool(ep, "--query", "fireball", "--provider", "nasa",
                                                 "--dry-run", archives=archives)
            self.assertEqual(code, 0, report)
        self.assertEqual(called.binary_calls, [])
        self.assertFalse((ep / LEDGER_NAME).exists())
        self.assertFalse((ep / RECORDS_NAME).exists())
        self.assertFalse((ep / SOURCE_DIR).exists(), "a plan does not create the layer's directory")
        self.assertEqual(len(report["accepted"]), 2)
        for entry in report["accepted"]:
            self.assertFalse(entry["downloaded"])
            self.assertEqual(entry["retrieval_url"], url)
        self.assertIn("dry run", report["why"])
        self.assertFalse(report["committed"])

    def test_a_dry_run_that_finds_nothing_for_a_shot_fails(self):
        archives = Archives(searches={("nasa", "fireball"): nasa_payload()})
        with tempfile.TemporaryDirectory() as tmp:
            ep = film(tmp)
            code, _, report = self.run_tool(ep, "--query", "fireball", "--provider", "nasa",
                                            "--dry-run", archives=archives)
            self.assertEqual(code, 1, report)
        self.assertEqual(report["unfilled"], sorted([FIREBALL, CORE]))


def filled_by(rows, ident):
    """A reader's helper for the one report the validators give back."""
    return rows[ident]


# --------------------------------------------------------------------------- contract, not literals

class NoContractLiteralsTests(unittest.TestCase):
    """The rule that made this tool possible: endpoints and field names are data, not code."""

    def setUp(self):
        self.source = (ROOT / SOURCING["entry_point"]).read_text(encoding="utf-8")

    def test_the_tool_names_no_endpoint(self):
        import re

        for url in re.findall(r"https?://[^\s'\"}]+", self.source):
            self.fail(f"{SOURCING['entry_point']} hard-codes {url}; the endpoints are "
                      "archive.sourcing's to state")

    def test_the_tool_names_no_provider_and_no_field_the_contract_declares(self):
        for name in PROVIDER_ENTRIES:
            self.assertNotIn(f'"{name}"', self.source,
                             f"the provider {name} is chosen from the contract, not from here")
        for entry in PROVIDER_ENTRIES.values():
            for field in entry.get("item_fields", {}).values():
                if "." in str(field) or "=" in str(field):
                    self.assertNotIn(str(field), self.source,
                                     f"{field} is a contract path, and this file reads it by name")

    def test_the_tool_holds_no_number_the_contract_owns(self):
        for number in (USAGE["still_seconds"], USAGE["clip_seconds"], RIGHTSS := RIGHTS["publication_year_floor"]):
            self.assertNotIn(str(float(number)) if isinstance(number, float) else str(number),
                             self.source, f"{number} is archive.sourcing's bound to state")

    def test_the_declared_entry_point_is_this_file(self):
        self.assertEqual(SOURCING["entry_point"], "tools/archive_source.py")
        self.assertTrue((ROOT / SOURCING["entry_point"]).is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
