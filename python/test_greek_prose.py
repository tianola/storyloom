"""Greek prose in this project's docs is machine-checked, not promised.

The operator reads this project in Greek and has said plainly that mixed-script text is
unreadable to them («δεν καταλαβαίνω τι λες»). Four distinct defects keep recurring in prose
written by agents, and none of them is visible to the person who has to read it afterwards:

  * a character from a foreign script substituted inside a Greek word — CJK, Cyrillic, Hangul,
    Thai, Arabic. Seen as `δείγμα下`, `το说`, `已有的`.
  * a Latin word glued onto a Greek one with no space, so a technical term stops being a term
    and the syllables break. Seen as `renderάρονταν`, `μεratio`, `στο_near`.
  * an English closed-class word standing in a Greek sentence with spaces on both sides. Seen
    as `είκοσι one επίπεδα`.
  * a Greek word typed without its accents. Seen as `θελουν`, `μεσος όρος`.

All four survive a human read because the reader's eye repairs them, and the first two are
trivial to detect. The last two are why this file exists in its current shape: on 2026-11-12 a
single edit shipped three of the looser defects into PRODUCTION-GUIDE.md §10 while the
two-pattern scanner reported the file clean. A grep is only evidence for the pattern typed into
it, so the checker grew with the corpus instead of the other way round.

Content words (a render, a still, albedo, spacing) stay English — that is the house style — so
the English detector is a closed list of articles, prepositions, pronouns, auxiliaries and
numerals, which have no legitimate use inside a Greek sentence.

The test checks the files and checks itself: the two `scanner_fires` tests feed the scanner the
exact strings that shipped in this repo, so the gate cannot pass by being broken.
"""
import re
import sys
import unicodedata
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Scripts that are never part of this project's Greek prose. Greek (0370-03FF) and Latin
# (0041-007A, with the accented Latin the house style tolerates) are deliberately absent.
FOREIGN = re.compile(
    "["
    "\u3040-\u30ff"      # Hiragana, Katakana
    "\u4e00-\u9fff"      # CJK ideographs
    "\uac00-\ud7af"      # Hangul
    "\u0400-\u04ff"      # Cyrillic
    "\u0e00-\u0eff"      # Thai
    "\u0600-\u06ff"      # Arabic
    "]"
)
# A Greek letter touching a Latin one with no space between them — through an underscore
# counts, because `στο_near` is as unreadable as `στοnear` and it is what an agent typing a
# code token inside a sentence actually produces.
GLUED = re.compile("[\u0370-\u03ff][A-Za-z_]|[A-Za-z_][\u0370-\u03ff]")

# English words that carry no meaning of their own: an article, a preposition, a pronoun, an
# auxiliary, a numeral. A technical term is a noun and stays English, so a content word is not
# in here — this list has to be small enough that a hit is always a defect. "still" is
# deliberately absent: it is a house term for a rendered frame.
ENGLISH = frozenset("""a an the and or but nor so yet for with without from to in into onto on
at as by of is are was were be been being am do does did done will would shall should can could
may might must this that these those there here they them their we us our you your it its he
him his she her not no yes one two three more most less least very just than when where which
who whom whose what how why all any some each every other both many much also even only over
under again once never always too""".split())

GREEK_VOWELS = "αεηιουω"
SYLLABLE = re.compile(r"[αεηιουω]+")
LATIN_RUN = re.compile(r"[A-Za-z][A-Za-z_-]*")
GREEK_WORD = re.compile(r"[\u0370-\u03ff]+")
# Code spans, URLs and slash-paths are identifiers, not prose: `docs/plans/the-thing.md` would
# otherwise report its path segments as English words. «…» is where the guide quotes a foreign
# source verbatim, and that English is supposed to be English.
NOT_PROSE = re.compile(r"`[^`]*`|https?://\S+|\S*/\S+|«[^»]*»")


def has_accent(word):
    """True when the word carries a tonos or a dialytika, at any case.

    Comparing against a written-out list of accented letters is what produced the first version
    of this check's noise: it held the lowercase forms only, so every sentence that begins with
    Έκδοση or Ίδρυση was reported as missing its accent.
    """
    return any(c in "\u0301\u0308\u0342" for c in unicodedata.normalize("NFD", word))


