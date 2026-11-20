"""Rigid cutout renderer. Pivots are texture pixels; offsets are unscaled stage pixels."""
from bisect import bisect_right
import json
import math
from pathlib import Path

from PIL import Image

from movements import MOVEMENTS


def load_json(path, schema):
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data.get("format"), data.get("version")) != (schema, 1):
        raise ValueError(f"Expected {schema} v1 at {path}")
    return data


def opposite(channel):
    for side, other in (("_left", "_right"), ("_right", "_left")):
        if channel.endswith(side):
            return channel[:-len(side)] + other
    return channel


class CutoutRig:
    def __init__(self, directory):
        directory = Path(directory)
        rig = load_json(directory / "rig.json", "jabjam.cutout")
        motion = load_json(directory / "motions.json", "jabjam.rig-motion")
        self.size = tuple(rig["canvas"])
        self.bones = rig["bones"]
        self.poses = motion["poses"]
        self.motions = motion["motions"]
        self.images = {}
        ink = [dict(b, texture=b["underlay"], z=1) for b in self.bones if "underlay" in b]
        self.order = sorted(ink + self.bones, key=lambda b: b["z"])
        parents = {None}
        for bone in self.bones:
            if bone["parent"] not in parents or bone["id"] in parents:
                raise ValueError(f"Bones must have unique IDs in parent-first order: {bone['id']}")
            parents.add(bone["id"])
            for name in {bone["texture"], bone.get("underlay", bone["texture"]), *bone.get("variants", {}).values()}:
                if Path(name).name != name or not name.endswith(".png"):
                    raise ValueError(f"Expected a local rig PNG: {name}")
                if name not in self.images:
                    with Image.open(directory / name) as im:
                        if im.mode != "RGBA":
                            raise ValueError(f"Rig PNG requires an alpha channel: {name}")
                        self.images[name] = im.copy()

    def transforms(self, pose):
        movement = MOVEMENTS[pose.action] if pose.action else None
        kind = movement.kind if movement else pose.state
        mirror = movement is not None and movement.side > 0
        keys = self.motions[kind][pose.state]
        i = max(1, min(len(keys)-1, bisect_right([k[0] for k in keys], pose.phase)))
        t0, a = keys[i-1]
        t1, b = keys[i]
        u = min(1., max(0., (pose.phase-t0)/(t1-t0)))
        u = u*u*(3-2*u)
        source, target = self.poses[a], self.poses[b]
        world = {}
        for bone in self.bones:
            name = bone["id"]
            key = opposite(name) if mirror else name
            start, end = source.get(key, (0,0,0)), target.get(key, (0,0,0))
            dx, dy, angle = (v+(w-v)*u for v,w in zip(start, end))
            x = bone["at"][0] + (-dx if mirror else dx)
            y = bone["at"][1] + dy
            angle = bone.get("angle", 0) + (-angle if mirror else angle)
            if bone["parent"]:
                px, py, pa = world[bone["parent"]]
                c, s = math.cos(pa), math.sin(pa)
                x, y = px+c*x-s*y, py+s*x+c*y
                angle += math.degrees(pa)
            world[name] = (x, y, math.radians(angle))
        return world

    def frame(self, pose):
        world = self.transforms(pose)
        result = Image.new("RGBA", self.size)
        expression = "open"
        if pose.state == "celebrate" and .10 <= pose.phase <= .90:
            expression = "happy"
        elif pose.action and pose.state == "strike" and MOVEMENTS[pose.action].kind != "step":
            expression = "focus"
        for bone in self.order:
            name = bone.get("variants", {}).get(expression, bone["texture"])
            texture = self.images[name]
            x, y, angle = world[bone["id"]]
            scale = bone["scale"]
            c, s = math.cos(angle), math.sin(angle)
            px, py = bone["pivot"]
            # Transform only the sprite's bounding rectangle, not 20 full canvases.
            corners = [(x+scale*(c*(u-px)-s*(v-py)), y+scale*(s*(u-px)+c*(v-py)))
                       for u in (0, texture.width) for v in (0, texture.height)]
            x0 = math.floor(min(p[0] for p in corners))
            y0 = math.floor(min(p[1] for p in corners))
            width = math.ceil(max(p[0] for p in corners))-x0
            height = math.ceil(max(p[1] for p in corners))-y0
            affine = (c/scale, s/scale, px+(c*(x0-x)+s*(y0-y))/scale,
                      -s/scale, c/scale, py+(-s*(x0-x)+c*(y0-y))/scale)
            sprite = texture.transform((width,height), Image.Transform.AFFINE, affine,
                                       Image.Resampling.BICUBIC)
            result.alpha_composite(sprite, (x0,y0))
        return result
