"""Rigid cutout renderer. Pivots are texture pixels; offsets are unscaled stage pixels."""
from bisect import bisect_right
import json
import math
from pathlib import Path

from PIL import Image

from movements import MOVEMENTS


def load_json(path, schema, versions=(1,)):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != schema or data.get("version") not in versions:
        raise ValueError(f"Unsupported {schema} format/version at {path}")
    return data


def opposite(channel):
    for side, other in (("_left", "_right"), ("_right", "_left")):
        if channel.endswith(side):
            return channel[:-len(side)] + other
    return channel


def turn_surface(texture, radians, depth):
    """Warp the chest/hips/face artwork around a curved front, using narrow UV strips."""
    if abs(radians) < 1e-6:
        return texture
    width,height = texture.size
    c, a = math.cos(radians), depth*math.sin(radians)
    def source_x(x):
        q = 2*x/width - 1
        # Linear extrapolation into transparent padding outside the turned silhouette.
        if q < -c:
            u = -1 + (q+c)/(c+2*a)
        elif q > c:
            u = 1 + (q-c)/(c-2*a)
        else:
            u = 2*(q-a)/(c + math.sqrt(max(0., c*c-4*a*(q-a))))
        return (u+1)*width/2
    mesh = []
    for left in range(0,width,8):
        right = min(left+8,width)
        x0,x1 = source_x(left),source_x(right)
        mesh.append(((left,0,right,height), (x0,0,x0,height,x1,height,x1,0)))
    return texture.transform(texture.size,Image.Transform.MESH,mesh,Image.Resampling.BICUBIC)


