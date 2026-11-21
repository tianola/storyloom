"""Characters who speak in their own voice: speaker tags in narration.md, per-line voices in the
Kokoro request and manifest, respelling for synthesis only, and the script gate's cast and
dramatisation checks."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "python"))
import make_episode  # noqa: E402
import narrate  # noqa: E402
import qc_script as Q  # noqa: E402

SOURCES = ("| Claim ID | Exact claim | Source URL | Publisher | Publication date | Source tier | Supporting quotation | Verification status |\n"
           "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
           "| c1 | a fact | https://example.org/a | Example | 2024-01-01 | 1 | quote | verified |\n"
           "| c2 | a rumour | https://example.org/b | Example | 2024-01-01 | 3 | quote | unverified |\n")

LINES = ["Vienna, eighteen forty six.",
         "[semmelweis] They breathe the same air as the women next door.",
         "[semmelweis:thought] Why here, and not there?",
         "Nobody had an answer."]


def episode(lines=LINES, cast=None, dram=None, pronounce=None):
    tmp = tempfile.TemporaryDirectory()
    ep = Path(tmp.name)
    (ep / "script").mkdir()
    (ep / "research").mkdir()
    (ep / "script" / "narration.md").write_text("\n".join(lines), encoding="utf-8")
    (ep / "research" / "sources.md").write_text(SOURCES, encoding="utf-8")
    for name, value in (("cast.json", cast), ("dramatisation.json", dram), ("pronounce.json", pronounce)):
        if value is not None:
            (ep / "script" / name).write_text(json.dumps(value), encoding="utf-8")
    return tmp, ep


CAST = {"narrator": {"voice": "af_heart"}, "semmelweis": {"voice": "bm_george", "sprite": "semmelweis"}}
DRAM = {"u002": {"basis": ["c1"], "note": "words imagined"}, "u003": {"basis": ["c1"], "note": "inner voice imagined"}}


def found(report, rule):
    return {(f["rule"], f["line"]) for f in report["findings"] if f["severity"] == "error" and f["rule"] == rule}


class Tags(unittest.TestCase):
    def test_tags_are_parsed_and_stripped(self):
        tmp, ep = episode()
        with tmp:
            lines = Q.read_lines(ep)
            self.assertEqual({k: lines["u001"][k] for k in ("speaker", "mode", "text")},
                             {"speaker": "narrator", "mode": "say", "text": LINES[0]})
            self.assertEqual(lines["u002"]["speaker"], "semmelweis")
            self.assertEqual(lines["u003"]["mode"], "thought")
            script = Q.read_script(ep)
            self.assertFalse(any("[" in t for t in script.values()))
            self.assertEqual(script["u003"], "Why here, and not there?")

    def test_directions_are_not_words(self):
        tmp, ep = episode(["[semmelweis] {frustrated} But they breathe the same air! {quietly} So it cannot be."])
        with tmp:
            line = Q.read_lines(ep)["u001"]
            self.assertEqual(line["text"], "But they breathe the same air! So it cannot be.")
            self.assertEqual(line["directed"], "[frustrated] But they breathe the same air! [quietly] So it cannot be.")

    def test_bracket_that_is_not_a_tag_stays_text(self):
        tmp, ep = episode(["[Applause] is not a speaker."])
        with tmp:
            self.assertEqual(Q.read_lines(ep)["u001"]["speaker"], "narrator")


class CastGate(unittest.TestCase):
    def test_clean_cast_passes(self):
        tmp, ep = episode(cast=CAST, dram=DRAM)
        with tmp:
            report = Q.check(ep)
            self.assertFalse(found(report, "cast") | found(report, "dramatisation"))

    def test_unknown_speaker_is_an_error(self):
        tmp, ep = episode(cast={"narrator": {"voice": "af_heart"}}, dram=DRAM)
        with tmp:
            self.assertIn(("cast", "u002"), found(Q.check(ep), "cast"))

    def test_non_english_voice_is_an_error(self):
        tmp, ep = episode(cast={**CAST, "semmelweis": {"voice": "ef_dora"}}, dram=DRAM)
        with tmp:
            self.assertIn(("cast", None), found(Q.check(ep), "cast"))

    def test_character_line_needs_dramatisation(self):
        tmp, ep = episode(cast=CAST, dram={"u002": DRAM["u002"]})
        with tmp:
            self.assertEqual(found(Q.check(ep), "dramatisation"), {("dramatisation", "u003")})

    def test_dramatisation_must_rest_on_verified_claims(self):
        tmp, ep = episode(cast=CAST, dram={**DRAM, "u002": {"basis": ["c2"], "note": "x"}})
        with tmp:
            self.assertEqual(found(Q.check(ep), "dramatisation"), {("dramatisation", "u002")})


class Request(unittest.TestCase):
    def test_voices_follow_the_cast_and_narrator_is_default(self):
        tmp, ep = episode(cast=CAST, pronounce={"Vienna": "Veeyenna"})
        with tmp:
            req = make_episode.narration_request(ep)
            self.assertEqual(req["voice"], "af_heart")
            u1, u2, u3, _ = req["utterances"]
            self.assertNotIn("voice", u1)
            self.assertEqual(u1["text"], LINES[0])
            self.assertEqual(u1["spoken"], "Veeyenna, eighteen forty six.")
            self.assertEqual((u2["speaker"], u2["voice"], u2["mode"]), ("semmelweis", "bm_george", "say"))
            self.assertEqual(u3["mode"], "thought")
            narrate.validate_request(req)

    def test_respelling_keeps_punctuation_and_possessive(self):
        self.assertEqual(make_episode.respell("Semmelweis's ward, Semmelweis.", {"Semmelweis": "Semmelvice"}),
                         "Semmelvice's ward, Semmelvice.")
        self.assertEqual(make_episode.respell("Ignaz", {"Ignaz": "two words"}), "Ignaz")


class Cloud(unittest.TestCase):
    ALIGN = {"characters": list("[soft] Bad air."), "character_start_times_seconds": [0.1 * i for i in range(15)],
             "character_end_times_seconds": [0.1 * i + 0.1 for i in range(15)]}

    def test_cache_means_one_call_per_line(self):
        import base64
        import eleven
        calls = []

        def fetch(voice_id, body):
            calls.append(body)
            return {"audio_base64": base64.b64encode(bytes(480)).decode(), "alignment": self.ALIGN}
        with tempfile.TemporaryDirectory() as d:
            e = eleven.ElevenEngine(Path(d), fetch=fetch)
            a, rate = e.create("[soft] Bad air.", "eleven:EXAVITQu4vr4xnSDxMaL")
            e2 = eleven.ElevenEngine(Path(d), fetch=fetch)
            e2.create("[soft] Bad air.", "eleven:EXAVITQu4vr4xnSDxMaL")
            self.assertEqual((len(calls), rate, len(a)), (1, 24000, 240))
            self.assertEqual(e2.last_alignment, self.ALIGN)

    def test_marks_skip_directions(self):
        import eleven
        self.assertEqual([w for w, _, _ in eleven.word_marks("Bad air.", self.ALIGN)], ["Bad", "air."])
        self.assertAlmostEqual(eleven.word_marks("Bad air.", self.ALIGN)[0][1], 0.7)
        self.assertNotIn("[", "".join(c for c, _, _ in eleven.phones(self.ALIGN)))

    def test_long_pause_is_shortened_and_marks_follow(self):
        import numpy
        import eleven
        rate = 24000
        tone = (0.3 * numpy.sin(numpy.arange(rate // 2) * 0.3)).astype(numpy.float32)   # 0.5 s of sound
        pcm = numpy.concatenate([numpy.zeros(rate // 2, numpy.float32), tone,
                                 numpy.zeros(2 * rate, numpy.float32), tone, numpy.zeros(rate, numpy.float32)])
        align = {"characters": ["a", "b"], "character_start_times_seconds": [0.5, 3.0],
                 "character_end_times_seconds": [1.0, 3.5]}
        out, moved = eleven.tighten(pcm, align, rate)
        # 0.05 lead + 0.5 + 0.4 pause + 0.5 + 0.12 tail
        self.assertAlmostEqual(len(out) / rate, 1.57, delta=0.03)
        self.assertAlmostEqual(moved["character_start_times_seconds"][0], 0.05, delta=0.02)
        self.assertAlmostEqual(moved["character_start_times_seconds"][1], 0.95, delta=0.02)
        self.assertAlmostEqual(moved["character_end_times_seconds"][1], 1.45, delta=0.02)

    def test_cast_speed_reaches_the_voice_settings(self):
        import base64
        import eleven
        bodies = []
        tmp, ep = episode(cast=dict(CAST, narrator={"voice": "eleven:EXAVITQu4vr4xnSDxMaL", "speed": 1.15}))
        with tmp:
            req = make_episode.narration_request(ep)
            narrate.validate_request(req)
            self.assertEqual(req["utterances"][0]["speed"], 1.15)
            self.assertNotIn("speed", req["utterances"][1])
        with tempfile.TemporaryDirectory() as d:
            e = eleven.ElevenEngine(Path(d), fetch=lambda v, b: bodies.append(b) or
                                    {"audio_base64": base64.b64encode(bytes(480)).decode(), "alignment": self.ALIGN})
            e.create("Bad air.", "eleven:EXAVITQu4vr4xnSDxMaL", speed=1.15)
            e.create("Bad air.", "eleven:EXAVITQu4vr4xnSDxMaL", speed=1.0)
        self.assertEqual(bodies[0]["voice_settings"]["speed"], 1.15)
        self.assertNotIn("speed", bodies[1]["voice_settings"])

    def test_directed_line_may_differ_in_words_for_eleven_only(self):
        req = {"voice": "af_heart", "speed": 1.0, "utterances": [
            {"id": "u001", "file": "u001.wav", "text": "Bad air.", "spoken": "[soft] Bad air.", "voice": "eleven:EXAVITQu4vr4xnSDxMaL"}]}
        narrate.validate_request(req)
        req["utterances"][0]["voice"] = "bm_george"
        with self.assertRaises(ValueError):
            narrate.validate_request(req)


class Engine:
    sample_rate = 24000
    voices = ["af_heart", "bm_george"]

    def __init__(self):
        self.calls = []

    def create(self, text, voice, speed=1.0):
        self.calls.append((text, voice))
        return [0.1] * 240, 24000


class Synthesis(unittest.TestCase):
    def request(self, **extra):
        return {"voice": "af_heart", "speed": 1.0, "utterances": [
            {"id": "u001", "file": "u001.wav", "text": "Plain line."},
            {"id": "u002", "file": "u002.wav", "text": "Vienna again.", "spoken": "Veeyenna again.",
             "speaker": "semmelweis", "voice": "bm_george", "mode": "say", **extra}]}

    def test_each_line_in_its_own_voice_and_spoken_text(self):
        with tempfile.TemporaryDirectory() as d:
            engine = Engine()
            manifest = narrate.synthesize(self.request(), d, engine)
            self.assertEqual(engine.calls, [("Plain line.", "af_heart"), ("Veeyenna again.", "bm_george")])
            u1, u2 = manifest["utterances"]
            self.assertNotIn("speaker", u1)
            self.assertEqual((u2["speaker"], u2["voice"], u2["mode"], u2["text"]),
                             ("semmelweis", "bm_george", "say", "Vienna again."))

    def test_uninstalled_or_foreign_voice_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                narrate.synthesize(self.request(voice="bm_lewis"), d, Engine())
        with self.assertRaises(ValueError):
            narrate.validate_request(self.request(voice="ef_dora"))

    def test_respelling_must_keep_the_word_count(self):
        bad = self.request()
        bad["utterances"][1]["spoken"] = "Vee yenna again."
        with self.assertRaises(ValueError):
            narrate.validate_request(bad)


if __name__ == "__main__":
    unittest.main()