def prose_only(line):
    return NOT_PROSE.sub(" ", line)


def dequoted(text):
    """Lines with every «…» range blanked, one output line per input line.

    The guide quotes its sources verbatim, and a quotation of English inside Greek prose is not
    a defect. The ranges cross lines — «their sources for / the claims» — so a per-line regex
    leaves the tail of the opening line looking like stray English in the middle of a Greek
    sentence, which is what it reported on the first run.
    """
    out, inside = [], False
    for line in text.splitlines():
        buf, i = [], 0
        while i < len(line):
            mark = "\u00bb" if inside else "\u00ab"
            j = line.find(mark, i)
            if j < 0:
                buf.append(line[i:] if not inside else " " * (len(line) - i))
                break
            buf.append(line[i:j] if not inside else " " * (j + 1 - i))
            i = j + 1
            inside = not inside
        out.append("".join(buf))
    return out


def greek_dominant(line):
    """True when the line is Greek prose, not an English sentence that quotes a Greek phrase.

    The quotes are stripped first, so a line that is English prose carrying one Greek phrase —
    «ένας κύβος και ένα τρίγωνο» rather than as hardware — has no Greek left to count and is
    out of scope, while a Greek sentence that uses three English house terms is still Greek.
    """
    text = prose_only(line)
    greek = sum("\u0370" <= c <= "\u03ff" for c in text)
    latin = sum(c.isascii() and c.isalpha() for c in text)
    return greek > latin


def english_words(line):
    """English function words sitting inside Greek prose, lowercased as they are mid-sentence.

    Only lowercase tokens count: «Plugged In» and «The European» are names of sources, and an
    English function word that begins a Greek sentence is not a thing this prose does.
    """
    if not greek_dominant(line):
        return []
    return [t for t in LATIN_RUN.findall(prose_only(line)) if t.islower() and t in ENGLISH]


def unaccented_greek(line):
    """Greek words of two or more syllables written with no tonos.

    Modern Greek puts exactly one accent on every word of two syllables or more; the
    accentless exceptions are monosyllabic (και, με, σε, του, που), and a syllable is a vowel
    *cluster*, not a vowel letter — «για», «και» and «που» are one syllable each. Counting
    letters instead reported 321 hits on clean prose. ALL-CAPS tokens are skipped: the guide
    writes the label «ΑΚΙΝΗΤΟ» the way the card on screen spells it.
    """
    if not greek_dominant(line):
        return []
    return [w for w in GREEK_WORD.findall(prose_only(line))
            if len(SYLLABLE.findall(w.lower())) >= 2 and w != w.upper()
            and not has_accent(w)]


def offenders(text):
    """(kind, line number, stripped line) for every prose defect in `text`.

    One entry per kind per line, not one per line: a single sentence can carry both a glued
    term and an unaccented word, and reporting only the first is how a fix round leaves half
    the line wrong.
    """
    hits = []
    raw = text.splitlines()
    for i, line in enumerate(dequoted(text), 1):
        if FOREIGN.search(raw[i - 1]):
            hits.append(("foreign-script", i, raw[i - 1].strip()))
        if GLUED.search(raw[i - 1]):
            hits.append(("glued-latin", i, raw[i - 1].strip()))
        if english_words(line):
            hits.append(("english-word", i, raw[i - 1].strip()))
        if unaccented_greek(line):
            hits.append(("unaccented-greek", i, raw[i - 1].strip()))
    return hits


