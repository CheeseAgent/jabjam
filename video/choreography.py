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



def _percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def padwork_round(notes, course, chart):
    """Write complete coach-style combinations onto a fixed beat grid.

    This uses the V2 tempo / energy estimate, not a claim of detected downbeats.
    All spacing is in whole beats so a five-hit phrase stays a unit instead of
    having individual punches deleted by the generic pacing filter.
    """
    from math import atan2, ceil, cos, pi, sin

    if not notes or not chart:
        return []
    bpm = chart.get("bpm", 0)
    if not isinstance(bpm, (int, float)) or not 60 <= bpm <= 180:
        raise ValueError("Padwork requires a valid auto-chart BPM")
    period = 60.0 / bpm

    # V2's onset-snapped notes all originate from the same tempo grid.
    # Circular averaging avoids a wrap at 0 / period and uses the calibrated
    # notes, so beat_offset_ms is respected.
    angles = [2 * pi * (note["time"] % period) / period for note in notes[:32]]
    phase = (atan2(sum(sin(a) for a in angles), sum(cos(a) for a in angles))
             % (2 * pi)) / (2 * pi) * period

    sections = chart.get("sections") or []
    if not sections:
        return pace_notes(notes, course, True)
    levels = [s.get("intensity", s.get("energy", 0.0)) for s in sections]
    active = [v for v in levels if v >= 0.09]
    high_cut = max(0.58, _percentile(active, 0.60))
    # Use a stable floor for teaching triples even when most of the song is loud.
    mid_cut = 0.28

    # Slot widths satisfy the same physical recovery limits as manual courses.
    jab_beats = max(1, ceil((course["min_gap"] - 1e-9) / period))
    recover_beats = max(1, ceil((max(course["min_gap"],
                                      RECOVERY_GAP[course["difficulty"]]) - 1e-9) / period))
    duration = chart.get("duration", notes[-1]["time"] + period)
    beat = max(0, ceil((3.0 - phase) / (8 * period))) * 8
    result = []
    phrase_no = 0
    while phase + beat * period < duration - 0.4:
        start = phase + beat * period
        # Look at the whole phrase instead of choosing actions from isolated hits.
        section_index = min(len(levels) - 1, max(0, int(start / 4.0)))
        level = levels[section_index]
        if level >= high_cut:
            shape = ("jab", "jab", "hook", "uppercut", "jab")
            offsets = (0, jab_beats, 2 * jab_beats,
                       2 * jab_beats + recover_beats,
                       2 * jab_beats + 2 * recover_beats)
            label = "直直摆勾直"
        elif level >= mid_cut:
            shape = ("jab", "jab", "hook")
            offsets = (0, jab_beats, 2 * jab_beats)
            label = "直直摆"
        elif level >= 0.09:
            shape = ("jab", "jab")
            offsets = (0, max(jab_beats, 2))
            label = "直直"
        else:
            shape, offsets, label = (), (), ""

        # Keep a full musical bar for recovery; add bars at fast BPMs.
        last_beat = offsets[-1] if offsets else 0
        phrase_beats = max(8, 4 * ceil((last_beat + recover_beats) / 4))
        start_hand = phrase_no % 2  # 0=left, 1=right; mirror every phrase.
        candidate = []
        for index, (kind, delta) in enumerate(zip(shape, offsets)):
            when = round(start + delta * period, 3)
            if when >= duration - 0.4:
                candidate = []  # Don't start a partial combination at EOF.
                break
            side = "left" if (start_hand + index) % 2 == 0 else "right"
            candidate.append({"time": when, "action": f"{side}_{kind}",
                              "combo_name": label, "combo_step": index + 1,
                              "combo_total": len(shape), "combo_no": phrase_no + 1})
        # Reject an entire phrase if it cannot fit with its neighbor. Never
        # silently remove a single member of a coach's prescribed combo.
        if candidate and (not result or
                candidate[0]["time"] - result[-1]["time"] + 1e-9 >=
                required_gap(MOVEMENTS[result[-1]["action"]],
                             MOVEMENTS[candidate[0]["action"]], course)):
            if all(b["time"] - a["time"] + 1e-9 >=
                   required_gap(MOVEMENTS[a["action"]], MOVEMENTS[b["action"]], course)
                   for a, b in zip(candidate, candidate[1:])):
                result.extend(candidate)
        beat += phrase_beats
        phrase_no += 1
    return result


def arrange(notes, course, automatic, chart=None):
    if automatic and course["difficulty"] == "normal" and course.get("movement_set") == "padwork":
        return padwork_round(notes, course, chart)
    paced = pace_notes(notes, course, automatic)
    if automatic and course["difficulty"] == "normal" and course.get("movement_set") == "mixed":
        return mixed_round(paced, course)
    return paced