class CutoutRig:
    def __init__(self, directory):
        directory = Path(directory)
        rig = load_json(directory / "rig.json", "jabjam.cutout")
        motion = load_json(directory / "motions.json", "jabjam.rig-motion", (1, 2))
        self.size = tuple(rig["canvas"])
        self.bones = rig["bones"]
        self.stride = motion.get("stride_px", 0)
        self.depth_stride = motion.get("depth_stride_px", 0)
        self.stance_geometry = motion.get("stance", {})
        self.turns = motion.get("turns", {})
        self.shoulder = rig.get("shoulder_projection", {})
        self.poses = motion["poses"]
        self.motions = motion["motions"]
        self.images = {}
        ink = [dict(b, texture=b["underlay"], z=1) for b in self.bones if "underlay" in b]
        fronts = [dict(b, texture=b["front"]["texture"], panel=True, z=b["z"]+1)
                  for b in self.bones if "front" in b]
        self.order = sorted(ink + self.bones + fronts, key=lambda b: b["z"])
        parents = {None}
        for bone in self.bones:
            if bone["parent"] not in parents or bone["id"] in parents:
                raise ValueError(f"Bones must have unique IDs in parent-first order: {bone['id']}")
            parents.add(bone["id"])
            textures = {bone["texture"], *bone.get("variants", {}).values()}
            if "underlay" in bone:
                textures.add(bone["underlay"])
            if "front" in bone:
                textures.add(bone["front"]["texture"])
            for name in textures:
                if Path(name).name != name or not name.endswith(".png"):
                    raise ValueError(f"Expected a local rig PNG: {name}")
                if name not in self.images:
                    with Image.open(directory / name) as im:
                        if im.mode != "RGBA":
                            raise ValueError(f"Rig PNG requires an alpha channel: {name}")
                        self.images[name] = im.copy()

    def _sample(self, pose):
        movement = MOVEMENTS[pose.action] if pose.action else None
        kind = movement.kind if movement else pose.state
        mirror = (movement is not None and
                  (movement.side > 0 or (kind in ("advance", "retreat") and pose.lead_foot == "right")))
        keys = self.motions[kind][pose.state]
        i = max(1, min(len(keys)-1, bisect_right([k[0] for k in keys], pose.phase)))
        t0, a = keys[i-1]
        t1, b = keys[i]
        u = min(1., max(0., (pose.phase-t0)/(t1-t0)))
        u = u*u*(3-2*u)
        source, target = self.poses[a], self.poses[b]
        turn0, turn1 = self.turns.get(a,(0,0)), self.turns.get(b,(0,0))
        direction = -1 if mirror else 1
        hips, chest = [math.radians(direction*(v+(w-v)*u)) for v,w in zip(turn0,turn1)]
        yaw = {"hips":hips, "chest":chest}
        world, zooms, limb_scales = {}, {}, {}
        for bone in self.bones:
            name = bone["id"]
            key = opposite(name) if mirror else name
            start, end = source.get(key, (0,0,0)), target.get(key, (0,0,0))
            dx, dy, angle = (v+(w-v)*u for v,w in zip(start[:3], end[:3]))
            zoom0 = start[3] if len(start) == 4 else 1.
            zoom1 = end[3] if len(end) == 4 else 1.
            zooms[name] = zoom0 + (zoom1 - zoom0)*u
            x = bone["at"][0] + (-dx if mirror else dx)
            y = bone["at"][1] + dy
            if name in ("thigh_left", "thigh_right"):
                lead = name == "thigh_" + pose.lead_foot
                if lead:
                    y += self.stance_geometry.get("lead_forward_px", 0)
                    x += (-1 if pose.lead_foot == "left" else 1) * self.stance_geometry.get("lead_spread_px", 0)
                else:
                    y -= self.stance_geometry.get("rear_back_px", 0)
                    x += (1 if pose.lead_foot == "left" else -1) * self.stance_geometry.get("rear_spread_px", 0)
            if name in ("foot_left", "foot_right"):
                zooms[name] *= 1.05 if name == "foot_" + pose.lead_foot else .98
            angle = bone.get("angle", 0) + (-angle if mirror else angle)
            parent_scale = limb_scales.get(bone["parent"],1.)
            limb_scales[name] = parent_scale
            if "shoulder_side" in bone:
                near = -bone["shoulder_side"] * math.sin(chest)
                limb_scales[name] = 1 + near*self.shoulder["depth_scale"]
                x *= math.cos(chest)*limb_scales[name]
                y += near*self.shoulder["drop_px"]
            if bone["parent"]:
                x, y = x*parent_scale, y*parent_scale
                px, py, pa = world[bone["parent"]]
                c, s = math.cos(pa), math.sin(pa)
                x, y = px+c*x-s*y, py+s*x+c*y
                angle += math.degrees(pa)
            else:
                # At the edge the framing follows the hips during another outward step.
                if self.stride and kind == "step" and pose.stance == movement.side:
                    x = bone["at"][0]
                x += pose.stance * self.stride
                if kind in ("advance", "retreat") and pose.depth == (1 if kind == "advance" else -1):
                    y = bone["at"][1]
                y += pose.depth * self.depth_stride
            world[name] = (x, y, math.radians(angle))
        return world, zooms, yaw, limb_scales

    def transforms(self, pose):
        return self._sample(pose)[0]

    def layers(self, pose):
        """Yield transformed cutouts in paint order for compositing and occlusion review."""
        world, zooms, yaw, limb_scales = self._sample(pose)
        expression = "open"
        if pose.focused:
            expression = "focus"
        elif pose.state == "celebrate" and .10 <= pose.phase <= .90:
            expression = "happy"
        elif pose.focused is None and pose.action and MOVEMENTS[pose.action].kind != "step":
            if (pose.state == "strike" or (pose.state == "prepare" and pose.phase >= .35)
                    or (pose.state == "recover" and pose.phase < .5)):
                expression = "focus"
        for bone in self.order:
            name = bone.get("variants", {}).get(expression, bone["texture"])
            texture = self.images[name]
            if "surface" in bone:
                surface = bone["surface"]
                texture = turn_surface(texture,yaw[surface["turn"]]*surface["amount"],surface["depth"])
            x, y, angle = world[bone["id"]]
            zoom = zooms[bone["id"]]
            px, py = bone["pivot"]
            if "front" in bone:
                front = bone["front"]
                depth = min(1., max(0., (zoom-1)/(front["zoom"]-1)))
                if bone.get("panel"):
                    if depth == 0:
                        continue
                    # Keep the knuckle-to-wrist distance linear in screen space as it grows.
                    weight = 1-(1-depth)/zoom
                    px += (front["pivot"][0]-px)*weight
                    py += (front["pivot"][1]-py)*weight
                elif depth > 0:
                    zoom = 1. + (front["cuff_scale"]-1.)*depth
            scale = bone["scale"] * zoom * limb_scales[bone["id"]]
            c, s = math.cos(angle), math.sin(angle)
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
            yield bone["id"], sprite, (x0,y0)

    def frame(self, pose):
        result = Image.new("RGBA", self.size)
        for _, sprite, position in self.layers(pose):
            result.alpha_composite(sprite, position)
        return result