def prose_files():
    """Every markdown file under docs/ that actually carries Greek text.

    docs/ also holds specs and plans written in English for other agents; requiring Greek in
    them would fail the wrong files, so an English file is out of scope rather than a defect.
    """
    out = []
    for path in sorted((ROOT / "docs").rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search("[\u0370-\u03ff]", text):
            out.append(path)
    return out


def _hits(files, kind):
    return [(f, o) for f in files for o in offenders(f.read_text(encoding="utf-8"))
            if o[0] == kind]


def _fmt(bad):
    return "\n".join(f"  {f.name}:{ln}  {txt[:78]}" for f, (_, ln, txt) in bad)


class GreekProse(unittest.TestCase):
    def setUp(self):
        self.files = prose_files()

    def test_there_are_greek_docs_to_check(self):
        # An empty scope would make the two tests below pass without looking at anything.
        self.assertGreaterEqual(
            len(self.files), 1,
            "no Greek markdown found under docs/ — the scope of this gate has moved")

    def test_no_foreign_script_inside_greek_prose(self):
        bad = _hits(self.files, "foreign-script")
        self.assertEqual(bad, [], "foreign-script characters in Greek prose:\n" + _fmt(bad))

    def test_no_latin_glued_inside_greek_words(self):
        bad = _hits(self.files, "glued-latin")
        self.assertEqual(bad, [], "a Latin term glued to a Greek word, with no space:\n"
                         + _fmt(bad))

    def test_scanner_fires_on_the_two_real_defects(self):
        """Every string here actually shipped in this repo, in some agent's Greek."""
        samples = [
            ("foreign-script", "το δείγμα下 γίνεται"),
            ("glued-latin", "τα beats renderάρονταν πιο γρήγορα"),
            ("glued-latin", "θεμελιώδης μεratio 2.7"),
            ("glued-latin", "η stipple στο_near plain"),
        ]
        for kind, line in samples:
            found = [k for k, _, _ in offenders(line)]
            self.assertIn(kind, found, f"scanner missed: {line!r}")

    def test_scanner_fires_on_the_two_looser_defects(self):
        """Both shipped in PRODUCTION-GUIDE.md §10 on 2026-11-12, in the same edit, while the
        two patterns above reported the file clean. An English function word with spaces around
        it and a Greek word typed without its accents are as unreadable as a glued one."""
        samples = [
            ("english-word", "είκοσι one επίπεδα"),
            ("unaccented-greek", "τα τέσσερα beats θελουν re-render"),
            ("unaccented-greek", "μεσος όρος 78"),
        ]
        for kind, line in samples:
            found = [k for k, _, _ in offenders(line)]
            self.assertIn(kind, found, f"scanner missed: {line!r}")

    def test_an_english_content_word_is_a_known_blind_spot(self):
        """`το ocupied τα sRGB` is unreadable and this scanner does not see it.

        Telling it from `το όριο του albedo` needs a judgment about which English nouns are
        house terms, and a guessed list would either flag half the guide or nothing. The rule
        that catches this class is a human read, so the limit is stated here rather than
        papered over with a list nobody maintains.
        """
        self.assertEqual(offenders("το ocupied τα sRGB 68"), [])

    def test_english_words_and_accented_greek_are_not_flagged(self):
        for line in ("Η μέτρηση λέει αλλιώς: το επίπεδο έδαφος είναι σκοτεινό.",
                     "Δύο από τα τέσσερα beats χρειάζονται re-render.",
                     "This section is written in English for another agent.",
                     "Το `min_gap` μαζί με το `size_bias` έφτιαχνε πλέγμα από λεκάνες."):
            self.assertEqual(offenders(line), [], f"false positive on {line!r}")

    def test_no_english_function_word_inside_greek_prose(self):
        bad = _hits(self.files, "english-word")
        self.assertEqual(bad, [], "an English word standing inside a Greek sentence:\n" + _fmt(bad))

    def test_no_unaccented_greek_word_inside_greek_prose(self):
        bad = _hits(self.files, "unaccented-greek")
        self.assertEqual(bad, [], "a Greek word missing its accents:\n" + _fmt(bad))

    def test_clean_greek_and_english_are_not_flagged(self):
        # Technical terms stay English, and quotes/code spans are not defects.
        for line in ("Ο `lunar_ground_probe` μετράει τον ορίζοντας.",
                     "Αυτό είναι το συμπέρασμα: τα textured beats έκαναν render γρηγορότερα.",
                     "This plan is written in English for another agent."):
            self.assertEqual(offenders(line), [], f"false positive on {line!r}")


if __name__ == "__main__":
    unittest.main()
