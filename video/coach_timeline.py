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
    stance: int = 0  # Planted position before this cue, in strides.
    # A standalone editor/plate pose has no song timestamp.
    focused: Optional[bool] = None
    depth: int = 0
    lead_foot: str = "left"


def validate_coach_config(value):
    """Validate the optional picture.coach contract without loading rendering libraries."""
    if not isinstance(value, dict):
        raise ValueError("picture.coach must be an object")
    allowed = {"enabled", "renderer", "skin", "side", "scale", "lead_foot", "show_stance_label"}
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
    lead_foot = value.get("lead_foot", "left")
    if lead_foot not in ("left", "right"):
        raise ValueError("picture.coach.lead_foot must be left or right")
    show_label = value.get("show_stance_label", True)
    if type(show_label) is not bool:
        raise ValueError("picture.coach.show_stance_label must be a boolean")
    return dict(enabled=enabled, renderer=renderer, skin=skin, side=side,
                scale=float(scale), lead_foot=lead_foot, show_stance_label=show_label)


class CoachTimeline:
    """Stateless pose selection: t is always seconds since the song began."""

    def __init__(self, notes, celebrate=False, *, cutout=False, lead_foot="left"):
        if lead_foot not in ("left", "right"):
            raise ValueError("lead_foot must be left or right")
        self.lead_foot = lead_foot
        self.cutout = cutout
        self.celebrate = celebrate or cutout
        self.notes = notes
        self.times = [note["time"] for note in notes]
        if any(a >= b for a, b in zip(self.times, self.times[1:])):
            raise ValueError("Coach timeline notes must be sorted by ascending time")
        if any(note["action"] not in MOVEMENTS for note in notes):
            raise ValueError("Coach timeline received an unknown action")

        self.stances = [0]
        self.depths = [0]
        self.focus_starts, self.focus_ends = [], []
        face = TIMING["cutout"]["focus"]
        for note in notes:
            movement = MOVEMENTS[note["action"]]
            step = movement.side if cutout and movement.kind == "step" else 0
            depth_step = (1 if movement.kind == "advance" else -1 if movement.kind == "retreat" else 0) if cutout else 0
            self.stances.append(max(-1, min(1, self.stances[-1] + step)))
            self.depths.append(max(-1, min(1, self.depths[-1] + depth_step)))
            if cutout and movement.kind in ("jab", "hook", "uppercut", "duck"):
                start = max(0., note["time"] - face["lead"])
                end = note["time"] + face["hold"]
                if self.focus_ends and start <= self.focus_ends[-1] + face["merge_gap"]:
                    self.focus_ends[-1] = end
                else:
                    self.focus_starts.append(start)
                    self.focus_ends.append(end)

    def at(self, t):
        if not math.isfinite(t) or t < 0:
            raise ValueError("Coach time must be a nonnegative, finite song timestamp")
        index = bisect_right(self.times, t)
        face_index = bisect_right(self.focus_starts, t) - 1
        focused = face_index >= 0 and t < self.focus_ends[face_index]
        previous = self.notes[index - 1] if index else None
        upcoming = self.notes[index] if index < len(self.notes) else None
        prepare, strike, recover = PREPARE_SECONDS, STRIKE_SECONDS, RECOVER_SECONDS
        landing = TIMING["minimum_landing"]
        if self.cutout:
            profile = TIMING["cutout"]
            if upcoming:
                prepare = profile["prepare"][MOVEMENTS[upcoming["action"]].kind]
                prepare = min(prepare, upcoming["time"])
            if previous and MOVEMENTS[previous["action"]].kind in ("step", "advance", "retreat"):
                recover = profile["step_recover"]
            if previous and upcoming:
                # Share a short gap between full curves instead of skipping the load
                # or interrupting the trailing foot. The authored hit stays fixed.
                gap = upcoming["time"] - previous["time"]
                fit = min(1., gap / (strike + recover + prepare))
                prepare, strike, recover = prepare*fit, strike*fit, recover*fit
            landing = 0.
        if upcoming:
            until_hit = upcoming["time"] - t
            after_previous = t - previous["time"] if previous else float("inf")
            if 0 < until_hit <= prepare and after_previous >= landing:
                return CoachPose("prepare", upcoming["action"], 1-until_hit/prepare, self.stances[index], focused, self.depths[index], self.lead_foot)
        if previous:
            elapsed = t - previous["time"]
            if elapsed < strike:
                return CoachPose("strike", previous["action"], elapsed/strike, self.stances[index-1], focused, self.depths[index-1], self.lead_foot)
            if elapsed < strike + recover:
                return CoachPose("recover", previous["action"], (elapsed-strike)/recover, self.stances[index-1], focused, self.depths[index-1], self.lead_foot)
            if self.celebrate and not upcoming:
                phase = (elapsed - strike - recover) / TIMING["celebrate"]
                if 0 <= phase < 1:
                    return CoachPose("celebrate", None, phase, self.stances[index], focused, self.depths[index], self.lead_foot)
        return CoachPose("idle", None, (t % IDLE_SECONDS)/IDLE_SECONDS, self.stances[index], focused, self.depths[index], self.lead_foot)
