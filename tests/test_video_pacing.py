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

    def test_forward_backward_and_duck_are_valid_and_spaced(self):
        from course import read_actions
        for action in ("step_forward", "step_backward", "duck"):
            self.assertEqual(read_actions([{"time": 4, "action": action}])[0]["action"], action)
            self.assertIn(action, MOVEMENTS)
        for sequence in [
            ("step_forward", "duck"),
            ("duck", "step_backward"),
            ("step_forward", "step_backward"),
        ]:
            valid = [{"time": 4, "action": sequence[0]}, {"time": 5.5, "action": sequence[1]}]
            self.assertEqual(arrange(valid, self.course, False), valid)
            invalid = [{"time": 4, "action": sequence[0]}, {"time": 5.49, "action": sequence[1]}]
            with self.assertRaisesRegex(ValueError, "needs"):
                arrange(invalid, self.course, False)

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
        self.assertEqual({n["action"] for n in result},
                         {"left_jab", "right_jab", "left_hook", "right_hook",
                          "left_uppercut", "right_uppercut", "step_left", "step_right"})
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

    def test_lyric_pickups_lead_and_followups_stay_on_calibrated_beats(self):
        beats = [round(i * .5 + (.07 if i < 24 else .12), 3) for i in range(90)]
        chart = {"bpm": 120, "duration": 44, "beats": beats, "sections": [{"intensity": .95}] * 11}
        seed = [{"time": 4, "action": "left_jab"}]
        # The line at 13.74 is too short even for a pair. The later long gap is instrumental.
        starts = [2.9, 3.13, 8.36, 13.74, 14.17, 16.26, 31.33, 43.5]
        for offset in (-170, 0, 215):
            with self.subTest(offset=offset):
                course = dict(self.course, min_gap=.45, movement_set="padwork", lyric_starts=starts,
                              beat_offset_ms=offset, lyric_phrasing="single")
                notes = calibrated_notes(arrange(seed, course, True, chart), offset, chart["duration"])
                leads = [n for n in notes if n["combo_step"] == 1]
                self.assertEqual([n["time"] for n in leads], [3.13, 8.36, 14.17, 16.26, 31.33])
                self.assertEqual([n["action"] for n in leads[:2]], ["left_jab", "right_jab"])
                self.assertEqual([n["combo_total"] for n in leads[:2]], [5, 5])
                self.assertLess(leads[2]["combo_total"], 5)
                grid = {round(t + offset / 1000, 3) for t in beats}
                for lead in leads:
                    group = [n for n in notes if n["combo_no"] == lead["combo_no"]]
                    self.assertEqual([n["combo_step"] for n in group], list(range(1, lead["combo_total"] + 1)))
                    self.assertTrue(all(n["time"] in grid for n in group[1:]))
                    self.assertLessEqual(group[-1]["time"] + .9, starts[lead["combo_no"]] + 1e-9)
                self.assertEqual(arrange(notes, course, False), notes)

    def test_lyric_recovery_survives_fractional_millisecond_calibration(self):
        bpm = 91
        beats = [round(i * 60 / bpm + .07, 3) for i in range(75)]
        chart = {"bpm": bpm, "duration": 50, "beats": beats, "sections": [{"intensity": .95}] * 13}
        course = dict(self.course, min_gap=60 / bpm, movement_set="padwork", beat_offset_ms=249.5,
                      lyric_starts=[3.13, 9.1, 15.6, 21.75, 28.12, 34.63, 45.0])
        notes = arrange([{"time": 4, "action": "left_jab"}], course, True, chart)
        saved = calibrated_notes(notes, 249.5, 50)
        self.assertGreater(len(saved), 10)
        self.assertEqual(arrange(saved, course, False), saved)

    def test_short_lines_can_share_one_complete_round(self):
        beats = [i / 2 for i in range(90)]
        chart = {"bpm": 120, "duration": 45, "beats": beats, "sections": [{"intensity": .95}] * 12}
        seed = [{"time": 4, "action": "left_jab"}]
        starts = [4.1, 6.1, 8.2, 16.3, 24.3, 32.3, 41.3]
        for mode, longest in (("normal", 5), ("hard", 6), ("expert", 8)):
            course = dict(difficulty=mode, min_gap=MIN_GAP[mode], movement_set="padwork", lyric_starts=starts)
            for offset in (-170, 0, 123.5):
                course["beat_offset_ms"] = offset
                notes = calibrated_notes(arrange(seed, course, True, chart), offset, 45)
                self.assertEqual(arrange(notes, course, False), notes)
                leads = [n for n in notes if n["combo_step"] == 1]
                self.assertEqual(max(n["combo_total"] for n in leads), longest)
                self.assertTrue(all(n["time"] in starts for n in leads))
                self.assertEqual(len(notes), sum(n["combo_total"] for n in leads))
                self.assertEqual(leads[0]["time"], 4.1)
                self.assertLessEqual(leads[1]["time"], 8.2)
                single = calibrated_notes(arrange(seed, dict(course, lyric_phrasing="single"), True, chart), offset, 45)
                self.assertGreater(leads[0]["combo_total"], single[0]["combo_total"])

    def test_calibration_drops_only_whole_boundary_combos(self):
        notes = [{"time": t, "combo_no": group} for t, group in
                 [(3.05, 1), (3.6, 1), (8, 2), (8.5, 2), (19, 3), (19.55, 3)]]
        notes.append({"time": 19.59})
        self.assertEqual([n.get("combo_no") for n in calibrated_notes(notes, -200, 20)], [2, 2, 3, 3, None])
        self.assertEqual([n["combo_no"] for n in calibrated_notes(notes, 200, 20)], [1, 1, 2, 2])

    def test_chorus_marks_reserve_mirrored_groups_on_the_song_clock(self):
        from choreography import CHORUS_FINALES
        starts = [8.12, 18.34, 28.17]
        beats = [round(i * .491 + .07, 3) for i in range(90)]
        seed = [{"time": 4.0, "action": "left_jab"}]
        chart = {"bpm": 122, "duration": 44, "beats": beats, "sections": [{"intensity": .95}] * 11}
        for base, finale in CHORUS_FINALES.items():
            for lyric_options in ({}, {"lyric_starts": [4, 7.8, 8.12, 13, 18.34, 23, 28.17, 35, 40]}):
                for offset in (-173.5, 249.5):
                    with self.subTest(base=base, offset=offset, lyrics=bool(lyric_options)):
                        course = dict(self.course, min_gap=.491, movement_set="padwork", chorus_starts=starts,
                                      chorus_combo=base, beat_offset_ms=offset, **lyric_options)
                        saved = calibrated_notes(arrange(seed, course, True, chart), offset, 44)
                        self.assertEqual(arrange(saved, course, False), saved)
                        leads = [n for n in saved if n["combo_step"] == 1 and "chorus_cue" in n]
                        self.assertEqual([n["time"] for n in leads], starts)
                        self.assertEqual([n["combo_id"] for n in leads], [base, base, finale])
                        self.assertEqual([n["chorus_cue"] for n in leads], ["learn", "mirror", "extend"])
                        groups = [[n for n in saved if n["combo_no"] == lead["combo_no"]] for lead in leads]
                        moves = [[MOVEMENTS[n["action"]] for n in group] for group in groups]
                        self.assertEqual([m.kind for m in moves[0]], [m.kind for m in moves[1]])
                        self.assertTrue(all(a.side != b.side for a, b in zip(moves[0], moves[1])))
                        self.assertEqual(moves[0], moves[2][:3])
                        self.assertEqual([len(g) for g in groups], [3, 3, 5])
                        grid = {round(t + offset/1000, 3) for t in beats}
                        self.assertTrue(all(n["time"] in grid for group in groups for n in group[1:]))
                        self.assertTrue(any("chorus_cue" not in n for n in saved))
                        for lead in (n for n in saved if n["combo_step"] == 1):
                            steps = [n["combo_step"] for n in saved if n["combo_no"] == lead["combo_no"]]
                            self.assertEqual(steps, list(range(1, lead["combo_total"] + 1)))

    def test_chorus_finale_falls_back_and_impossible_marks_name_the_time(self):
        beats = [i / 2 for i in range(80)]
        chart = {"beats": beats, "bpm": 120, "duration": 40, "sections": [{"intensity": .7}] * 10}
        seed = [{"time": 4, "action": "left_jab"}]
        course = dict(self.course, min_gap=.45, movement_set="padwork", lyric_phrasing="single",
                      lyric_starts=[4, 12, 21, 23.3, 32])
        for starts, expected in [([4], ["learn"]), ([4, 12], ["learn", "mirror"]),
                                 ([4, 12, 21], ["learn", "mirror", "repeat"]),
                                 ([4, 12, 21, 38], ["learn", "mirror", "repeat", "mirror"])]:
            notes = arrange(seed, dict(course, chorus_starts=starts), True, chart)
            leads = [n for n in notes if "chorus_cue" in n and n["combo_step"] == 1]
            self.assertEqual([n["chorus_cue"] for n in leads], expected)
            self.assertTrue(all(n["combo_total"] == 3 for n in leads))
        for starts, message in [([2.9], "2.9s"), ([4, 5.5], "5.5s"), ([39], "39s"), ([43], "43s")]:
            with self.subTest(starts=starts), self.assertRaisesRegex(ValueError, message):
                arrange(seed, dict(course, chorus_starts=starts), True, chart)

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

    @unittest.skipUnless(shutil.which("godot") and shutil.which("ffprobe"), "automatic charts need Godot and ffprobe")
    def test_chorus_course_freezes_labels_and_honors_difficulty_override(self):
        source = ROOT / "courses/chorus-signature.json"
        self.assertIn("3 chorus marks", self.cli(source, "--check", no_tools=True).stdout)
        self.assertIn("chorus marks inactive", self.cli(source, "--check", "--difficulty", "easy", no_tools=True).stdout)
        frozen = self.work / "frozen.json"
        for level in ("easy", "normal", "hard", "expert"):
            result = self.cli(source, "--write-course", frozen, "--difficulty", level, "--beat-offset-ms=-107")
            self.assertEqual(result.returncode, 0, result.stderr)
            settings, _, actions, _ = config(frozen)
            leads = [n for n in actions if n.get("combo_step") == 1 and "chorus_cue" in n]
            self.assertEqual([n["time"] for n in leads], [] if level == "easy" else [8, 18, 28])
            self.assertEqual(arrange(actions, settings, False), actions)
        data = json.loads(source.read_text())
        for key, value in [("chorus_starts", [12, 8]), ("chorus_starts", [8, 8.00001]),
                           ("chorus_starts", [True]), ("chorus_combo", "unknown")]:
            bad = dict(data, course=dict(data["course"], **{key: value}))
            frozen.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError, key):
                config(frozen)

    def test_lrc_discovery_inline_override_and_other_course_modes(self):
        audio = self.work / "song.ogg"
        shutil.copyfile(ROOT / "tests/fixtures/pulse.ogg", audio)
        source = self.work / "training.json"
        course = {"music": audio.name, "movement_set": "padwork"}
        def save(actions="auto"):
            source.write_text(json.dumps({"version": 1, "course": course, "actions": actions}))
        save()
        self.assertNotIn("lyric_starts", config(source)[0])
        lyrics = audio.with_suffix(".lrc")
        lyrics.write_text("[ar:Coach]\n[00:12.25][00:04.2]Again\n[00:04.20]Translation\n"
                          "[00:05.88]\n[00:08.678]Next\n[00:10.0][Instrumental]\n[offset:+100]\n",
                          encoding="utf-8-sig")
        self.assertEqual(config(source)[0]["lyric_starts"], [4.1, 8.578, 12.15])
        self.assertIn("3 timed lyric lines", self.cli(source, "--check", no_tools=True).stdout)
        lyrics.write_text("words without timing")
        with self.assertRaisesRegex(ValueError, "no timed lyric lines"):
            config(source)
        self.assertNotIn("lyric_starts", config(source, difficulty="easy")[0])
        course["movement_set"] = "mixed"
        save()
        self.assertNotIn("lyric_starts", config(source)[0])
        course["movement_set"] = "padwork"
        save([{"time": 4.1, "action": "left_jab"}])
        self.assertNotIn("lyric_starts", config(source)[0])
        course["lyric_starts"] = [6.3, 10.2]
        save()
        self.assertEqual(config(source)[0]["lyric_starts"], [6.3, 10.2])
        for bad in ([], "4.2", [True], [3.4, 3.4], [4, 3], [-1], [601]):
            with self.subTest(bad=bad):
                course["lyric_starts"] = bad
                save()
                with self.assertRaisesRegex(ValueError, "course.lyric_starts"):
                    config(source)

    @unittest.skipUnless(shutil.which("godot") and shutil.which("ffprobe"), "automatic charts need Godot and ffprobe")
    def test_write_lyric_course_freezes_the_same_pickups(self):
        audio = self.work / "pulse.ogg"
        shutil.copyfile(ROOT / "tests/fixtures/pulse.ogg", audio)
        lyrics = audio.with_suffix(".lrc")
        lyrics.write_text("[00:03.23]One\n[00:10.21]Two\n[00:18.17]Three\n[offset:-100]\n")
        source = self.work / "auto.json"
        source.write_text(json.dumps({"version": 1, "course": {"music": audio.name, "movement_set": "padwork"}}))
        frozen = self.work / "drafts" / "frozen.json"
        run = self.cli(source, "--write-course", frozen, "--beat-offset-ms=120")
        self.assertEqual(run.returncode, 0, run.stderr)
        draft = json.loads(frozen.read_text())
        leads = [n["time"] for n in draft["actions"] if n["combo_step"] == 1]
        self.assertEqual(leads, [3.33, 10.31, 18.27])
        lyrics.unlink()
        again = self.work / "again.json"
        run = self.cli(frozen, "--write-course", again, "--beat-offset-ms=-150")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(again.read_text())["actions"], draft["actions"])

    def test_display_lyrics_are_independent_of_chart_and_freeze_with_the_course(self):
        audio = self.work / "pulse.ogg"
        shutil.copyfile(ROOT / "tests/fixtures/pulse.ogg", audio)
        lrc = audio.with_suffix(".lrc")
        lrc.write_text("[offset:+100]\n[00:04.20][00:12.25]向前一步\n[00:04.20]Translation\n"
                       "[00:08.00]句 02\n[00:10.00][Instrumental]\n")
        path = self.work / "manual.json"
        path.write_text(json.dumps({"version": 1, "course": {"music": audio.name, "difficulty": "expert",
                                    "lyric_starts": [6.2]}, "actions": [{"time": 4, "action": "left_jab"}]}))
        self.assertNotIn("lyric_lines", config(path)[0])
        course, _, _, _ = config(path, lyrics="rise")
        self.assertEqual(course["lyric_starts"], [6.2])
        self.assertEqual(course["lyric_lines"][0], {"time": 4.1, "text": "向前一步"})
        self.assertIn("2 visible lyric lines", self.cli(path, "--check", "--lyrics=rise", no_tools=True).stdout)
        frozen = self.work / "frozen.json"
        result = self.cli(path, "--write-course", frozen, "--lyrics=rise", "--combo-side=right", "--combo-style=ring")
        self.assertEqual(result.returncode, 0, result.stderr)
        lrc.unlink()
        replay, _, actions, picture = config(frozen)
        self.assertEqual(replay["lyric_lines"], course["lyric_lines"])
        self.assertEqual(actions[0]["time"], 4)
        self.assertEqual(picture, {"lyrics": "rise", "combo_side": "right", "combo_style": "ring"})
        self.assertIn("no lyric text", self.cli(path, "--check", "--lyrics=pulse", no_tools=True).stdout)

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
