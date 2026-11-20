"""Check the two uppercuts and two floor cues in the encoded eight-move fixture."""
import json
from pathlib import Path
import sys
from PIL import Image

from render_video_job import ROOT, check, frame


def verify(path):
    course = json.loads((ROOT / "courses/eight-moves.json").read_text())
    preview = Image.new("RGB", (1600, 450))
    for i, note in enumerate(course["actions"]):
        at = note["time"]
        # The sample uses 24 fps and a two-second approach.
        before = frame(path, at - 2/24)
        preview.paste(before.resize((400, 225)), (i % 4 * 400, i // 4 * 225))
        action = note["action"]
        side = -1 if "left" in action else 1
        if action.endswith("uppercut"):
            u = 1 - (2/24)/2
            p = .25*u + .75*u*u
            x, y, r = 640+side*(23+232*p), 210+300*p, 11+58*p
            def bright(dx, dy):
                return max(before.getpixel((round(x+dx*r), round(y+dy*r)))) > 140
            check(not bright(-side*.30, -.68), f"Missing upward tip on {action}")
            check(bright(0, -.68) and not bright(0, .49), f"Missing J-shaped pocket on {action}")
        elif action.startswith("step_"):
            hit = frame(path, at)
            x = 640 + side*255
            def bright(dx, dy):
                return max(hit.getpixel((x+side*dx, 579+dy))) > 140
            check(bright(62, 0) and not bright(51, 0), f"Missing outward chevron on {action}")
            check(not bright(-26, -16) and bright(-26, 7), f"Missing split footprint on {action}")
            check(not bright(0, -80), f"Step rendered as a punch on {action}")
    preview.save(path.with_suffix(".jpg"), quality=92)


if __name__ == "__main__":
    verify(Path(sys.argv[1]))
