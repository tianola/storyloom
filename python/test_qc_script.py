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


class ScriptGate(unittest.TestCase):
    def test_jensen_is_too_short_and_its_personal_life_line_is_named(self):
        report = Q.check(ROOT / "work" / "jensen-huang")
        errors = rules(report)
        self.assertIn(("length", None), errors)
        self.assertIn(("sensitive", "u018"), errors)
        self.assertIn(("unsourced", "u001"), errors)
        self.assertIn(("hook", "u001"), errors)
        self.assertIn(("chapters", None), errors)

    def test_a_long_sourced_chaptered_script_passes(self):
        lines = [l.replace("Line", "Number") for l in long_script(700)]
        lines = [l.replace(" 0 ", " zero ") for l in lines]
        words = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
        lines = [f"Opening {w} " + " ".join(["word"] * 8) + "." for w in words] * (len(lines) // 10)
        tmp, ep = episode(lines, chapters=[{"title": "a", "from": "u001"}, {"title": "b", "from": f"u{len(lines)//3:03d}"},
                                           {"title": "c", "from": f"u{2*len(lines)//3:03d}"}],
                          claims={f"u{i:03d}": ["c1"] for i in range(1, len(lines) + 1)})
        with tmp:
            report = Q.check(ep)
        self.assertEqual(rules(report), set(), report["findings"][:3])

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
