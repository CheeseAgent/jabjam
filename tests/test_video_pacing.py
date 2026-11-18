"""Regression checks for authored and generated workout timelines."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "video"))
from export import config, pace_notes


class VideoPacing(unittest.TestCase):
    def setUp(self):
        self.course = {"difficulty": "normal", "min_gap": .7}

    def test_auto_preserves_beats_and_alternation(self):
        notes = [{"time": t, "action": action} for t, action in
                 [(3, "left_hook"), (3.8, "right_jab"), (4.6, "left_jab"), (5.4, "right_jab")]]
        self.assertEqual(pace_notes(notes, self.course, True), [notes[0], notes[3]])

    def test_manual_spacing_and_exact_boundary(self):
        for difficulty, after_hook, basic in [("easy", 1.35, 1.1), ("normal", 1, .7)]:
            self.course.update(difficulty=difficulty, min_gap=basic)
            for first, second, gap in [("left_hook", "right_jab", after_hook),
                                       ("left_jab", "left_jab", after_hook),
                                       ("left_jab", "right_jab", basic)]:
                notes = [{"time": 3, "action": first}, {"time": 3+gap, "action": second}]
                self.assertEqual(pace_notes(notes, self.course, False), notes)
                notes[1]["time"] -= .001
                with self.assertRaisesRegex(ValueError, "needs"):
                    pace_notes(notes, self.course, False)

    def test_runtime_overrides_cannot_lower_the_floor(self):
        path = Path(__file__).resolve().parents[1] / "courses/neon-round.json"
        course, *_ = config(path, "Demo", "easy", .3)
        self.assertEqual((course["song_title"], course["min_gap"]), ("Demo", 1.1))
        course, *_ = config(path, None, "normal", 1.6)
        notes = [{"time": 3, "action": "left_jab"}, {"time": 4.5, "action": "right_jab"}]
        with self.assertRaisesRegex(ValueError, "1.6s"):
            pace_notes(notes, course, False)


if __name__ == "__main__":
    unittest.main()
