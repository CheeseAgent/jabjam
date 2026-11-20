"""Video-only timing and arrangement. All times are seconds on the source song."""
from movements import MOVEMENTS

MIN_GAP = {"easy": 1.1, "normal": 0.45}
RECOVERY_GAP = {"easy": 1.35, "normal": 0.90}
STEP_GAP = {"easy": 1.75, "normal": 1.5}


def required_gap(previous, current, course):
    gap = course["min_gap"]
    difficulty = course["difficulty"]
    if previous.kind == "step" or current.kind == "step":
        return max(gap, STEP_GAP[difficulty])
    if previous.side == current.side or previous.kind in ("hook", "uppercut"):
        return max(gap, RECOVERY_GAP[difficulty])
    return gap


def pace_notes(notes, course, automatic):
    """Keep authored actions intact or skip crowded beats in the automatic punch chart."""
    kept = []
    for note in notes:
        if kept:
            previous = kept[-1]
            before = MOVEMENTS[previous["action"]]
            after = MOVEMENTS[note["action"]]
            gap = required_gap(before, after, course)
            if note["time"] - previous["time"] + 1e-9 < gap:
                if automatic:
                    continue
                raise ValueError(f"Action at {note['time']}s needs {gap:g}s after {previous['time']}s")
            if automatic and before.side == after.side and before.kind != "step" and after.kind != "step":
                continue
        kept.append(note)
    return kept


def mixed_round(notes, course):
    """Use existing beat times for uppercuts and paired out-and-back steps."""
    # The input is an alternating punch chart. Both types of hook use the same recovery.
    uppercuts = {"left_hook": "left_uppercut", "right_hook": "right_uppercut"}
    counts = dict.fromkeys(uppercuts, 0)
    result = []
    for note in notes:
        action = note["action"]
        if action in uppercuts:
            counts[action] += 1
            if counts[action] % 2 == 0:
                action = uppercuts[action]
        result.append({"time": note["time"], "action": action})

    # One eight-cue window per 24 cues. Leave three beat intervals to move out,
    # return, and settle before punching again. Edit backwards to keep indices stable.
    windows = range(8, len(result) - 8, 24)
    for start in reversed(windows):
        times = [result[i]["time"] for i in (start - 1, start + 2, start + 5, start + 8)]
        rest = max(course["min_gap"], STEP_GAP[course["difficulty"]])
        if any(b - a + 1e-9 < rest for a, b in zip(times, times[1:])):
            continue
        outward, back = "step_left", "step_right"
        if (start - 8) // 24 % 2:
            outward, back = back, outward
        result[start:start + 8] = [{"time": times[1], "action": outward},
                                   {"time": times[2], "action": back}]
    return result


def arrange(notes, course, automatic):
    paced = pace_notes(notes, course, automatic)
    if automatic and course["difficulty"] == "normal" and course.get("movement_set") == "mixed":
        return mixed_round(paced, course)
    return paced
