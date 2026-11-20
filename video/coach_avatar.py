"""Optional full-body coach overlay. Both backends implement draw(canvas, pose, t)."""
from functools import lru_cache
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

from coach_timeline import CoachTimeline, validate_coach_config

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "coaches"
GROUND_Y = 625
BASE_WIDTH = 300
BASE_HEIGHT = 390


def _location(side):
    # Outside the cue hit lanes, with feet above the bottom HUD.
    return 1135 if side == "right" else 145


def _composite(canvas, layer, side, scale):
    height = round(335 * scale)
    width = round(height * layer.width / layer.height)
    layer = layer.resize((width, height), Image.Resampling.BICUBIC)
    x = _location(side) - width // 2
    canvas.paste(layer, (x, GROUND_Y - height), layer)


class VectorCoach:
    """No-asset stand-in: readable action/hand/step silhouettes, NOT finished character art."""

    def draw(self, canvas, pose, t, side, scale):
        image = Image.new("RGBA", (BASE_WIDTH, BASE_HEIGHT))
        d = ImageDraw.Draw(image)
        shift = round(3 * math.sin(t * 3.2))
        action = pose.action or ""
        if action.startswith("step_"):
            direction = -1 if action == "step_left" else 1
            if pose.state == "prepare":
                shift += round(direction * 9 * pose.phase)
            elif pose.state == "strike":
                shift += direction * 19
            elif pose.state == "recover":
                shift += round(direction * 19 * (1 - pose.phase))
        cx = 150 + shift
        outline = (54, 46, 69, 255)
        fur = (254, 249, 235, 255)
        shade = (217, 208, 222, 255)
        pink = (247, 166, 186, 255)
        shorts = (85, 145, 157, 255)
        glove = (250, 113, 107, 255)
        # Shadow, legs and broad feet establish a full-body silhouette.
        d.ellipse((cx - 77, 367, cx + 77, 384), fill=(13, 35, 54, 90))
        for dx in (-29, 29):
            d.line((cx + dx // 2, 307, cx + dx, 359), fill=outline, width=27)
            d.line((cx + dx // 2, 307, cx + dx, 359), fill=fur, width=19)
            d.ellipse((cx + dx - 24, 351, cx + dx + 24, 377), fill=fur, outline=outline, width=4)
        d.ellipse((cx - 63, 215, cx + 63, 324), fill=fur, outline=outline, width=5)
        d.rounded_rectangle((cx - 59, 291, cx + 59, 331), radius=18,
                            fill=shorts, outline=outline, width=4)
        d.ellipse((cx - 31, 237, cx + 30, 294), fill=shade)
        # Ears and head are rendered behind the arms.
        for dx, lean in ((-36, -8), (36, 8)):
            d.ellipse((cx + dx - 20 + lean, 22, cx + dx + 20 + lean, 149),
                      fill=fur, outline=outline, width=5)
            d.ellipse((cx + dx - 9 + lean, 42, cx + dx + 9 + lean, 133), fill=pink)
        d.ellipse((cx - 73, 112, cx + 73, 248), fill=fur, outline=outline, width=5)
        d.ellipse((cx - 41, 178, cx - 29, 190), fill=outline)
        d.ellipse((cx + 29, 178, cx + 41, 190), fill=outline)
        d.ellipse((cx - 9, 197, cx + 9, 208), fill=pink)
        d.arc((cx - 17, 201, cx + 17, 221), 0, 180, fill=outline, width=3)
        # Coach's screen-side hand equals the trainee's named screen side.
        hands = {-1: [cx - 51, 239], 1: [cx + 51, 239]}
        if action.startswith(("left_", "right_")) and not action.startswith("step_"):
            hand = -1 if action.startswith("left_") else 1
            kind = action.split("_", 1)[1]
            if pose.state == "prepare":
                hands[hand] = [cx + hand * (51 - 16 * pose.phase), 241]
            elif pose.state in ("strike", "recover"):
                power = 1.0 if pose.state == "strike" else 1 - pose.phase
                reach = {"jab": 46, "hook": 28, "uppercut": 15}[kind]
                rise = {"jab": 38, "hook": 72, "uppercut": 94}[kind]
                hands[hand] = [round(cx + hand * (51 + reach * power)),
                               round(239 - rise * power)]
        for hand in (-1, 1):
            shoulder = (cx + hand * 52, 252)
            target = tuple(round(v) for v in hands[hand])
            d.line((shoulder, target), fill=outline, width=29)
            d.line((shoulder, target), fill=fur, width=20)
            x, y = target
            d.ellipse((x - 24, y - 25, x + 24, y + 24),
                      fill=glove, outline=outline, width=5)
            d.arc((x - 17, y - 18, x + 15, y + 9), 200, 340,
                  fill=(255, 197, 172, 255), width=4)
        _composite(canvas, image, side, scale)


@lru_cache(maxsize=96)
def _sprite_image(path):
    with Image.open(path) as img:
        return img.convert("RGBA")


class SpriteCoach:
    """Pack format v1: transparent PNGs indexed by action.state and normalized phase."""

    def __init__(self, skin):
        self.base = (ASSETS / skin).resolve()
        try:
            self.base.relative_to(ASSETS.resolve())
        except ValueError as exc:
            raise ValueError("Invalid coach skin path") from exc
        path = self.base / "manifest.json"
        if not path.is_file():
            raise ValueError(f"Missing coach sprite pack: {path}; use renderer=vector until art exists")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("version") != 1 or not isinstance(manifest.get("clips"), dict):
            raise ValueError("Coach manifest requires version 1 and clips object")
        self.clips = {}
        for key, frames in manifest["clips"].items():
            if not isinstance(key, str) or not isinstance(frames, list) or not frames:
                raise ValueError(f"Invalid coach clip: {key!r}")
            resolved = []
            for item in frames:
                if not isinstance(item, str) or not item.endswith(".png"):
                    raise ValueError(f"Coach frame must be a PNG: {item!r}")
                frame = (self.base / item).resolve()
                try:
                    frame.relative_to(self.base)
                except ValueError as exc:
                    raise ValueError("Coach PNG path escapes the skin directory") from exc
                if not frame.is_file():
                    raise ValueError(f"Missing coach frame: {frame}")
                resolved.append(frame)
            self.clips[key] = resolved
        if "idle" not in self.clips:
            raise ValueError("Coach sprite pack must include the idle clip")

    def draw(self, canvas, pose, t, side, scale):
        key = "idle" if pose.action is None else f"{pose.action}.{pose.state}"
        frames = self.clips.get(key)
        if not frames:
            raise ValueError(f"Coach skin is missing clip {key!r}; do not silently show the wrong punch")
        frame = frames[min(len(frames) - 1, int(pose.phase * len(frames)))]
        _composite(canvas, _sprite_image(str(frame)), side, scale)


class CoachLayer:
    def __init__(self, notes, settings):
        self.settings = validate_coach_config(settings)
        self.enabled = self.settings["enabled"]
        if self.enabled:
            self.timeline = CoachTimeline(notes)
            self.renderer = (VectorCoach() if self.settings["renderer"] == "vector"
                             else SpriteCoach(self.settings["skin"]))

    def draw(self, canvas, t):
        if self.enabled:
            pose = self.timeline.at(t)
            self.renderer.draw(canvas, pose, t, self.settings["side"], self.settings["scale"])
