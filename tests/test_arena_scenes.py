"""Artwork, course selection and nearest-frame hit timing in the MP4 renderer."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "video"))
from arena import Arena, HIT_Y
from course import ART_HORIZONS, SCENES, config, read_picture


class ArenaScenes(unittest.TestCase):
    course = ROOT / "courses/coach-demo.json"
    notes = json.loads(course.read_text())["actions"]

    def test_all_backgrounds_use_the_supplied_art_without_covering_the_hud(self):
        # Compare an unobstructed patch in the left-hand illustration to its source.
        for scene, horizon in ART_HORIZONS.items():
            with self.subTest(scene=scene):
                _, _, _, picture = config(self.course, scene=scene)
                arena = Arena("Test", picture, self.notes, 24)
                with Image.open(ROOT / "assets" / "arenas" / (scene + ".jpg")) as original:
                    src = original.resize((1280, 555))
                    box = (40, 145, 230, 255)
                    diff = ImageChops.difference(src.crop(box), arena.base.crop((40, 222, 230, 332)))
                    self.assertLess(max(ImageStat.Stat(diff).mean), 8)
                self.assertEqual(arena.position(1, 0)[1], horizon)
                self.assertEqual(arena.position(1, 1)[1], HIT_Y)
                self.assertEqual(arena.base.getpixel((4, 15)), (12, 21, 35))
                self.assertEqual(arena.base.getpixel((4, 700)), (12, 21, 35))

    def test_selected_art_stays_fixed_across_combos_and_seeks(self):
        notes = [dict(note, combo_name="练习", combo_step=i % 2 + 1, combo_total=2) for i, note in enumerate(self.notes)]
        box = (42, 175, 135, 240)
        for scene in ART_HORIZONS:
            with self.subTest(scene=scene):
                arena = Arena("Test", {"scene": scene}, notes, 24)
                expected = arena.base.crop(box).tobytes()
                for at in (0, 8, 12.5, 18, 23.9, 4):
                    self.assertEqual(arena.frame(at).crop(box).tobytes(), expected)

    def test_older_tour_courses_resolve_to_a_single_overridable_scene(self):
        self.assertNotIn("art-tour", SCENES)
        self.assertEqual(read_picture({"scene": "art-tour"}, None)["scene"], "undersea-office")
        self.assertEqual(read_picture({"scene": "art-tour"}, "moon-carrots")["scene"], "moon-carrots")
        arena = Arena("Test", {"scene": "art-tour"}, self.notes, 24)
        arena.frame(23.9)
        self.assertEqual(arena.scene, "undersea-office")

    def test_fractional_hits_coincide_on_the_nearest_coach_and_burst_frame(self):
        notes = [dict(time=t, action="left_jab", combo_name="直直", combo_step=i+1, combo_total=2)
                 for i, t in enumerate((4.01, 5.027))]
        for fps in (24, 25, 30):
            arena = Arena("Test", {"fps": fps, "coach": {"enabled": True, "renderer": "rig"}}, notes, 8)
            for step, (when, note) in enumerate(zip(arena.times, notes), 1):
                self.assertLessEqual(abs(when - note["time"]), .5 / fps)
                self.assertEqual(arena.coach.timeline.at(when - 1/fps).state, "prepare")
                self.assertEqual(arena.coach.timeline.at(when).state, "strike")
                with patch.object(arena, "burst", wraps=arena.burst) as burst, patch("arena.text") as draw:
                    arena.frame(when - 1/fps)
                    burst.assert_not_called()
                    arena.frame(when)
                    self.assertEqual(burst.call_args.args[4], 0)
                    self.assertTrue(any(call.args[2].endswith(f"{step}/2") for call in draw.call_args_list[-6:]))
        self.assertEqual([n["time"] for n in notes], [4.01, 5.027])

    def test_lyric_presets_clear_on_breaks_and_never_touch_the_targets(self):
        lines = [{"time": 1, "text": "星光落进拳套 Let's move"}, {"time": 3, "text": ""},
                 {"time": 5, "text": "句 03"}]
        notes = [dict(time=4, action="left_jab")]
        off = Arena("Test", {}, notes, 12, lyric_lines=lines)
        samples = []
        for style in ("fade", "rise", "pulse"):
            arena = Arena("Test", {"lyrics": style}, notes, 12, lyric_lines=lines)
            frame = arena.frame(1.09)
            box = ImageChops.difference(frame, off.frame(1.09)).getbbox()
            self.assertIsNotNone(box)
            self.assertLessEqual(box[3], 210)
            self.assertGreater(box[0], 200)
            samples.append(frame.tobytes())
            for t in (7, .5, 3.4, 5.4):
                self.assertEqual(arena.frame(t).tobytes(), off.frame(t).tobytes())
            self.assertEqual(arena.frame(1.09).tobytes(), samples[-1])
        self.assertEqual(len(set(samples)), 3)

    def test_streak_styles_sides_reset_and_pre_cue_are_seekable(self):
        notes = [{"time": t, "action": "left_jab", "combo_name": "直直",
                  "combo_step": i % 2 + 1, "combo_total": 2} for i, t in enumerate([4, 4.5, 9, 9.5])]
        off = Arena("Test", {"combo_side": "off"}, notes, 12)
        frames = []
        for style in ("minimal", "arcade", "ring"):
            for side in ("left", "right"):
                arena = Arena("Test", {"combo_side": side, "combo_style": style}, notes, 12)
                self.assertEqual(arena.hud.counts, [1, 2, 1, 2])
                for t in (7, 9, 4):
                    self.assertEqual(arena.frame(t).tobytes(), off.frame(t).tobytes())
                at = arena.frame(4.5)
                box = ImageChops.difference(at, off.frame(4.5)).getbbox()
                self.assertTrue(box[2] < 300 if side == "left" else box[0] > 980)
                frames.append(at.tobytes())
        self.assertEqual(len(set(frames)), 6)
        self.assertEqual(Arena("T", {"coach": {"enabled": True, "side": "left"}}, notes, 12).hud.side, "right")
        with patch("workout_hud.text") as draw:
            off.frame(6)
            self.assertIn("回架", [c.args[2] for c in draw.call_args_list])
            draw.reset_mock()
            off.frame(8.1)
            self.assertIn("下一组  ·  左起  ·  直直", [c.args[2] for c in draw.call_args_list])


if __name__ == "__main__":
    unittest.main()
