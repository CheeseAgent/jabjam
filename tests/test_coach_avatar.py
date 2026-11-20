"""Contract regression for the independently replaceable full-body coach."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "video"))

from coach_timeline import CoachTimeline, validate_coach_config
from course import config
from PIL import Image
from coach_avatar import CoachLayer, SpriteCoach


NOTES = [
    {"time": 4.0, "action": "left_jab"},
    {"time": 4.5, "action": "right_hook"},
    {"time": 6.0, "action": "step_left"},
]


class CoachContractTests(unittest.TestCase):
    def test_exact_beat_and_seek_are_deterministic(self):
        timeline = CoachTimeline(NOTES)
        self.assertEqual(timeline.at(3.0).state, "idle")
        self.assertEqual(timeline.at(3.8).state, "prepare")
        self.assertEqual(timeline.at(4.0).state, "strike")
        self.assertEqual(timeline.at(4.0).action, "left_jab")
        self.assertEqual(timeline.at(4.2).state, "recover")
        self.assertEqual(timeline.at(4.28).action, "right_hook")
        self.assertEqual(timeline.at(4.5).action, "right_hook")
        self.assertEqual(timeline.at(6.0).action, "step_left")
        self.assertEqual(timeline.at(8.0).state, "idle")
        self.assertEqual(timeline.at(4.05), timeline.at(4.05))
        timeline.at(6.0)
        self.assertEqual(timeline.at(3.8), CoachTimeline(NOTES).at(3.8))

    def test_settings_reject_unmaintainable_configs(self):
        for settings in ({"enabled": 1}, {"renderer": "gif"}, {"scale": 9},
                         {"skin": "../escape"}, {"side": "middle"},
                         {"enabled": True, "unknown": "x"}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                validate_coach_config(settings)
        self.assertFalse(validate_coach_config({})["enabled"])

    def test_course_accepts_opt_in_and_keeps_legacy_default(self):
        base = ROOT / "courses/eight-moves.json"
        self.assertNotIn("coach", config(base)[3])
        original = json.loads(base.read_text())
        original["picture"]["coach"] = {"enabled": True, "renderer": "vector"}
        with tempfile.TemporaryDirectory(dir=ROOT / "courses") as folder:
            path = Path(folder) / "test.json"
            # Temporary courses live one directory below courses/.
            original["course"]["music"] = "../../tests/fixtures/pulse.ogg"
            path.write_text(json.dumps(original), encoding="utf-8")
            settings = config(path)[3]["coach"]
            self.assertTrue(settings["enabled"])

    def test_vector_renders_distinct_full_body_action_frames(self):
        layer = CoachLayer(NOTES, {"enabled": True, "renderer": "vector"})
        before = Image.new("RGB", (1280, 720), "#121c31")
        impact = before.copy()
        layer.draw(before, 3.5)
        layer.draw(impact, 4.0)
        self.assertNotEqual(before.tobytes(), impact.tobytes())
        self.assertNotEqual(before.getpixel((1135, 400)), (18, 28, 49))

    def test_sprite_pack_requires_real_frames(self):
        with self.assertRaisesRegex(ValueError, "Missing coach sprite pack"):
            SpriteCoach("no_such_pack_for_test")


if __name__ == "__main__":
    unittest.main()
