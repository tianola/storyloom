"""The talking cast: every cell draws at its size, mouths and eyes change only their own pixels,
the palette has every key used, and workflow/sprites.json mirrors the registry."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "pixel"))
import people as P  # noqa: E402
from sprites import PALETTE  # noqa: E402


def diff(a, b):
    return {(x, y) for y, (ra, rb) in enumerate(zip(a, b)) for x, (ca, cb) in enumerate(zip(ra, rb)) if ca != cb}


class Cells(unittest.TestCase):
    def test_every_cell_has_its_size_and_known_colours(self):
        for key, c in P.CHARACTERS.items():
            for size in P.sizes_of(key):
                w, h = {"bust": (P.BUST_W, P.BUST_H), "bed": (P.BED_W, P.BED_H)}.get(size, (P.FIG_W, P.FIG_H))
                for pose in P.poses_of(key, size):
                    for x in P.EXPRESSIONS:
                        rows = P.cell(key, pose, x, size=size)
                        self.assertEqual((len(rows[0]), len(rows)), (w, h), (key, pose, x, size))
                        used = set("".join(rows)) - {"."}
                        self.assertLessEqual(used, set(PALETTE), (key, pose, x))

    def test_mouths_change_only_the_mouth(self):
        for size, box in (("figure", (6, 11, 9, 13)), ("bust", (12, 16, 17, 20))):
            base = P.cell("explorer", size=size)
            for m in P.MOUTHS[1:]:
                for x, y in diff(base, P.cell("explorer", mouth=m, size=size)):
                    self.assertTrue(box[0] <= x <= box[2] and box[1] <= y <= box[3], (size, m, x, y))

    def test_blink_changes_only_the_eyes(self):
        for size, rows in (("figure", (8, 9)), ("bust", (10, 13))):
            changed = diff(P.cell("semmelweis", size=size), P.cell("semmelweis", eyes="blink", size=size))
            self.assertTrue(changed)
            self.assertTrue(all(rows[0] <= y <= rows[1] for _, y in changed), size)

    def test_talking_mouths_differ(self):
        shapes = [tuple(P.cell("semmelweis", mouth=m, size="bust")) for m in P.MOUTHS]
        self.assertEqual(len(set(shapes)), len(shapes))

    def test_atlas_layout_is_complete(self):
        lay = P.atlas_layout("semmelweis", "figure")
        self.assertEqual(sorted(lay["col"].values()), list(range(lay["cols"])))
        self.assertEqual(sorted(lay["row"].values()), list(range(lay["rows"])))


class Clergy(unittest.TestCase):
    def test_new_cast_and_poses(self):
        self.assertEqual(P.sizes_of("patient"), ["bed"])
        self.assertLess(P.BED_H, P.BED_W)
        self.assertTrue({"stand", "talk", "walk1", "walk2", "walk3", "walk4"} <= set(P.poses_of("priest")))
        self.assertTrue({"stand", "ring", "walk1", "walk2", "walk3", "walk4"} <= set(P.poses_of("acolyte")))
        self.assertEqual(P.poses_of("patient"), ["lie", "lie-turn"])

    def test_acolyte_is_a_boy(self):
        def height(key):
            rows = P.cell(key)
            return len(rows) - next(i for i, r in enumerate(rows) if set(r) != {"."})
        self.assertLessEqual(height("acolyte") / height("priest"), 0.85)

    def test_bell_rings_only_in_ring(self):
        self.assertNotEqual(P.cell("acolyte", "ring"), P.cell("acolyte", "stand"))

    def test_patient_face_parts_stay_in_their_boxes(self):
        for pose in P.BED_POSES:
            base = P.cell("patient", pose)
            for m in P.MOUTHS[1:]:
                for x, y in diff(base, P.cell("patient", pose, mouth=m)):
                    self.assertTrue(5 <= x <= 9 and 5 <= y <= 8, (pose, m, x, y))
            for x, y in diff(base, P.cell("patient", pose, eyes="blink")):
                self.assertEqual(y, 4)
            for e in ("worried", "sad", "neutral"):
                self.assertIn(e, P.EXPRESSIONS)
            self.assertNotEqual(P.cell("patient", pose, "worried"), P.cell("patient", pose, "sad"))


class Mirror(unittest.TestCase):
    def test_workflow_mirror_matches_the_registry(self):
        reg = json.loads((ROOT / "workflow" / "sprites.json").read_text(encoding="utf-8"))
        self.assertEqual(reg["mouths"], P.MOUTHS)
        self.assertEqual(reg["expressions"], P.EXPRESSIONS)
        self.assertEqual(reg["eyes"], P.EYES)
        self.assertEqual(reg["bust_poses"], P.BUST_POSES)
        self.assertEqual({k: (v["poses"], v["bust"]) for k, v in reg["characters"].items()},
                         {k: (v["poses"], v["bust"]) for k, v in P.CHARACTERS.items()})


if __name__ == "__main__":
    unittest.main()
