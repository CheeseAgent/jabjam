"""Regression checks for authored and generated workout timelines."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "video"))
from export import calibrated_notes, config, prepare
from choreography import MIN_GAP, arrange, pace_notes
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
            from choreography import PADWORK_COMBOS
            templates = {t[0]: t[2] for group in PADWORK_COMBOS.values() for t in group}
            self.assertEqual(kinds, list(templates[group[0]["combo_id"]]))
        for a, b in zip(result, result[1:]):
            self.assertGreaterEqual(b["time"] - a["time"] + 1e-8,
                 __import__("choreography").required_gap(
                     MOVEMENTS[a["action"]], MOVEMENTS[b["action"]], course))
        self.assertEqual(result, arrange(seed, course, True, chart))

    def test_combos_use_the_supplied_beat_grid(self):
        beats = [round(i * .5 + (.19 if i < 32 else .25), 3) for i in range(120)]
        chart = {"bpm": 120, "duration": 60, "beats": beats, "sections": [{"intensity": .9}] * 15}
        seed = [{"time": 4 + i * .5, "action": "left_jab"} for i in range(64)]
        notes = arrange(seed, dict(self.course, min_gap=.45, movement_set="padwork"), True, chart)
        self.assertGreater(notes[-1]["time"], 50)
        self.assertTrue(all(note["time"] in beats for note in notes))
        for offset in (-200, 150):
            shifted = calibrated_notes(notes, offset, 60)
            self.assertEqual([round(n["time"] - m["time"], 3) for n, m in zip(shifted, notes)],
                             [offset / 1000] * len(notes))

    def test_calibration_drops_only_whole_boundary_combos(self):
        notes = [{"time": t, "combo_no": group} for t, group in
                 [(3.05, 1), (3.6, 1), (8, 2), (8.5, 2), (19, 3), (19.55, 3)]]
        notes.append({"time": 19.59})
        self.assertEqual([n.get("combo_no") for n in calibrated_notes(notes, -200, 20)], [2, 2, 3, 3, None])
        self.assertEqual([n["combo_no"] for n in calibrated_notes(notes, 200, 20)], [1, 1, 2, 2])

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

    def test_saved_padwork_respects_recovery_after_millisecond_rounding(self):
        bpm = 130
        period = 60 / bpm
        chart = {"bpm": bpm, "duration": 83, "sections": [{"intensity": .95}] * 21}
        seed = [{"time": 3 + i * period, "action": "left_jab"} for i in range(90)]
        course = dict(self.course, min_gap=period - .00002, movement_set="padwork")
        notes = arrange(seed, course, True, chart)
        self.assertTrue(notes)
        self.assertEqual(notes, arrange(notes, course, False))

    def test_runtime_overrides_cannot_lower_the_floor(self):
        path = ROOT / "courses/neon-round.json"
        course, *_ = config(path, "Demo", "easy", .3)
        self.assertEqual((course["song_title"], course["min_gap"]), ("Demo", 1.1))
        course, *_ = config(path, None, "normal", 1.6)
        notes = [{"time": 3, "action": "left_jab"}, {"time": 4.5, "action": "right_jab"}]
        with self.assertRaisesRegex(ValueError, "1.6s"):
            pace_notes(notes, course, False)


class CourseCLI(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)

    def cli(self, *args, no_tools=False):
        # -E -S skips site-packages and PYTHONPATH, even on a machine with Pillow installed.
        env = dict(os.environ)
        if no_tools:
            env["PATH"] = ""
        return subprocess.run([sys.executable, "-E", "-S", ROOT / "video/export.py", *args],
                              cwd=self.work, env=env, capture_output=True, text=True, timeout=60)

    def test_check_uses_only_python_and_reports_bad_spacing(self):
        for name in ("eight-moves", "neon-round"):
            result = self.cli(ROOT / f"courses/{name}.json", "--check", no_tools=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        course = {"version": 1, "course": {"music": "builtin:demo"},
                  "actions": [{"time": 4, "action": "step_left"}, {"time": 5, "action": "step_right"}]}
        source = self.work / "crowded.json"
        source.write_text(json.dumps(course))
        result = self.cli(source, "--check", no_tools=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("1.5", result.stderr)

    def test_cli_requires_one_output_mode(self):
        source = ROOT / "courses/four-punches.json"
        for args in ((), ("output.mp4", "--check"), ("--check", "--write-course", "out.json"),
                     ("output.mp4", "--write-course", "out.json")):
            with self.subTest(args=args):
                result = self.cli(source, *args, no_tools=True)
                self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(list(self.work.iterdir()), [])

    @unittest.skipUnless(shutil.which("ffprobe"), "writing a course probes its audio with ffprobe")
    def test_write_manual_course_relocates_music_and_preserves_edits(self):
        source = ROOT / "courses/four-punches.json"
        original = json.loads(source.read_text())
        output = self.work / "drafts" / "round.json"
        result = self.cli(source, "--write-course", output, "--song-title", "练习",
                          "--difficulty", "easy", "--min-gap", "1.4")
        self.assertEqual(result.returncode, 0, result.stderr)
        draft = json.loads(output.read_text())
        course = draft["course"]
        self.assertEqual(draft["actions"], original["actions"])
        self.assertEqual(draft["picture"], original["picture"])
        self.assertEqual((course["song_title"], course["difficulty"], course["min_gap"]), ("练习", "easy", 1.4))
        self.assertFalse(Path(course["music"]).is_absolute())
        self.assertEqual((output.parent / course["music"]).resolve(), (source.parent / original["course"]["music"]).resolve())
        draft["actions"][0]["action"] = "left_uppercut"
        output.write_text(json.dumps(draft))
        edited = self.work / "edited.json"
        result = self.cli(output, "--write-course", edited)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(edited.read_text())["actions"], draft["actions"])

        # A timeline past the end of the song must leave the previous export intact.
        previous = edited.read_bytes()
        draft["actions"][-1]["time"] = 599
        output.write_text(json.dumps(draft))
        result = self.cli(output, "--write-course", edited)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(edited.read_bytes(), previous)
        result = self.cli(edited, "--write-course", edited)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(edited.read_bytes(), previous)

    @unittest.skipUnless(shutil.which("godot") and shutil.which("ffprobe"), "automatic charts need Godot and ffprobe")
    def test_write_auto_captures_render_timeline(self):
        source = ROOT / "courses/neon-round.json"
        course, music, actions, _ = config(source, beat_offset_ms=95)
        _, _, expected, _, _ = prepare(course, music, actions, self.work)
        output = self.work / "round.json"
        output.write_text("{}")
        result = self.cli(source, "--write-course", output, "--beat-offset-ms=95", "--scene", "classic")
        self.assertEqual(result.returncode, 0, result.stderr)
        draft = json.loads(output.read_text())
        self.assertEqual(draft["actions"], expected)
        self.assertTrue(any(n.get("combo_step") == 2 for n in expected))
        self.assertEqual(draft["picture"]["scene"], "classic")
        self.assertEqual(draft["course"]["beat_offset_ms"], 95)
        self.assertEqual(draft["course"]["music"], "builtin:demo")
        result = self.cli(output, "--check", no_tools=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
