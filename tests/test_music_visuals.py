"""Optional opening, music-driven graphics and the streamed background in exported courses."""
from contextlib import closing
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "video"))
from arena import Arena
from audio_wave import song_envelope
from background_video import STAGE_SIZE, video_frames
from course import TITLE_STYLES, WAVE_STYLES, check_course, config
from export import export, write_course
from opening_title import TITLE_SECONDS, fitted_lines
from render_video_job import frame, pcm, verify_course


class MusicVisuals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        cls.dir = Path(tmp.name)
        cls.clip = cls.dir / "红 蓝.mp4"
        cls.song = ROOT / "tests/fixtures/pulse.ogg"
        # Portrait, four fps with a yellow top edge that center cropping should remove.
        # The clip's audio intentionally outlasts the picture.
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                        "color=red:size=80x120:rate=4:duration=1,drawbox=w=iw:h=25:c=yellow:t=fill,"
                        "drawbox=w=iw:h=ih:c=blue:t=fill:enable='gte(t,0.5)'",
                        "-f", "lavfi", "-i", "sine=frequency=877:duration=2", "-threads:v", "1",
                        "-c:v", "libx264", "-c:a", "aac", str(cls.clip)], check=True)
        cls.notes = [{"time": 4, "action": "left_jab"}]

    def course_file(self, picture, music=None):
        path = self.dir / "input.json"
        data = {"version": 1, "course": {"music": str(music or self.song), "song_title": "小奶茶 · First round"},
                "actions": self.notes, "picture": picture}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_config_overrides_and_portable_frozen_course(self):
        path = self.course_file({"title_style": "arcade", "wave_style": "orbit", "background_video": self.clip.name})
        frozen = self.dir / "sub" / "round.json"
        write_course(path, frozen, title_style="off", wave_style="bars")
        data = json.loads(frozen.read_text())
        self.assertEqual(data["picture"], {"title_style": "off", "wave_style": "bars",
                                           "background_video": "../" + self.clip.name})
        self.assertEqual(config(frozen)[3]["background_video"], str(self.clip))
        self.assertEqual(data["actions"], self.notes)
        for opts in ({"title_style": "no"}, {"wave_style": "no"}, {"background_video": "missing.mp4"},
                     {"background_video": str(self.song)}):
            with self.subTest(opts=opts), self.assertRaisesRegex(ValueError, "picture"):
                check_course(path, **opts)
        path = self.course_file({"background_video": "old-missing.mp4"})
        self.assertEqual(config(path, background_video="off")[3]["background_video"], "off")
        self.assertEqual(config(path, background_video=str(self.clip))[3]["background_video"], str(self.clip))
        with self.assertRaisesRegex(ValueError, "different from the background"):
            export(path, self.clip, background_video=str(self.clip))

    def test_opening_bounds_seeking_and_immediate_first_hit(self):
        title = "星光 " + "B" * 60 + "拳" * 60
        face, lines = fitted_lines(title, 510, 105)
        self.assertEqual("".join(lines).replace(" ", ""), title.replace(" ", ""))
        self.assertTrue(all(face.getlength(line) <= 510 for line in lines))
        self.assertLessEqual(len(lines) * (face.size + 5), 105)
        notes = [{"time": 0, "action": "left_jab"}]
        base = Arena(title, {}, notes, 8)
        plain = Arena(title, {"title_style":"off", "wave_style":"off", "background_video":"off"}, notes, 8)
        self.assertEqual(base.frame(0).tobytes(), plain.frame(0).tobytes())
        styles = set()
        for style in TITLE_STYLES[1:]:
            arena = Arena(title, {"title_style":style}, notes, 8)
            opening = arena.frame(0)
            self.assertEqual(base.frame(0).crop((260,430,510,580)).tobytes(),
                             opening.crop((260,430,510,580)).tobytes())
            styles.add(opening.crop((230,240,1030,410)).tobytes())
            self.assertEqual(base.frame(TITLE_SECONDS).tobytes(), arena.frame(TITLE_SECONDS).tobytes())
            self.assertEqual(opening.tobytes(), arena.frame(0).tobytes())
        self.assertEqual(len(styles), 3)

    def test_each_wave_follows_source_loudness_and_silence_at_any_song_time(self):
        env = song_envelope(self.song, 24)
        self.assertEqual(max(env[900:1100]), 0)
        self.assertGreater(env[1400], env[400])
        styles = set()
        for style in WAVE_STYLES[1:]:
            arena = Arena("Pulse", {"wave_style":style, "scene":"classic"}, self.notes, 24, envelope=env)
            box = (25,185,440,385)
            silent = arena.frame(9).crop(box)
            self.assertEqual(silent.tobytes(), arena.frame(10.2).crop(box).tobytes())
            loud = arena.frame(14.02).crop(box)
            self.assertIsNotNone(ImageChops.difference(silent, loud).getbbox())
            self.assertIsNotNone(ImageChops.difference(loud, arena.frame(14.23).crop(box)).getbbox())
            self.assertEqual(loud.tobytes(), arena.frame(14.02).crop(box).tobytes())
            styles.add(loud.tobytes())
        self.assertEqual(len(styles), 3)

    def test_clip_uses_video_clock_center_crop_and_loops_at_output_fps(self):
        for fps in (24, 25, 30):
            with self.subTest(fps=fps), closing(video_frames(self.clip, fps)) as frames:
                for i in range(fps + 1):
                    image = next(frames)
                    self.assertEqual(image.size, STAGE_SIZE)
                    red, green, blue = image.getpixel((20, 5))
                    if i in (0, fps):
                        self.assertGreater(red, 235)
                        self.assertLess(max(green, blue), 20)
                    if i == fps-1:
                        self.assertGreater(blue, 235)

    def test_encoded_video_keeps_song_audio_length_and_hit_guides(self):
        song = self.dir / "short.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(self.song), "-t", "8", str(song)], check=True)
        picture = {"size": [640,360], "fps": 24, "title_style":"vinyl", "wave_style":"orbit",
                   "background_video":self.clip.name}
        path = self.course_file(picture, song)
        output = self.dir / "output.mp4"
        export(path, output)
        self.assertAlmostEqual(verify_course(output, json.loads(path.read_text()), song), 8, places=2)
        original = pcm(song, 4, .18)
        encoded = pcm(output, 4, .18)
        correlation = sum(a*b for a,b in zip(original, encoded)) / (
            sum(a*a for a in original) * sum(b*b for b in encoded))**.5
        self.assertGreater(correlation, .95)
        for at, channel in ((3.25, 0), (3.75, 2), (4.25, 0)):
            image = frame(output, at)
            self.assertGreater(image.getpixel((25, 325))[channel], 150)
            self.assertLess(max(image.getpixel((5, 700))), 50)
            self.assertGreater(min(image.getpixel((40, 510))), 75)
        broken = self.dir / "broken.mp4"
        broken.write_bytes(b"broken")
        prior = output.read_bytes()
        with self.assertRaisesRegex(ValueError, "background video"):
            export(path, output, background_video=str(broken))
        self.assertEqual(output.read_bytes(), prior)


if __name__ == "__main__":
    unittest.main()
