"""Verify coach-demo's decoded audio/video and the artwork around each authored cue."""
import json
import math
from pathlib import Path
import sys

from PIL import ImageChops, ImageStat

from render_video_job import ROOT, frame, verify_course

sys.path.insert(0, str(ROOT / "video"))
from arena import Arena


def verify(path):
    course = json.loads((ROOT/"courses/coach-demo.json").read_text())
    duration = verify_course(path,course,ROOT/"tests/fixtures/pulse.ogg")
    arena = Arena(course["course"]["song_title"],course["picture"],course["actions"],duration)
    fps = course["picture"]["fps"]
    # Crop tightly around the character to keep HUD text and scene motion out of the metric.
    region = (995,295,1274,625)
    sample_frames = [0]
    for note in course["actions"]:
        hit = math.ceil(note["time"]*fps)
        sample_frames.extend(hit+offset for offset in (-4,-1,0,4))
    sample_frames.append(math.ceil((course["actions"][-1]["time"]+1.1)*fps))
    worst = 0.
    for n in sample_frames:
        t = n/fps
        reference = arena.frame(t).crop(region)
        decoded = frame(path,t).crop(region)
        error = max(ImageStat.Stat(ImageChops.difference(reference,decoded)).mean)
        if error > 5:
            raise ValueError(f"Coach pixels differ at {t:.3f}s / frame {n} (MAE {error:.2f})")
        worst = max(worst,error)
    print(f"Verified audio/video and {len(sample_frames)} decoded coach frames, max channel MAE {worst:.2f}/255")


if __name__ == "__main__":
    verify(Path(sys.argv[1]))
