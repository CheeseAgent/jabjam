"""Regression checks for authored and generated workout timelines."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "video"))
from export import config
from choreography import arrange, pace_notes, MIN_GAP
from movements import MOVEMENTS


class VideoPacing(unittest.TestCase):
    def setUp(self):
        self.course = {"difficulty": "normal", "min_gap": .7}

    def test_auto_preserves_beats_and_alternation(self):
        notes = [{"time": t, "action": action} for t, action in
                 [(3, "left_hook"), (3.8, "right_jab"), (4.6, "left_jab"), (5.4, "right_jab")]]
        self.assertEqual(pace_notes(notes, self.course, True), [notes[0], notes[3]])

    def test_manual_spacing_and_exact_boundary(self):
        for difficulty, after_hook, basic in [("easy", 1.35, 1.1), ("normal", .90, .45)]:
            self.course.update(difficulty=difficulty, min_gap=basic)
            for first, second, gap in [("left_hook", "right_jab", after_hook),
                                       ("left_jab", "left_jab", after_hook),
                                       ("left_jab", "right_jab", basic)]:
                notes = [{"time": 3, "action": first}, {"time": 3+gap, "action": second}]
                self.assertEqual(pace_notes(notes, self.course, False), notes)
                notes[1]["time"] -= .001
                with self.assertRaisesRegex(ValueError, "needs"):
                    pace_notes(notes, self.course, False)

    def test_step_needs_recovery_on_both_sides_of_beat(self):
        for difficulty, gap in [("easy", 1.75), ("normal", 1.5)]:
            course = dict(self.course, difficulty=difficulty)
            for first, second in [("left_jab", "step_right"), ("step_left", "right_uppercut"),
                                  ("step_left", "step_right")]:
                notes = [{"time": 3.0, "action": first}, {"time": 3.0 + gap, "action": second}]
                self.assertEqual(arrange(notes, course, False), notes)
                notes[1]["time"] -= .01
                with self.assertRaisesRegex(ValueError, "needs"):
                    arrange(notes, course, False)
        notes = [{"time": 3, "action": "left_uppercut"}, {"time": 3.8, "action": "right_jab"}]
        with self.assertRaisesRegex(ValueError, "needs"):
            arrange(notes, self.course, False)

    def test_mixed_round_reuses_beats_and_balances_steps(self):
        pattern = ["left_jab", "right_jab", "left_hook", "right_hook"]
        original = [{"time": 3 + i, "action": pattern[i % 4]} for i in range(48)]
        mixed = dict(self.course, movement_set="mixed")
        result = arrange(original, mixed, True)
        self.assertEqual(result, arrange(original, mixed, True))
        self.assertTrue(all(n["time"] in range(3, 51) for n in result))
        self.assertEqual({n["action"] for n in result}, set(MOVEMENTS))
        steps = [n["action"] for n in result if MOVEMENTS[n["action"]].kind == "step"]
        self.assertEqual(steps, ["step_left", "step_right", "step_right", "step_left"])
        self.assertEqual(result, pace_notes(result, mixed, False))
        self.assertEqual(arrange(original, self.course, True), original)
        self.assertEqual(arrange(original, mixed, False), original)
        easy = [{"time": 3 + 2*i, "action": pattern[i % 2]} for i in range(48)]
        self.assertEqual(arrange(easy, dict(mixed, difficulty="easy"), True), easy)

    def test_normal_accepts_short_punch_bursts(self):
        course = {"difficulty": "normal", "min_gap": MIN_GAP["normal"]}
        notes = [{"time": 4 + i*.5, "action": a} for i,a in enumerate(
            ["left_jab", "right_jab", "left_jab", "right_jab"])]
        self.assertEqual(pace_notes(notes, course, True), notes)
        self.assertEqual(MIN_GAP["normal"], .45)

    def test_padwork_makes_intact_coach_combos(self):
        # First two phrases are medium, subsequent phrases are high.
        chart = {"bpm": 120, "duration": 48, "sections":
                 [{"time": i * 4, "intensity": .3 if i < 2 else .95}
                  for i in range(12)]}
        seed = [{"time": 4 + .5 * i, "action": "left_jab"} for i in range(80)]
        course = {"difficulty": "normal", "min_gap": .45,
                  "movement_set": "padwork"}
        result = arrange(seed, course, True, chart)
        self.assertTrue(result)
        groups = {}
        for note in result:
            groups.setdefault(note["combo_no"], []).append(note)
        self.assertTrue(any(g[0]["combo_name"] == "直直摆" for g in groups.values()))
        self.assertTrue(any(g[0]["combo_name"] == "直直摆勾直" for g in groups.values()))
        for group in groups.values():
            self.assertEqual(len(group), group[0]["combo_total"])
            self.assertEqual([n["combo_step"] for n in group],
                             list(range(1, len(group) + 1)))
            kinds = [MOVEMENTS[n["action"]].kind for n in group]
            if len(group) == 5:
                self.assertEqual(kinds, ["jab", "jab", "hook", "uppercut", "jab"])
            if len(group) == 3:
                self.assertEqual(kinds, ["jab", "jab", "hook"])
        for a, b in zip(result, result[1:]):
            self.assertGreaterEqual(b["time"] - a["time"] + 1e-8,
                 __import__("choreography").required_gap(
                     MOVEMENTS[a["action"]], MOVEMENTS[b["action"]], course))
        self.assertEqual(result, arrange(seed, course, True, chart))

    def test_padwork_mirrors_and_respects_fast_tempos(self):
        from choreography import required_gap
        course = {"difficulty": "normal", "min_gap": .45,
                  "movement_set": "padwork"}
        for bpm in (60, 120, 160, 180):
            chart = {"bpm": bpm, "duration": 120, "sections":
                     [{"time": i * 4, "intensity": .95} for i in range(30)]}
            notes = [{"time": 4 + i * 60 / bpm, "action": "left_jab"}
                     for i in range(80)]
            result = arrange(notes, course, True, chart)
            groups = {}
            for note in result:
                groups.setdefault(note["combo_no"], []).append(note)
            self.assertGreaterEqual(len(groups), 2)
            self.assertTrue(all(len(g) == 5 for g in groups.values()))
            firsts = [g[0]["action"].split("_")[0] for g in groups.values()]
            self.assertTrue(set(firsts) == {"left", "right"})
            for a, b in zip(result, result[1:]):
                self.assertGreaterEqual(b["time"] - a["time"] + 1e-8,
                         required_gap(MOVEMENTS[a["action"]],
                                      MOVEMENTS[b["action"]], course))
            self.assertLess(result[-1]["time"], 120)
        # Hand-authored timelines must remain untouched.
        manual = [{"time": 4, "action": "left_jab"},
                  {"time": 5, "action": "right_hook"}]
        self.assertEqual(arrange(manual, course, False), manual)

    def test_padwork_repertoire_rotates_after_mirrored_repetition(self):
        from choreography import PADWORK_COMBOS, required_gap
        self.assertGreaterEqual(len(PADWORK_COMBOS["steady"]), 4)
        self.assertGreaterEqual(len(PADWORK_COMBOS["peak"]), 4)
        self.assertTrue(any(len(t[2]) == 4 for t in PADWORK_COMBOS["steady"]))
        course = {"difficulty": "normal", "min_gap": .45,
                  "movement_set": "padwork"}
        for intensity, library_name in ((.4, "steady"), (.95, "peak")):
            chart = {"bpm": 120, "duration": 200,
                     "sections": [{"time": i * 4, "intensity": intensity}
                                  for i in range(50)]}
            seed = [{"time": 4 + .5 * i, "action": "left_jab"}
                    for i in range(48)]
            result = arrange(seed, course, True, chart)
            phrases = {}
            for note in result:
                phrases.setdefault(note["combo_no"], []).append(note)
            combos = list(phrases.values())
            # Rehearse every pattern twice, switching the lead hand.
            self.assertGreaterEqual(len(combos), 10)
            used = [p[0]["combo_id"] for p in combos]
            self.assertGreaterEqual(len(set(used)), 4)
            expected_ids = [entry[0] for entry in PADWORK_COMBOS[library_name]]
            self.assertEqual(used[:8], [expected_ids[i // 2] for i in range(8)])
            for i in range(0, 8, 2):
                self.assertEqual([MOVEMENTS[n["action"]].kind for n in combos[i]],
                                 [MOVEMENTS[n["action"]].kind for n in combos[i+1]])
                self.assertEqual(combos[i][0]["action"].split("_")[0], "left")
                self.assertEqual(combos[i+1][0]["action"].split("_")[0], "right")
            for phrase in combos:
                self.assertEqual(len(phrase), phrase[0]["combo_total"])
                self.assertTrue(all(n["combo_id"] == phrase[0]["combo_id"]
                                    for n in phrase))
            for previous, current in zip(result, result[1:]):
                self.assertGreaterEqual(
                    current["time"] - previous["time"] + 1e-8,
                    required_gap(MOVEMENTS[previous["action"]],
                                 MOVEMENTS[current["action"]], course))
            self.assertEqual(result, arrange(seed, course, True, chart))

    def test_padwork_respects_higher_recovery_without_broken_combos(self):
        from choreography import required_gap
        chart = {"bpm": 160, "duration": 115,
                 "sections": [{"time": i * 4, "intensity": .8}
                              for i in range(29)]}
        seed = [{"time": 4 + .375 * i, "action": "left_jab"}
                for i in range(48)]
        course = {"difficulty": "normal", "min_gap": 1.25,
                  "movement_set": "padwork"}
        notes = arrange(seed, course, True, chart)
        combos = {}
        for n in notes:
            combos.setdefault(n["combo_no"], []).append(n)
        self.assertTrue(combos)
        self.assertTrue(all(len(group) == group[0]["combo_total"]
                            for group in combos.values()))
        self.assertTrue(all(b["time"] - a["time"] + 1e-8 >=
                            required_gap(MOVEMENTS[a["action"]],
                                         MOVEMENTS[b["action"]], course)
                            for a, b in zip(notes, notes[1:])))

    def test_padwork_config_selected(self):
        path = Path(__file__).resolve().parents[1] / "courses/neon-round.json"
        course, *_ = config(path)
        self.assertEqual(course["movement_set"], "padwork")

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
