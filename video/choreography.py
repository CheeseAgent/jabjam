"""Video-only timing and arrangement. All times are seconds on the source song."""
from bisect import bisect_left, bisect_right
from itertools import groupby
import json
from math import atan2, ceil, cos, pi, sin
from pathlib import Path

from movements import MOVEMENTS

DIFFICULTIES = json.loads(Path(__file__).with_name("difficulties.json").read_text())
MIN_GAP = {name: profile["gap"] for name, profile in DIFFICULTIES.items()}


def required_gap(previous, current, course):
    gap = course["min_gap"]
    profile = DIFFICULTIES[course["difficulty"]]
    if previous.kind == "step" or current.kind == "step":
        return max(gap, profile["step"])
    if previous.side == current.side or previous.kind in ("hook", "uppercut"):
        return max(gap, profile["recovery"])
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
        rest = max(course["min_gap"], DIFFICULTIES[course["difficulty"]]["step"])
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
    "six": (
        ("double_three", "直直摆直直勾", ("jab", "jab", "hook", "jab", "jab", "uppercut")),
        ("six_turn", "直摆直勾摆直", ("jab", "hook", "jab", "uppercut", "hook", "jab")),
    ),
    "eight": (
        ("two_fours", "直直摆直直勾摆直", ("jab", "jab", "hook", "jab", "jab", "uppercut", "hook", "jab")),
        ("eight_turn", "直勾直摆直直勾直", ("jab", "uppercut", "jab", "hook", "jab", "jab", "uppercut", "jab")),
    ),
}

# Warm, steady and peak sections use progressively longer complete patterns.
SECTION_BANDS = {"normal": ("warmup", "steady", "peak"), "hard": ("warmup", "peak", "six"),
                 "expert": ("steady", "six", "eight")}

# Each finale starts with the exact same three moves as its teaching phrase.
CHORUS_FINALES = {
    "jab_jab_hook": "jab_jab_hook_uppercut_jab",
    "jab_jab_uppercut": "jab_jab_uppercut_hook_jab",
    "jab_hook_jab": "jab_hook_jab_uppercut_jab",
    "jab_uppercut_jab": "jab_uppercut_jab_hook_jab",
}
DEFAULT_CHORUS = "jab_jab_hook"
CHORUS_LABELS = {"learn": "副歌学招", "mirror": "副歌换边", "repeat": "副歌再来", "extend": "副歌加长"}


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


