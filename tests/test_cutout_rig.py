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

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "video"))
from coach_avatar import CoachLayer, SpriteCoach
from coach_rig import turn_surface
from coach_timeline import CoachPose, CoachTimeline, TIMING
from movements import MOVEMENTS


def cutout_masks(rig, pose):
    """Measure the actual transformed pixels, including the frontal glove panel."""
    masks = {}
    for name, image, position in rig.layers(pose):
        if name not in masks:
            masks[name] = Image.new("L",rig.size)
        masks[name].paste(255, position, image.getchannel("A"))
    return {k:m.point(lambda a: 255 if a >= 128 else 0) for k,m in masks.items()}


def center(mask):
    left, top, right, bottom = mask.getbbox()
    return (left+right)/2, (top+bottom)/2


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

    def test_jab_comes_toward_camera_and_hides_the_arm(self):
        neutral = cutout_masks(self.rig,self.guard)
        for side, opposite, outward in [("left","right",-1), ("right","left",1)]:
            action = side+"_jab"
            hand, passive = "glove_"+side, "glove_"+opposite
            pose = CoachPose("strike",action,0)
            masks = cutout_masks(self.rig,pose)
            arm = ImageChops.lighter(masks["upper_arm_"+side], masks["lower_arm_"+side])
            covered = ImageChops.darker(arm,masks[hand]).histogram()[255]
            self.assertGreater(covered/arm.histogram()[255], .95)
            x,y = center(masks[hand])
            guard_x,guard_y = center(neutral[hand])
            shoulder_x = self.rig.transforms(pose)["upper_arm_"+side][0]
            self.assertGreater(outward*(guard_x-x),25)
            self.assertGreater(outward*(x-240),0)
            self.assertLess(abs(x-shoulder_x),16)
            self.assertLess(abs(y-guard_y),14)
            # Perspective peaks on the named side only and retracts back to guard.
            phases = [.45,.7,.82,1.]
            areas = [cutout_masks(self.rig,CoachPose("prepare",action,u))[hand].histogram()[255]
                     for u in phases]
            self.assertEqual(areas,sorted(areas))
            self.assertGreater(areas[-1]/neutral[hand].histogram()[255],2.3)
            passive_ratio = masks[passive].histogram()[255]/neutral[passive].histogram()[255]
            self.assertTrue(.75 < passive_ratio < .93)  # Far shoulder recedes during the turn.
            self.assertEqual(cutout_masks(self.rig,CoachPose("recover",action,1))[hand].getbbox(),
                             neutral[hand].getbbox())

    def test_windups_are_visible_at_playback_speed_and_have_distinct_paths(self):
        neutral = cutout_masks(self.rig,self.guard)
        for side,other,sign in [("left","right",-1),("right","left",1)]:
            for kind in ["hook","uppercut"]:
                action = side+"_"+kind
                timeline = CoachTimeline([{"time":2.,"action":action}],cutout=True)
                hand, guard_hand = "glove_"+side, "glove_"+other
                guard = center(neutral[hand])
                loaded = cutout_masks(self.rig,CoachPose("prepare",action,.5))
                load_x,load_y = center(loaded[hand])
                hit = center(cutout_masks(self.rig,timeline.at(2.))[hand])
                mid = center(cutout_masks(self.rig,CoachPose("prepare",action,.80))[hand])
                self.assertLess(math.dist(center(loaded[guard_hand]),center(neutral[guard_hand])),28)
                self.assertGreater(sign*(hit[0]-240),0)
                if kind == "hook":
                    self.assertGreater(sign*(load_x-guard[0]),30)
                    self.assertGreater(sign*(load_x-hit[0]),95)
                    self.assertGreater(load_y-mid[1],45)
                else:
                    self.assertGreater(load_y-guard[1],50)
                    self.assertGreater(load_y-hit[1],105)
                    self.assertLess(abs(hit[0]-load_x),50)
                    self.assertTrue(hit[1] < mid[1] < load_y)
                # At least three adjacent output frames show the drawn-back pose.
                held = 0
                for frame in range(32,48):
                    p = timeline.at(frame/24)
                    same = self.rig.transforms(p)[hand] == self.rig.transforms(CoachPose("prepare",action,.5))[hand]
                    held = held+1 if same else 0
                    if held >= 3:
                        break
                self.assertGreaterEqual(held,3)

    def test_chest_turn_carries_whale_and_shoulder_while_face_stays_readable(self):
        skin = {b["id"]:b for b in self.rig.bones}
        shirt = self.rig.images[skin["torso"]["texture"]]
        def logo_center(image):
            red,green,_,alpha = image.split()
            teal = ImageChops.subtract(green,red).point(lambda v: 255 if v > 35 else 0)
            solid = alpha.point(lambda v: 255 if v > 210 else 0)
            return center(ImageChops.darker(teal,solid))[0]
        self.assertEqual(skin["head"]["surface"],skin["face"]["surface"])
        for side,far,direction in [("left","right",1),("right","left",-1)]:
            for kind in ["jab","hook","uppercut"]:
                action = side+"_"+kind
                _,_,load,_ = self.rig._sample(CoachPose("prepare",action,.5))
                _,_,hit,scales = self.rig._sample(CoachPose("strike",action,0))
                _,_,rest,_ = self.rig._sample(CoachPose("recover",action,1))
                self.assertLess(direction*load["chest"],-.10)
                self.assertTrue(0 < direction*hit["hips"] < direction*hit["chest"])
                self.assertTrue(25 < math.degrees(direction*hit["chest"]) < 40)
                self.assertLess(abs(math.degrees(hit["chest"])*skin["head"]["surface"]["amount"]),12)
                self.assertGreater(scales["glove_"+side],1.07)
                self.assertLess(scales["glove_"+far],.94)
                if kind != "jab":
                    _,_,drive,_ = self.rig._sample(CoachPose("prepare",action,.79 if kind == "hook" else .81))
                    self.assertGreater(direction*(drive["hips"]-drive["chest"]),.07)
                turned = turn_surface(shirt,hit["chest"],skin["torso"]["surface"]["depth"])
                self.assertGreater(direction*(logo_center(turned)-logo_center(shirt)),18)
                self.assertEqual(rest,{"hips":0.,"chest":0.})

    def test_punch_expression_survives_recovery_and_short_combo_gaps(self):
        notes = [{"time":t,"action":a} for t,a in
                 [(2,"left_hook"),(4,"step_left"),(6,"right_jab"),(7,"left_uppercut")]]
        timeline = CoachTimeline(notes,cutout=True)
        for t in (1.63,2.59,3.99,4.3,5.63,7.59):
            self.assertFalse(timeline.at(t).focused,t)
        for t in (1.65,2.,2.45,2.57,5.65,6.0,6.61,6.99,7.57):
            self.assertTrue(timeline.at(t).focused,t)
        # The arm has returned to guard at both times. Compare the actual face pixels.
        still = timeline.at(2.45)
        self.assertEqual(still.state,"idle")
        def face(p):
            return next(im.tobytes() for name,im,_ in self.rig.layers(p) if name == "face")
        self.assertNotEqual(face(still),face(CoachPose("idle",None,still.phase,0,False)))
        self.assertEqual(face(still),face(timeline.at(2.45)))

    def test_lead_foot_plants_then_trailing_foot_follows_and_stays(self):
        for side, other, sign in [("left","right",-1),("right","left",1)]:
            notes = [{"time":1., "action":"step_"+side}, {"time":3., "action":"step_"+other}]
            timeline = CoachTimeline(notes,cutout=True)
            lead, trail = "foot_"+side, "foot_"+other
            neutral = self.rig.transforms(self.guard)
            guard_lead, guard_trail = neutral[lead][:2],neutral[trail][:2]
            def feet(t):
                w = self.rig.transforms(timeline.at(t))
                return w[lead][:2], w[trail][:2]
            first_air, planted = feet(.85)
            self.assertGreater(guard_lead[1]-first_air[1],12)
            self.assertLess(math.dist(planted,guard_trail),1)
            first, second = feet(1.0)
            self.assertAlmostEqual(sign*(first[0]-guard_lead[0]),self.rig.stride,delta=.3)
            self.assertLess(math.dist(second,guard_trail),1)
            _, second_air = feet(1.35)
            self.assertGreater(guard_trail[1]-second_air[1],14)
            for i in range(40):
                self.assertLess(math.dist(feet(.581+i*.01)[1],guard_trail),1)
                self.assertLess(math.dist(feet(1+i*.015)[0],first),1)
            for t in (1.62,1.9,2.35):
                a,b = feet(t)
                for foot, initial in [(a,guard_lead),(b,guard_trail)]:
                    self.assertAlmostEqual(sign*(foot[0]-initial[0]),self.rig.stride,delta=.3)
                    self.assertAlmostEqual(foot[1],initial[1],delta=.3)
            final = feet(3.62)
            self.assertLess(math.dist(final[0],guard_lead),.3)
            self.assertLess(math.dist(final[1],guard_trail),.3)

    def test_crowded_notes_share_the_gap_without_skipping_the_follow_step(self):
        notes = [{"time":1., "action":"step_left"},{"time":1.33,"action":"left_hook"}]
        timeline = CoachTimeline(notes,cutout=True)
        fit = .33/(TIMING["strike"]+TIMING["cutout"]["step_recover"]+TIMING["cutout"]["prepare"]["hook"])
        boundary = 1+(TIMING["strike"]+TIMING["cutout"]["step_recover"])*fit
        a,b = timeline.at(boundary-.00001),timeline.at(boundary+.00001)
        self.assertEqual((a.state,b.state),("recover","prepare"))
        self.assertGreater(a.phase,.999)
        self.assertLess(b.phase,.001)
        self.assertEqual((a.stance,b.stance),(0,-1))
        prev, nxt = self.rig.transforms(a), self.rig.transforms(b)
        for foot in ["foot_left","foot_right"]:
            self.assertLess(math.dist(prev[foot][:2],nxt[foot][:2]),.05)
        self.assertEqual(timeline.at(1.33).state,"strike")
        # Consecutive steps at the edge remain in view; a reverse step moves inward immediately.
        repeated = CoachTimeline([{"time":t,"action":"step_"+s} for t,s in
                                  [(1,"left"),(2,"left"),(3,"left"),(4,"right")]],cutout=True)
        for t in (2.0,2.3,2.65,3.2,3.65):
            im = self.rig.frame(repeated.at(t))
            l,_,r,_ = im.getbbox()
            self.assertTrue(0 < l < r < im.width)
        self.assertEqual(repeated.at(4.7).stance,0)

    def test_stance_forward_backward_duck_and_foot_order(self):
        notes = [{"time": 2.0, "action": "step_forward"},
                 {"time": 4.0, "action": "step_backward"},
                 {"time": 6.0, "action": "duck"}]
        for lead, rear in (("left", "right"), ("right", "left")):
            timeline = CoachTimeline(notes, cutout=True, lead_foot=lead)
            guard = self.rig.transforms(timeline.at(0.0))
            self.assertGreater(guard["foot_"+lead][1], guard["foot_"+rear][1]+8)
            self.assertEqual(timeline.at(2.7).depth, 1)
            self.assertEqual(timeline.at(4.7).depth, 0)
            self.assertEqual(timeline.at(6.0).action, "duck")
            self.assertEqual(timeline.at(6.0).state, "strike")
            low = self.rig.transforms(timeline.at(6.0))
            self.assertGreater(low["head"][1], guard["head"][1]+35)
            self.assertGreater(low["pelvis"][1], guard["pelvis"][1]+20)
            for foot in ("foot_left", "foot_right"):
                self.assertLess(abs(low[foot][1]-guard[foot][1]), 25)
            self.assertEqual(timeline.at(8.5).state, "idle")
            self.assertEqual(timeline.at(3.0), CoachTimeline(notes, cutout=True, lead_foot=lead).at(3.0))

    def test_ceil_frame_and_final_celebration(self):
        timeline = CoachTimeline([dict(time=2.017,action="left_jab")], celebrate=True)
        self.assertEqual(timeline.at(48/24).state,"prepare")
        self.assertEqual(timeline.at(49/24).state,"strike")
        last = self.notes[-1]["time"]
        self.assertEqual(self.layer.timeline.at(last+.5).state,"recover")
        self.assertEqual(self.layer.timeline.at(last+.7).state,"celebrate")
        self.assertEqual(self.layer.timeline.at(last+2.3).state,"idle")
        self.assertEqual(CoachTimeline(self.notes).at(last+.5).state,"idle")

    def test_godot_matches_existing_song_timeline_and_bones_after_seeking(self):
        notes = [*self.notes, {"time":20.83, "action":"left_jab"}, {"time":21.3,"action":"step_right"},
                 {"time":22.8,"action":"step_right"}, {"time":23.9,"action":"right_hook"}, {"time":25.5,"action":"step_forward"},
                 {"time":27.0,"action":"duck"}, {"time":29.0,"action":"step_backward"}]
        timeline = CoachTimeline(notes, cutout=True)
        times = [0, .47, 22.14, 23.1, 24.8, 26.3]
        for note in notes:
            times.extend(note["time"]+dt for dt in (-.52,-.38,-.35,-.21,-1/24,0,.08,.13,.31,.48,.575,.59))
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
            state, action, phase, stance, focused, depth = frame["pose"]
            self.assertEqual(depth, expected.depth, t)
            self.assertEqual(stance,expected.stance,t)
            self.assertEqual(focused,expected.focused,t)
            expected_face = "focus" if focused else "happy" if state == "celebrate" and .1 <= phase <= .9 else "open"
            self.assertEqual(frame["face"],expected_face,t)
            self.assertEqual((state,action or None),(expected.state,expected.action),t)
            self.assertAlmostEqual(phase,expected.phase,places=6)
            world, zooms, yaw, scales = self.rig._sample(expected)
            for bone in self.rig.bones:
                key = bone["id"]
                if "surface" in bone:
                    spec = bone["surface"]
                    self.assertAlmostEqual(frame["yaw"][key],yaw[spec["turn"]]*spec["amount"],places=5)
                zoom = zooms[key]
                if "front" in bone and zoom > 1:
                    front = bone["front"]
                    depth = min(1.,(zoom-1)/(front["zoom"]-1))
                    weight = 1-(1-depth)/zoom
                    px,py = [(a+(b-a)*weight)*-bone["scale"]*zoom for a,b in zip(bone["pivot"],front["pivot"])]
                    forward = frame["fronts"][key]
                    self.assertLess(math.dist((px,py),forward[:2]),.001)
                    self.assertAlmostEqual(forward[2],bone["scale"]*zoom,places=5)
                    self.assertGreater(forward[3],bone["z"])
                    zoom = 1+(front["cuff_scale"]-1)*depth
                else:
                    self.assertNotIn(key,frame["fronts"])
                self.assertAlmostEqual(frame["zooms"][key],zoom,places=5)
            for key,(x,y,angle) in world.items():
                gx,gy,ga,scale = frame["world"][key]
                self.assertAlmostEqual(scale,scales[key],places=5)
                self.assertLess(math.hypot(x-gx,y-gy),.001,(t,key))
                self.assertAlmostEqual(math.sin((angle-ga)/2),0,places=5)


if __name__ == "__main__":
    unittest.main()
