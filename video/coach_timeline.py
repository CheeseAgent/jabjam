"""Pure, timestamp-driven coaching poses. No pixels, audio engine or frame state."""
from bisect import bisect_right
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Optional

from movements import MOVEMENTS

TIMING_PATH = Path(__file__).resolve().parents[1] / "assets/coaches/timing.json"
TIMING = json.loads(TIMING_PATH.read_text(encoding="utf-8"))
PREPARE_SECONDS = TIMING["prepare"]
STRIKE_SECONDS = TIMING["strike"]
RECOVER_SECONDS = TIMING["recover"]
IDLE_SECONDS = TIMING["idle"]


@dataclass(frozen=True)
class CoachPose:
    state: str
    action: Optional[str]
    phase: float


def validate_coach_config(value):
    """Validate the optional picture.coach contract without loading rendering libraries."""
    if not isinstance(value, dict):
        raise ValueError("picture.coach must be an object")
    allowed = {"enabled", "renderer", "skin", "side", "scale"}
    unknown = set(value) - allowed
    if unknown:
        raise ValueError("picture.coach: unknown field(s) " + ", ".join(sorted(unknown)))
    enabled = value.get("enabled", False)
    if type(enabled) is not bool:
        raise ValueError("picture.coach.enabled must be a boolean")
    renderer = value.get("renderer", "vector")
    if renderer not in ("vector", "sprite", "rig"):
        raise ValueError("picture.coach.renderer must be vector, sprite or rig")
    side = value.get("side", "right")
    if side not in ("left", "right"):
        raise ValueError("picture.coach.side must be left or right")
    scale = value.get("scale", 1.0)
    if type(scale) not in (int, float) or not math.isfinite(scale) or not .6 <= scale <= 1.1:
        raise ValueError("picture.coach.scale must be between 0.6 and 1.1")
    skin = value.get("skin", "milktea")
    if not isinstance(skin, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,39}", skin):
        raise ValueError("picture.coach.skin must be a lowercase asset-pack ID")
    return dict(enabled=enabled, renderer=renderer, skin=skin, side=side, scale=float(scale))


class CoachTimeline:
    """Stateless pose selection: t is always seconds since the song began."""

    def __init__(self, notes, celebrate=False):
        self.celebrate = celebrate
        self.notes = notes
        self.times = [note["time"] for note in notes]
        if any(a >= b for a, b in zip(self.times, self.times[1:])):
            raise ValueError("Coach timeline notes must be sorted by ascending time")
        if any(note["action"] not in MOVEMENTS for note in notes):
            raise ValueError("Coach timeline received an unknown action")

    def at(self, t):
        if not math.isfinite(t) or t < 0:
            raise ValueError("Coach time must be a nonnegative, finite song timestamp")
        index = bisect_right(self.times, t)
        previous = self.notes[index - 1] if index else None
        upcoming = self.notes[index] if index < len(self.notes) else None
        # Start the next wind-up after the preceding punch has visibly landed.
        if upcoming:
            until_hit = upcoming["time"] - t
            after_previous = t - previous["time"] if previous else float("inf")
            if 0 < until_hit <= PREPARE_SECONDS and after_previous >= TIMING["minimum_landing"]:
                return CoachPose("prepare", upcoming["action"], 1 - until_hit / PREPARE_SECONDS)
        if previous:
            elapsed = t - previous["time"]
            if elapsed < STRIKE_SECONDS:
                return CoachPose("strike", previous["action"], elapsed / STRIKE_SECONDS)
            if elapsed < STRIKE_SECONDS + RECOVER_SECONDS:
                return CoachPose("recover", previous["action"],
                                 (elapsed - STRIKE_SECONDS) / RECOVER_SECONDS)
            if self.celebrate and not upcoming:
                phase = (elapsed - STRIKE_SECONDS - RECOVER_SECONDS) / TIMING["celebrate"]
                if 0 <= phase < 1:
                    return CoachPose("celebrate", None, phase)
        return CoachPose("idle", None, (t % IDLE_SECONDS) / IDLE_SECONDS)
