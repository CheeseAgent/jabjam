"""Shared rig contract, screen-side geometry, alpha joins, and Godot/Pillow parity."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "video"))
from coach_avatar import CoachLayer, SpriteCoach
from coach_timeline import CoachPose, CoachTimeline
from movements import MOVEMENTS


class CutoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        course = json.loads((ROOT / "courses/coach-demo.json").read_text())
        cls.notes = course["actions"]
        cls.layer = CoachLayer(cls.notes, course["picture"]["coach"])
        cls.rig = cls.layer.renderer.rig
        cls.guard = CoachPose("idle", None, 0)

    def test_source_and_formats(self):
        folder = ROOT / "assets/coaches/milktea/rig"
        data = json.loads((folder/"rig.json").read_text())
        textures = set(self.rig.images) | set(data["alternate_textures"])
        self.assertEqual({p.name for p in folder.glob("*.png")}, textures)
        for name in textures:
            with self.subTest(name=name), Image.open(folder / name) as im:
                self.assertEqual(im.mode, "RGBA")
                self.assertEqual(im.getchannel("A").getextrema()[0], 0)
                self.assertGreater(im.getchannel("A").getextrema()[1], 245)
        with tempfile.TemporaryDirectory() as tmp, patch("coach_avatar.ASSETS", Path(tmp)):
            skin = Path(tmp)/"legacy"
            skin.mkdir()
            (skin/"manifest.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "clips"):
                SpriteCoach("legacy")
            Image.new("RGBA", (8,8), "coral").save(skin/"frame.png")
            (skin/"manifest.json").write_text(json.dumps({"version":1,"clips":{"idle":["frame.png"]}}))
            canvas = Image.new("RGB", (1280,720))
            SpriteCoach("legacy").draw(canvas, self.guard, 0, "right", 1)
            self.assertIsNotNone(canvas.getbbox())

    def test_joint_overlap_and_connected_silhouettes(self):
        for b in self.rig.bones:
            if not b["id"].startswith(("lower_arm", "glove", "shin", "foot")):
                continue
            parent = next(p for p in self.rig.bones if p["id"] == b["parent"])
            x = round(parent["pivot"][0]+b["at"][0]/parent["scale"])
            y = round(parent["pivot"][1]+b["at"][1]/parent["scale"])
            for tex, pos in [(b["texture"], tuple(b["pivot"])),(parent["texture"],(x,y))]:
                with self.subTest(joint=b["id"], texture=tex):
                    self.assertGreater(self.rig.images[tex].getpixel(pos)[3], 230)
        poses = [self.guard, CoachPose("celebrate",None,.5)]
        for action in MOVEMENTS:
            poses += [CoachPose("prepare",action,.45),CoachPose("strike",action,0),
                      CoachPose("recover",action,.55)]
        for pose in poses:
            im = self.rig.frame(pose)
            solid = im.getchannel("A").point(lambda a: 255 if a >= 120 else 0)
            x0,y0,x1,y1 = solid.getbbox()
            self.assertTrue(0 < x0 < x1 < im.width and 0 < y0 < y1 < im.height, pose)
            ImageDraw.floodfill(solid, (240,310), 0)
            self.assertLess(solid.histogram()[255], 12, pose)

    def test_screen_hands_and_feet(self):
        neutral = self.rig.transforms(self.guard)
        for kind in ("jab", "hook", "uppercut"):
            impacts = {}
            for side, sign in (("left",-1),("right",1)):
                other = "right" if side == "left" else "left"
                pose = self.rig.transforms(CoachPose("strike",side+"_"+kind,0))
                hand = "glove_"+side
                distance = math.dist(pose[hand][:2],neutral[hand][:2])
                passive = "glove_"+other
                self.assertGreater(distance, math.dist(pose[passive][:2],neutral[passive][:2])+15)
                self.assertGreater(sign*(pose[hand][0]-240), 0)
                impacts[side] = pose[hand][:2]
            self.assertAlmostEqual(impacts["left"][0]+impacts["right"][0],480, places=5)
            self.assertAlmostEqual(impacts["left"][1],impacts["right"][1], places=5)
        for side, sign in (("left",-1),("right",1)):
            w = self.rig.transforms(CoachPose("strike","step_"+side,0))
            foot = "foot_"+side
            self.assertGreater(sign*(w[foot][0]-neutral[foot][0]),25)
        xs = [self.rig.transforms(CoachPose("strike","left_"+k,0))["glove_left"][:2]
              for k in ("jab","hook","uppercut")]
        self.assertLess(xs[0][0], xs[1][0]-45)
        self.assertLess(xs[2][1], xs[1][1]-18)

    def test_ceil_frame_and_final_celebration(self):
        timeline = CoachTimeline([dict(time=2.017,action="left_jab")], celebrate=True)
        self.assertEqual(timeline.at(48/24).state,"prepare")
        self.assertEqual(timeline.at(49/24).state,"strike")
        last = self.notes[-1]["time"]
        self.assertEqual(self.layer.timeline.at(last+.5).state,"celebrate")
        self.assertEqual(self.layer.timeline.at(last+2.1).state,"idle")
        self.assertEqual(CoachTimeline(self.notes).at(last+.5).state,"idle")

    def test_godot_matches_existing_song_timeline_and_bones_after_seeking(self):
        notes = [*self.notes, {"time":20.83, "action":"left_jab"}]
        timeline = CoachTimeline(notes, celebrate=True)
        times = [0, .47, 22.14, 23.1]
        for note in notes:
            times.extend(note["time"]+dt for dt in (-.38,-.21,-1/24,0,.08,.13,.31,.48))
        # Deliberately seek backwards across states, beats and the final celebration.
        times = times[::-1]
        with tempfile.TemporaryDirectory() as tmp:
            fixture, output = Path(tmp)/"in.json", Path(tmp)/"out.json"
            fixture.write_text(json.dumps(dict(notes=notes,times=times)))
            env = dict(os.environ)
            for key in ("DATA", "CONFIG", "CACHE"):
                env["XDG_"+key+"_HOME"] = str(Path(tmp)/key.lower())
            run = subprocess.run([os.environ.get("GODOT_BIN","godot"),"--headless","--path",str(ROOT),
                                  "--script","res://tests/sample_coach_rig.gd","--",str(fixture),str(output)],
                                 env=env,capture_output=True,text=True,timeout=25)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertNotIn("ERROR:",run.stderr)
            frames = json.loads(output.read_text())
        self.assertEqual(len(frames),len(times))
        for t, frame in zip(times,frames):
            expected = timeline.at(t)
            state, action, phase = frame["pose"]
            self.assertEqual((state,action or None),(expected.state,expected.action),t)
            self.assertAlmostEqual(phase,expected.phase,places=6)
            for key,(x,y,angle) in self.rig.transforms(expected).items():
                gx,gy,ga = frame["world"][key]
                self.assertLess(math.hypot(x-gx,y-gy),.001,(t,key))
                self.assertAlmostEqual(math.sin((angle-ga)/2),0,places=5)


if __name__ == "__main__":
    unittest.main()