def _combo_cues(band, seen, beats, start, course, spacing_beats):
    library = PADWORK_COMBOS[band]
    return _place_combo(library[(seen // 2) % len(library)], seen, beats, start, course, spacing_beats)


def _place_combo(template, turn, beats, start, course, spacing_beats):
    """Place the lead at start, then find measured beats with enough recovery."""
    key, label, kinds = template
    built = []
    hit = start
    spacing_time = round(start + course.get("beat_offset_ms", 0) / 1000, 3)
    for index, kind in enumerate(kinds):
        side = "left" if (turn + index) % 2 == 0 else "right"
        action = f"{side}_{kind}"
        if built:
            last = built[-1]
            gap = required_gap(MOVEMENTS[last["action"]], MOVEMENTS[action], course)
            slot = bisect_left(spacing_beats, spacing_time + gap - 1e-9)
            if slot == len(beats):
                return []
            hit = beats[slot]
            spacing_time = spacing_beats[slot]
        built.append({"time": hit, "action": action, "combo_name": label,
                      "combo_id": key, "combo_step": index + 1, "combo_total": len(kinds)})
    return built


def _intensity_band(start, levels, high_cut, difficulty):
    level = levels[min(len(levels) - 1, int(start / 4.0))]
    warm, steady, peak = SECTION_BANDS[difficulty]
    return peak if level >= high_cut else steady if level >= 0.28 else warm if level >= 0.09 else None


def uses_padwork(course):
    return course["difficulty"] in SECTION_BANDS and course.get("movement_set") == "padwork"


def _lyric_deadline(start, following, starts, period, phrasing):
    if following == len(starts):
        return None
    next_line = starts[following]
    if phrasing == "paired" and following + 1 < len(starts):
        after_pair = starts[following + 1]
        if max(next_line - start, after_pair - next_line) <= 4.5 * period:
            return after_pair
    return next_line


def _lyric_padwork(beats, spacing_beats, course, duration, levels, high_cut, period):
    starts = course["lyric_starts"]
    offset = course.get("beat_offset_ms", 0) / 1000
    difficulty = course["difficulty"]
    recovery = max(course["min_gap"], DIFFICULTIES[difficulty]["recovery"])
    bands = list(PADWORK_COMBOS)
    repetitions = dict.fromkeys(PADWORK_COMBOS, 0)
    result = []
    ready_at = 3.0
    for index, start in enumerate(starts):
        if start + 1e-9 < ready_at or start >= duration - 0.4:
            continue
        deadline = _lyric_deadline(start, index + 1, starts, period, course.get("lyric_phrasing", "paired"))
        band = _intensity_band(start, levels, high_cut, difficulty) or "warmup"
        for choice in reversed(bands[:bands.index(band) + 1]):
            # LRC marks are already on the audio clock. Convert the lead to the
            # analysis clock so the final calibration lands it back on that syllable.
            candidate = _combo_cues(choice, repetitions[choice], beats, start - offset, course, spacing_beats)
            if not candidate:
                continue
            finish = round(candidate[-1]["time"] + offset, 3)
            if finish >= duration - 0.4 or (deadline is not None and finish + recovery > deadline + 1e-9):
                continue
            for note in candidate:
                note["combo_no"] = index + 1
            result.extend(candidate)
            repetitions[choice] += 1
            ready_at = finish + recovery
            break
    return result


def _with_choruses(ordinary, beats, spacing_beats, course, duration, period):
    """Reserve marked pickups first. Keep ordinary groups whole on either side."""
    starts = course["chorus_starts"]
    lyrics = course.get("lyric_starts", [])
    offset = course.get("beat_offset_ms", 0) / 1000
    rest = max(course["min_gap"], DIFFICULTIES[course["difficulty"]]["recovery"])
    base = course.get("chorus_combo", DEFAULT_CHORUS)
    templates = {item[0]: item for band in PADWORK_COMBOS.values() for item in band}

    def song_time(note):
        return round(note["time"] + offset, 3)

    choruses = []
    for turn, start in enumerate(starts):
        if not 3 <= start < duration - 0.4:
            raise ValueError(f"Chorus at {start:g}s falls outside the playable part of this recording "
                             f"(3s to {duration - 0.4:g}s)")
        group = _place_combo(templates[base], turn, beats, start - offset, course, spacing_beats)
        if not group or song_time(group[-1]) >= duration - 0.4:
            raise ValueError(f"No complete chorus fits at {start:g}s before the song ends")
        if turn + 1 < len(starts) and song_time(group[-1]) + rest > starts[turn + 1] + 1e-9:
            raise ValueError(f"Chorus at {start:g}s needs more recovery before the mark at {starts[turn + 1]:g}s")
        cue = "mirror" if turn % 2 else "repeat"
        if turn == 0:
            cue = "learn"
        if turn >= 2 and turn == len(starts) - 1:
            deadline = _lyric_deadline(start, bisect_right(lyrics, start), lyrics, period,
                                       course.get("lyric_phrasing", "paired"))
            extended = _place_combo(templates[CHORUS_FINALES[base]], turn, beats,
                                    start - offset, course, spacing_beats)
            if extended and song_time(extended[-1]) < duration - 0.4:
                if deadline is None or song_time(extended[-1]) + rest <= deadline + 1e-9:
                    group, cue = extended, "extend"
        for note in group:
            note["chorus_cue"] = cue
        choruses.append(group)

    groups = list(choruses)
    upcoming = 0
    for _, members in groupby(ordinary, key=lambda note: note["combo_no"]):
        group = list(members)
        start = song_time(group[0])
        while upcoming < len(choruses) and song_time(choruses[upcoming][-1]) + rest <= start + 1e-9:
            upcoming += 1
        if upcoming == len(choruses) or song_time(group[-1]) + rest <= starts[upcoming] + 1e-9:
            groups.append(group)
    result = []
    for number, group in enumerate(sorted(groups, key=lambda g: g[0]["time"]), 1):
        for note in group:
            result.append(dict(note, combo_no=number))
    return result


def padwork_round(notes, course, chart):
    """Repeat complete mirrored combinations on the song's measured beat grid."""
    if not notes or not chart:
        return []
    bpm = chart.get("bpm", 0)
    if not isinstance(bpm, (int, float)) or not 60 <= bpm <= 180:
        raise ValueError("Padwork requires a valid auto-chart BPM")
    sections = chart.get("sections") or []
    if not sections and "lyric_starts" not in course and "chorus_starts" not in course:
        return pace_notes(notes, course, True)
    levels = [s.get("intensity", s.get("energy", 0.0)) for s in sections] or [0.28]
    high_cut = max(0.58, _percentile([v for v in levels if v >= 0.09], 0.60))

    beats = _beat_times(notes, chart)
    # Check spacing on the final millisecond song clock. Emit source beats so
    # the exporter applies the calibration only once, including to lyric pickups.
    offset = course.get("beat_offset_ms", 0) / 1000
    spacing_beats = [round(t + offset, 3) for t in beats]
    duration = chart.get("duration", notes[-1]["time"] + 60 / bpm)
    if "lyric_starts" in course:
        result = _lyric_padwork(beats, spacing_beats, course, duration, levels, high_cut, 60 / bpm)
    else:
        result = _beat_padwork(beats, spacing_beats, course, duration, levels, high_cut)
    if "chorus_starts" in course:
        return _with_choruses(result, beats, spacing_beats, course, duration, 60 / bpm)
    return result


def _beat_padwork(beats, spacing_beats, course, duration, levels, high_cut):
    beat = ((bisect_left(beats, 3.0) + 7) // 8) * 8
    result = []
    phrase_no = 0
    repetitions = dict.fromkeys(PADWORK_COMBOS, 0)
    offset = course.get("beat_offset_ms", 0) / 1000
    last_finish = 0.0

    while beat < len(beats) and beats[beat] < duration - 0.4:
        start = beats[beat]
        band = _intensity_band(start, levels, high_cut, course["difficulty"])

        if band is None:
            beat += 8
            phrase_no += 1
            continue

        seen = repetitions[band]
        # The same technique is drilled from both sides before changing pattern.
        candidate = _combo_cues(band, seen, beats, start, course, spacing_beats)
        if not candidate:
            break
        recovery = max(course["min_gap"], DIFFICULTIES[course["difficulty"]]["recovery"])
        finish = round(candidate[-1]["time"] + offset, 3)
        next_slot = bisect_left(spacing_beats, finish + recovery - 1e-9)
        phrase_beats = max(8, 4 * ((next_slot - beat + 3) // 4))

        # Reject the *entire* exercise if it would clip at the end or collide
        # with a preceding exercise; never turn a five-hit combo into four.
        complete = candidate[-1]["time"] < duration - 0.4
        enough_rest = (not result or
                       spacing_beats[beat] - last_finish + 1e-9 >=
                       required_gap(MOVEMENTS[result[-1]["action"]],
                                    MOVEMENTS[candidate[0]["action"]], course))
        if complete and enough_rest:
            for note in candidate:
                note["combo_no"] = phrase_no + 1
            result.extend(candidate)
            last_finish = finish
            repetitions[band] += 1
        beat += phrase_beats
        phrase_no += 1

    return result


def arrange(notes, course, automatic, chart=None):
    if automatic and uses_padwork(course):
        return padwork_round(notes, course, chart)
    paced = pace_notes(notes, course, automatic)
    if automatic and course["difficulty"] != "easy" and course.get("movement_set") == "mixed":
        return mixed_round(paced, course)
    return paced
