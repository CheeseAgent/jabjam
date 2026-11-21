"""Video-only timing and arrangement. All times are seconds on the source song."""
from bisect import bisect_left
from math import atan2, ceil, cos, pi, sin

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



# A small coaching vocabulary, not isolated random punches. Entries can be extended
# without changing rendering, course schemas, or chart caching.
# 直 = jab/straight, 摆 = hook, 勾 = uppercut; each pattern is mirrored.
PADWORK_COMBOS = {
    "warmup": (
        ("straight_pair", "直直", ("jab", "jab")),
        ("jab_hook", "直摆", ("jab", "hook")),
    ),
    "steady": (
        ("jab_jab_hook", "直直摆", ("jab", "jab", "hook")),
        ("jab_jab_uppercut", "直直勾", ("jab", "jab", "uppercut")),
        ("jab_hook_jab", "直摆直", ("jab", "hook", "jab")),
        ("jab_uppercut_jab", "直勾直", ("jab", "uppercut", "jab")),
        ("jab_jab_hook_jab", "直直摆直", ("jab", "jab", "hook", "jab")),
        ("jab_jab_uppercut_jab", "直直勾直", ("jab", "jab", "uppercut", "jab")),
    ),
    "peak": (
        ("jab_jab_hook_uppercut_jab", "直直摆勾直",
         ("jab", "jab", "hook", "uppercut", "jab")),
        ("jab_jab_hook_jab_uppercut", "直直摆直勾",
         ("jab", "jab", "hook", "jab", "uppercut")),
        ("jab_uppercut_jab_hook_jab", "直勾直摆直",
         ("jab", "uppercut", "jab", "hook", "jab")),
        ("jab_jab_uppercut_hook_jab", "直直勾摆直",
         ("jab", "jab", "uppercut", "hook", "jab")),
        ("jab_hook_jab_uppercut_jab", "直摆直勾直",
         ("jab", "hook", "jab", "uppercut", "jab")),
        ("jab_jab_hook_jab_hook", "直直摆直摆",
         ("jab", "jab", "hook", "jab", "hook")),
    ),
}


def _percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def _beat_times(notes, chart):
    if "beats" in chart:
        return chart["beats"]
    # Older analysis files only stored sparse cues and a global tempo.
    period = 60 / chart["bpm"]
    angles = [2 * pi * (note["time"] % period) / period for note in notes[:32]]
    phase = atan2(sum(sin(a) for a in angles), sum(cos(a) for a in angles)) % (2*pi) * period / (2*pi)
    duration = chart.get("duration", notes[-1]["time"] + period)
    return [round(phase + i * period, 3) for i in range(ceil((duration-phase) / period))]


def _combo_cues(template, beats, start, start_hand, course):
    """Choose whole measured beats and leave time to recover after each punch."""
    key, label, kinds = template
    built = []
    slot = start
    for index, kind in enumerate(kinds):
        side = "left" if (start_hand + index) % 2 == 0 else "right"
        action = f"{side}_{kind}"
        if built:
            last = built[-1]
            gap = required_gap(MOVEMENTS[last["action"]], MOVEMENTS[action], course)
            slot = bisect_left(beats, last["time"] + gap - 1e-9, lo=slot + 1)
            if slot == len(beats):
                return [], slot
        built.append({"time": beats[slot], "action": action, "combo_name": label,
                      "combo_id": key, "combo_step": index + 1, "combo_total": len(kinds)})
    return built, slot


def padwork_round(notes, course, chart):
    """Repeat complete mirrored combinations on the song's measured beat grid."""
    if not notes or not chart:
        return []
    bpm = chart.get("bpm", 0)
    if not isinstance(bpm, (int, float)) or not 60 <= bpm <= 180:
        raise ValueError("Padwork requires a valid auto-chart BPM")
    sections = chart.get("sections") or []
    if not sections:
        return pace_notes(notes, course, True)
    levels = [s.get("intensity", s.get("energy", 0.0)) for s in sections]
    high_cut = max(0.58, _percentile([v for v in levels if v >= 0.09], 0.60))
    mid_cut = 0.28

    beats = _beat_times(notes, chart)
    duration = chart.get("duration", notes[-1]["time"] + 60 / bpm)
    beat = ((bisect_left(beats, 3.0) + 7) // 8) * 8
    result = []
    phrase_no = 0
    repetitions = {"warmup": 0, "steady": 0, "peak": 0}

    while beat < len(beats) and beats[beat] < duration - 0.4:
        start = beats[beat]
        section_index = min(len(levels) - 1, max(0, int(start / 4.0)))
        level = levels[section_index]
        band = ("peak" if level >= high_cut else
                "steady" if level >= mid_cut else
                "warmup" if level >= 0.09 else None)

        if band is None:
            beat += 8
            phrase_no += 1
            continue

        seen = repetitions[band]
        library = PADWORK_COMBOS[band]
        template = library[(seen // 2) % len(library)]
        # The same technique is drilled from both sides before changing pattern.
        candidate, end_beat = _combo_cues(template, beats, beat, seen % 2, course)
        if not candidate:
            break
        recovery = max(course["min_gap"], RECOVERY_GAP[course["difficulty"]])
        next_slot = bisect_left(beats, candidate[-1]["time"] + recovery - 1e-9, lo=end_beat + 1)
        phrase_beats = max(8, 4 * ((next_slot - beat + 3) // 4))

        # Reject the *entire* exercise if it would clip at the end or collide
        # with a preceding exercise; never turn a five-hit combo into four.
        complete = candidate[-1]["time"] < duration - 0.4
        enough_rest = (not result or
                       candidate[0]["time"] - result[-1]["time"] + 1e-9 >=
                       required_gap(MOVEMENTS[result[-1]["action"]],
                                    MOVEMENTS[candidate[0]["action"]], course))
        if complete and enough_rest:
            for note in candidate:
                note["combo_no"] = phrase_no + 1
            result.extend(candidate)
            repetitions[band] += 1
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
