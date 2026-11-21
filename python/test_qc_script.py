"""Script gate: each rule fires on a script built to break it, and passes one built to satisfy it."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import qc_script as Q  # noqa: E402

CONTRACT = Q.load_contract()
SOURCES = ("# Sources\n\n| Claim ID | Exact claim | Source URL | Publisher | Publication date | Source tier | Supporting quotation | Verification status |\n"
           "| --- | --- | --- | --- | --- | --- | --- | --- |\n"
           "| c1 | a fact | https://example.org/a | Example | 2024-01-01 | 1 | quote | verified |\n"
           "| c2 | a rumour | https://example.org/b | Example | 2024-01-01 | 3 | quote | unverified |\n")


def episode(lines, chapters=None, claims=None, sources=SOURCES):
    tmp = tempfile.TemporaryDirectory()
    ep = Path(tmp.name)
    (ep / "script").mkdir()
    (ep / "research").mkdir()
    (ep / "script" / "narration.md").write_text("\n".join(lines), encoding="utf-8")
    (ep / "research" / "sources.md").write_text(sources, encoding="utf-8")
    if chapters is not None:
        (ep / "script" / "chapters.json").write_text(json.dumps({"chapters": chapters}), encoding="utf-8")
    if claims is not None:
        (ep / "script" / "claims.json").write_text(json.dumps(claims), encoding="utf-8")
    return tmp, ep


def rules(report, severity="error"):
    return {(f["rule"], f["line"]) for f in report["findings"] if f["severity"] == severity}


def long_script(seconds):
    n = int(seconds * CONTRACT["script"]["words_per_second"] / 10)
    return [f"Line {i} " + " ".join(["word"] * 8) + "." for i in range(n)]


# Ten lines with the measured shape of the reference films: a question, two turns, two named
# people, one number, and the thing we follow (the lamp) in most lines.
STORY_CYCLE = [
    "Why does the old lamp flicker every night at nine?",
    "The lamp looks fine from the outside, so people blame the bulb.",
    "Ada Lovelace opened the lamp and found the wires were clean.",
    "But the flicker came back the next evening, right on time.",
    "Grace Hopper checked the street and saw the trams pass by.",
    "Each tram pulls a lot of power from the same line.",
    "That turns out to be the whole story of the lamp.",
    "The voltage sags, the filament cools, and the light dips.",
    "The tram schedule had about forty departures in the evening.",
    "So the lamp was keeping time with the trams all along.",
]


def story_episode(cycle, story="default"):
    lines = cycle * max(1, int(700 * CONTRACT["script"]["words_per_second"] / sum(len(l.split()) for l in cycle)))
    n = len(lines)
    tmp, ep = episode(lines, chapters=[{"title": "a", "from": "u001"}, {"title": "b", "from": f"u{n // 3:03d}"},
                                       {"title": "c", "from": f"u{2 * n // 3:03d}"}],
                      claims={f"u{i:03d}": ["c1"] for i in range(1, n + 1)})
    if story == "default":
        story = {"question": "u001", "payoff": f"u{n:03d}", "follow": "lamp",
                 "guess": "u002", "reversal": f"u{(n // 2) // 10 * 10 + 4:03d}",   # "But the flicker came back"
                 "hook": {"kind": "mystery", "image": "a street lamp dimming at nine sharp"},
                 "people": [{"name": "Ada Lovelace", "line": "u003"}, {"name": "Grace Hopper", "line": "u005"}]}
    if story is not None:
        (ep / "script" / "story.json").write_text(json.dumps(story), encoding="utf-8")
    return tmp, ep


class ScriptGate(unittest.TestCase):
    def test_jensen_is_too_short_and_its_personal_life_line_is_named(self):
        report = Q.check(ROOT / "work" / "jensen-huang")
        errors = rules(report)
        self.assertIn(("length", None), errors)
        self.assertIn(("sensitive", "u018"), errors)
        self.assertIn(("unsourced", "u001"), errors)
        self.assertIn(("hook", "u001"), errors)
        self.assertIn(("chapters", None), errors)

    def test_a_long_sourced_chaptered_story_passes(self):
        tmp, ep = story_episode(STORY_CYCLE)
        with tmp:
            report = Q.check(ep)
        self.assertEqual(rules(report), set(), report["findings"][:3])

    def test_a_fact_list_fails_the_story_rules(self):
        """The shape of the rejected ask-chatgpt cut: numbers in every line, nothing breaks, no one in it."""
        facts = [f"The chip moves about {w} gigabytes of weights per token today." for w in
                 ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]]
        tmp, ep = story_episode(facts, story=None)
        with tmp:
            report = Q.check(ep)
        messages = " ".join(f["message"] for f in report["findings"] if f["rule"] == "story")
        for expected in ("carry a number", "in a row", "turns", "story.json"):
            self.assertIn(expected, messages)

    def test_a_late_question_and_an_empty_cast_are_named(self):
        tmp, ep = story_episode(STORY_CYCLE, story={"question": "u021", "payoff": "u001", "follow": "lamp", "people": []})
        with tmp:
            report = Q.check(ep)
        messages = " ".join(f["message"] for f in report["findings"] if f["rule"] == "story")
        self.assertIn("has to be open by", messages)
        self.assertIn("real people", messages)
        self.assertIn(("story", "u001"), rules(report, "warn"))    # payoff before the last fifth

    def test_an_answer_given_up_front_has_no_turn_to_break(self):
        """No guess and reversal declared, then a reversal too early, too late and with no turn word."""
        base = {"question": "u001", "follow": "lamp",
                "people": [{"name": "Ada Lovelace", "line": "u003"}, {"name": "Grace Hopper", "line": "u005"}]}
        tmp, ep = story_episode(STORY_CYCLE, story=base)
        with tmp:
            messages = " ".join(f["message"] for f in Q.check(ep)["findings"] if f["rule"] == "story")
        self.assertIn("needs 'guess'", messages)
        tmp, ep = story_episode(STORY_CYCLE, story={**base, "guess": "u002", "reversal": "u004"})
        with tmp:
            report = Q.check(ep)
        self.assertIn(("story", "u004"), rules(report))          # breaks the guess before it is believed
        tmp, ep = story_episode(STORY_CYCLE, story={**base, "guess": "u002", "reversal": "u046"})
        with tmp:
            report = Q.check(ep)
        messages = " ".join(f["message"] for f in report["findings"] if f["rule"] == "story")
        self.assertIn("no turn in it", messages)                    # "Each tram pulls a lot of power..."

    def test_a_soft_undeclared_opening_fails_the_hook(self):
        soft = ["Today we look at how a lamp works."] + STORY_CYCLE[1:]
        story = {"question": "u001", "follow": "lamp", "guess": "u002", "reversal": "u044",
                 "people": [{"name": "Ada Lovelace", "line": "u003"}, {"name": "Grace Hopper", "line": "u005"}]}
        tmp, ep = story_episode(soft, story=story)
        with tmp:
            messages = " ".join(f["message"] for f in Q.check(ep)["findings"] if f["rule"] == "hook")
        self.assertIn("needs 'hook'", messages)
        self.assertIn("soft opener ('Today')", messages)

    def test_a_shocking_opening_must_cite_a_claim(self):
        tmp, ep = story_episode(STORY_CYCLE)
        with tmp:
            story = json.loads((ep / "script" / "story.json").read_text(encoding="utf-8"))
            story["hook"]["kind"] = "shock"
            (ep / "script" / "story.json").write_text(json.dumps(story), encoding="utf-8")
            claims = json.loads((ep / "script" / "claims.json").read_text(encoding="utf-8"))
            self.assertEqual(rules(Q.check(ep)), set())                    # cited: fine
            claims["u001"] = "framing"
            (ep / "script" / "claims.json").write_text(json.dumps(claims), encoding="utf-8")
            self.assertIn(("hook", "u001"), rules(Q.check(ep)))

    def test_digits_and_symbols_fail_but_model_names_only_warn(self):
        tmp, ep = episode(["It cost $40,000 in 1993.", "The NV1 failed."], claims={"u001": "framing", "u002": "framing"})
        with tmp:
            report = Q.check(ep)
        self.assertIn(("speech", "u001"), rules(report))
        self.assertNotIn(("speech", "u002"), rules(report))
        self.assertIn(("speech", "u002"), rules(report, "warn"))

    def test_framing_lines_need_no_source_but_other_lines_need_a_verified_one(self):
        tmp, ep = episode(["Hello there friend.", "A fact.", "A rumour.", "Nothing cited."],
                          claims={"u001": "framing", "u002": ["c1"], "u003": ["c2"]})
        with tmp:
            report = Q.check(ep)
        flagged = {line for rule, line in rules(report) if rule == "unsourced"}
        self.assertEqual(flagged, {"u003", "u004"})

    def test_a_sensitive_line_cannot_hide_as_framing(self):
        tmp, ep = episode(["His marriage ended last year."], claims={"u001": "framing"})
        with tmp:
            report = Q.check(ep)
        self.assertIn(("sensitive", "u001"), rules(report))

    def test_sentence_length_warns_then_errors(self):
        tmp, ep = episode([" ".join(["word"] * 36) + ".", " ".join(["word"] * 50) + "."],
                          claims={"u001": "framing", "u002": "framing"})
        with tmp:
            report = Q.check(ep)
        self.assertIn(("sentence", "u001"), rules(report, "warn"))
        self.assertIn(("sentence", "u002"), rules(report))

    def test_chapters_must_start_at_the_first_line(self):
        tmp, ep = episode(["One fine line.", "Two fine lines.", "Three fine lines."],
                          chapters=[{"title": "a", "from": "u002"}, {"title": "b", "from": "u003"}, {"title": "c", "from": "u003"}])
        with tmp:
            report = Q.check(ep)
        self.assertIn(("chapters", None), rules(report))

    def test_the_command_fails_on_errors(self):
        with tempfile.TemporaryDirectory() as t:
            tmp, ep = episode(["Short."], claims={"u001": "framing"})
            with tmp:
                self.assertEqual(Q.main(["--episode", str(ep)]), 1)
                self.assertTrue((ep / "qc" / "script-qc.json").exists())


if __name__ == "__main__":
    unittest.main()
