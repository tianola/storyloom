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


SIZES = {"figure": (P.FIG_W, P.FIG_H), "bust": (P.BUST_W, P.BUST_H), "bed": (P.BED_W, P.BED_H),
         "hands": (P.HANDS_W, P.HANDS_H)}
SHIFT_Y = {"kneel": 6, "give-birth": 8, "look-hands": 1}   # rows the face moves down, per pose (people._lower)
SHIFT_X = {"give-birth": 1}                                  # columns it moves right (people._lower stamps at x=1)


def diff(a, b):
    return {(x, y) for y, (ra, rb) in enumerate(zip(a, b)) for x, (ca, cb) in enumerate(zip(ra, rb)) if ca != cb}


class Cells(unittest.TestCase):
    def test_every_cell_has_its_size_and_known_colours(self):
        for key, c in P.CHARACTERS.items():
            for size in P.sizes_of(key):
                w, h = SIZES[size]
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
        self.assertEqual(P.poses_of("patient"), ["lie", "lie-turn", "lie-side", "sick"])

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
        self.assertEqual(reg["bed_poses"], P.BED_POSES)
        self.assertEqual(reg["hands_poses"], P.HANDS_POSES)
        self.assertEqual({k: (v["poses"], v["bust"], v["sizes"]) for k, v in reg["characters"].items()},
                         {k: (v["poses"], v["bust"], P.sizes_of(k)) for k, v in P.CHARACTERS.items()})


def lowest(rows):
    return max(y for y, r in enumerate(rows) if set(r) != {"."})


def top(rows):
    return min(y for y, r in enumerate(rows) if set(r) != {"."})


FIGURE_CAST = [k for k, c in P.CHARACTERS.items() if c["poses"] is P.POSES]
NEW_FIGURE = ["kneel", "give-birth", "look-hands"]


class NewPoses(unittest.TestCase):
    def test_new_figure_poses_belong_to_every_figure_character(self):
        self.assertTrue(set(NEW_FIGURE) <= set(P.POSES))
        for key in FIGURE_CAST:
            for pose in NEW_FIGURE:
                self.assertIn(pose, P.poses_of(key))
                for x in P.EXPRESSIONS:
                    rows = P.cell(key, pose, x)
                    self.assertEqual((len(rows[0]), len(rows)), (P.FIG_W, P.FIG_H))
                    self.assertTrue(set("".join(rows)) - {"."}, (key, pose))

    def test_figure_poses_keep_their_feet_on_the_ground_line(self):
        for key in FIGURE_CAST:
            ground = lowest(P.cell(key, "stand"))
            for pose in NEW_FIGURE:
                self.assertEqual(lowest(P.cell(key, pose)), ground, (key, pose))

    def test_kneeling_and_giving_birth_are_lower_than_standing(self):
        for key in FIGURE_CAST:
            for pose in ("kneel", "give-birth"):
                self.assertGreater(top(P.cell(key, pose)), top(P.cell(key, "stand")) + 3, (key, pose))

    def test_faces_work_in_the_new_poses(self):
        for key in FIGURE_CAST:
            for pose in NEW_FIGURE:
                base = P.cell(key, pose)
                self.assertTrue(diff(base, P.cell(key, pose, mouth="open")), (key, pose))
                self.assertTrue(diff(base, P.cell(key, pose, eyes="blink")), (key, pose))
                self.assertNotEqual(base, P.cell(key, pose, "angry"))
                # tools/pixel/people.py `_lower` moves the whole standing body, face included, so the
                # mouth moves with the head: 6 rows down for kneel, 8 down and 1 right for give-birth,
                # 1 down for look-hands (its face is drawn one row lower and gets no extra wide row)
                dx, dy = SHIFT_X.get(pose, 0), SHIFT_Y.get(pose, 0)
                for x, y in diff(base, P.cell(key, pose, mouth="wide")):
                    self.assertTrue(6 + dx <= x <= 9 + dx and 8 + dy <= y <= 17 + dy, (key, pose, x, y))

    def test_bed_poses(self):
        for key in ("patient", "kolletschka"):
            self.assertIn("bed", P.sizes_of(key))
            self.assertEqual(P.poses_of(key, "bed"), P.BED_POSES)
            cells = {p: P.cell(key, p, size="bed") for p in P.BED_POSES}
            self.assertEqual(len({tuple(v) for v in cells.values()}), len(P.BED_POSES))
            for p in ("lie-side", "sick"):
                self.assertEqual((len(cells[p][0]), len(cells[p])), (P.BED_W, P.BED_H))
        self.assertEqual(P.sizes_of("kolletschka"), ["figure", "bed"])
        self.assertEqual(P.sizes_of("semmelweis"), ["figure", "bust", "hands"])
        self.assertEqual(P.sizes_of("patient"), ["bed"])
        self.assertEqual(P.sizes_of("townsman"), ["figure"])

    def test_sick_is_grey_green_with_sweat_and_heavy_lids(self):
        rows = P.cell("kolletschka", "sick", size="bed")
        flat = "".join(rows)
        self.assertIn("5", flat)
        self.assertIn("%", flat)
        self.assertNotIn("%", "".join(P.cell("kolletschka", "lie-turn", size="bed")))
        self.assertNotEqual(rows, P.cell("kolletschka", "sick", eyes="narrow", size="bed"))

    def test_hands_size(self):
        for key in ("semmelweis", "doctor", "student"):
            self.assertEqual(P.poses_of(key, "hands"), ["open", "reach", "hold"])
            for pose in P.HANDS_POSES:
                rows = P.cell(key, pose, size="hands")
                self.assertEqual((len(rows[0]), len(rows)), (P.HANDS_W, P.HANDS_H))
                self.assertTrue(set("".join(rows)) - {"."}, (key, pose))
                self.assertIn(P.CHARACTERS[key]["coat_c"], "".join(rows))
                self.assertEqual(rows, P.cell(key, pose, "angry", "wide", "blink", "hands"))
            self.assertEqual(len({tuple(P.cell(key, p, size="hands")) for p in P.HANDS_POSES}), 3)
        self.assertIn("q", "".join(P.cell("doctor", "hold", size="hands")))
        self.assertNotEqual(P.cell("doctor", "hold", size="hands"), P.cell("student", "hold", size="hands"))

    def test_hands_atlas_layout_is_one_cell_per_pose(self):
        lay = P.atlas_layout("semmelweis", "hands")
        self.assertEqual((lay["cols"], lay["rows"], lay["w"], lay["h"]), (1, 3, P.HANDS_W + 2, P.HANDS_H + 2))
        self.assertEqual(set(lay["col"].values()), {0})
        self.assertEqual(sorted(set(lay["row"].values())), [0, 1, 2])
        for m in P.MOUTHS:
            for e in P.EYES:
                self.assertIn((m, e), lay["col"])
        for p in P.HANDS_POSES:
            for x in P.EXPRESSIONS:
                self.assertIn((p, x), lay["row"])

    def test_output_is_deterministic(self):
        for key, size, pose in (("mother", "figure", "give-birth"), ("patient", "bed", "sick"), ("doctor", "hands", "hold")):
            self.assertEqual(P.cell(key, pose, size=size), P.cell(key, pose, size=size))


if __name__ == "__main__":
    unittest.main()
