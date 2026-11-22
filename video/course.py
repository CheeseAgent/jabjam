"""Read and check version 1 course files using only the Python standard library."""
import json
import re
from math import ceil

from choreography import CHORUS_FINALES, CHORUS_LABELS, DEFAULT_CHORUS, MIN_GAP, arrange, uses_padwork
from movements import MOVEMENTS
from coach_timeline import validate_coach_config
from lyrics import LYRIC_STYLES, read_lrc_lines, visible_text

# Floor vanishing points on the 1280x720 canvas, with the artwork between the HUD bars.
ART_HORIZONS = {"undersea-office": 338, "jellyfish-radio": 300, "panda-hotpot": 280, "moon-carrots": 331}
SCENES = ("neon", "classic", *ART_HORIZONS)
COUNTER_SIDES = ("auto", "left", "right", "off")
COUNTER_STYLES = ("minimal", "arcade", "ring")


def fixed_scene(value):
    """Older course files and CLI invocations used art-tour. Keep its opening scene."""
    return "undersea-office" if value == "art-tour" else value


def fields(obj, allowed, label):
    if not isinstance(obj, dict):
        raise ValueError(f"{label} must be an object")
    unknown = sorted(set(obj) - set(allowed))
    if unknown:
        raise ValueError(f"{label}: unknown field(s) {', '.join(unknown)}. Choose from {', '.join(allowed)}")
    return obj


def number(value, low, high, label):
    if type(value) not in (int, float) or not low <= value <= high:
        raise ValueError(f"{label} must be between {low} and {high}")
    return value


def read_actions(actions):
    if actions == "auto":
        return actions
    maximum = ceil(600 / min(MIN_GAP.values())) + 1
    if not isinstance(actions, list) or not 1 <= len(actions) <= maximum:
        raise ValueError(f'actions must be "auto" or a list of 1–{maximum} notes')
    last = -1
    for index, note in enumerate(actions):
        label = f"actions[{index}]"
        fields(note, ("time", "action", "combo_id", "combo_no", "combo_name", "combo_step", "combo_total",
                      "chorus_cue"), label)
        t = number(note.get("time"), 0, 600, f"{label}.time")
        action = note.get("action")
        if not isinstance(action, str) or action not in MOVEMENTS:
            raise ValueError(f"{label}.action: unknown ID {action!r}. Choose from {', '.join(MOVEMENTS)}")
        if t <= last:
            raise ValueError(f"{label}.time ({t:g}s) must be later than actions[{index-1}].time ({last:g}s)")
        if "chorus_cue" in note and note["chorus_cue"] not in tuple(CHORUS_LABELS):
            raise ValueError(f"{label}.chorus_cue must be one of " + ", ".join(CHORUS_LABELS))
        if any(key in note for key in ("combo_name", "combo_step", "combo_total", "chorus_cue")):
            if not isinstance(note.get("combo_name"), str) or not note["combo_name"].strip():
                raise ValueError(f"{label}.combo_name must name the combination")
            step, total = note.get("combo_step"), note.get("combo_total")
            if type(step) is not int or type(total) is not int or not 1 <= step <= total:
                raise ValueError(f"{label} needs integer combo_step and combo_total with 1 <= step <= total")
        if "combo_id" in note and not isinstance(note["combo_id"], str):
            raise ValueError(f"{label}.combo_id must be a string")
        if "combo_no" in note and (type(note["combo_no"]) is not int or note["combo_no"] < 1):
            raise ValueError(f"{label}.combo_no must be a positive integer")
        last = t
    return actions


def read_picture(picture, scene, lyrics=None, combo_side=None, combo_style=None):
    fields(picture, ("size", "fps", "approach_seconds", "left_color", "right_color", "scene", "coach",
                     "lyrics", "combo_side", "combo_style"), "picture")
    for field, override, choices in (("lyrics", lyrics, LYRIC_STYLES), ("combo_side", combo_side, COUNTER_SIDES),
                                     ("combo_style", combo_style, COUNTER_STYLES)):
        if override is not None:
            picture[field] = override
        if field in picture and picture[field] not in choices:
            raise ValueError(f"picture.{field} must be one of " + ", ".join(choices))
    if scene is not None or "scene" in picture:
        picture["scene"] = fixed_scene(scene if scene is not None else picture["scene"])
    if picture.get("scene", "neon") not in SCENES:
        raise ValueError("picture.scene must be one of " + ", ".join(SCENES))
    size = picture.get("size", [1280, 720])
    if size not in ([640, 360], [960, 540], [1280, 720]) or any(type(n) is not int for n in size):
        raise ValueError("picture.size must be [640, 360], [960, 540] or [1280, 720]")
    fps = picture.get("fps", 24)
    if type(fps) is not int or fps not in (24, 25, 30):
        raise ValueError("picture.fps must be 24, 25 or 30")
    number(picture.get("approach_seconds", 2), 0.7, 4, "picture.approach_seconds")
    for key in ("left_color", "right_color"):
        if key in picture and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(picture[key])):
            raise ValueError(f"picture.{key} must be a #RRGGBB color")
    if "coach" in picture:
        validate_coach_config(picture["coach"])
    return picture


def ordered_times(values, field):
    if not isinstance(values, list) or not values:
        raise ValueError(f"{field} must be a nonempty list of times in seconds")
    times = [round(number(t, 0, 600, field), 3) for t in values]
    if any(a >= b for a, b in zip(times, times[1:])):
        raise ValueError(f"{field} must increase at millisecond precision")
    return times


def load_lyrics(course, music, actions, show):
    auto = actions == "auto" and uses_padwork(course)
    need_starts = auto and "lyric_starts" not in course
    lines = course.get("lyric_lines")
    if "lyric_lines" in course:
        if not isinstance(lines, list):
            raise ValueError("course.lyric_lines must be a list of timed text rows")
        for row in lines:
            fields(row, ("time", "text"), "course.lyric_lines")
            if not isinstance(row.get("text"), str):
                raise ValueError("course.lyric_lines needs a string for each text")
        times = ordered_times([row.get("time") for row in lines], "course.lyric_lines")
        lines = [{"time": t, "text": row["text"].strip()} for row, t in zip(lines, times)]
        course["lyric_lines"] = lines
    elif (need_starts or show) and music != "builtin:demo" and music.with_suffix(".lrc").is_file():
        lines = read_lrc_lines(music.with_suffix(".lrc"))
        if show:
            course["lyric_lines"] = lines
    if need_starts and lines:
        starts = [row["time"] for row in lines if row["text"]]
        if starts:
            course["lyric_starts"] = starts
    if "lyric_starts" in course:
        course["lyric_starts"] = ordered_times(course["lyric_starts"], "course.lyric_starts")


def config(path, song_title=None, difficulty=None, min_gap=None, beat_offset_ms=None, scene=None,
           lyrics=None, combo_side=None, combo_style=None):
    """Return effective course settings, resolved music source, actions, and picture."""
    data = fields(json.loads(path.read_text(encoding="utf-8")), ("version", "course", "actions", "picture"), "config")
    if type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("version must be the integer 1")
    course = fields(data.get("course"), ("title", "song_title", "music", "difficulty", "bpm", "min_gap",
                                         "movement_set", "beat_offset_ms", "lyric_starts", "lyric_lines",
                                         "lyric_phrasing", "display_beats", "chorus_starts", "chorus_combo"), "course")
    if "chorus_starts" in course:
        course["chorus_starts"] = ordered_times(course["chorus_starts"], "course.chorus_starts")
    if "chorus_combo" in course:
        if "chorus_starts" not in course or course["chorus_combo"] not in tuple(CHORUS_FINALES):
            raise ValueError("course.chorus_combo needs chorus_starts and must be one of " + ", ".join(CHORUS_FINALES))
    if course.get("lyric_phrasing", "paired") not in ("single", "paired"):
        raise ValueError("course.lyric_phrasing must be single or paired")
    if "display_beats" in course:
        course["display_beats"] = ordered_times(course["display_beats"], "course.display_beats")
    if course.get("movement_set", "classic") not in ("classic", "mixed", "padwork"):
        raise ValueError("course.movement_set must be classic, mixed or padwork")
    if song_title is not None:
        course["song_title"] = song_title
    if "song_title" in course:
        title = course["song_title"]
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 128:
            raise ValueError("course.song_title must contain 1–128 characters")
    music = course.get("music")
    if not isinstance(music, str) or not music:
        raise ValueError("course.music must be a local music path or builtin:demo")
    if music != "builtin:demo":
        music = (path.parent / music).resolve()
        if music.suffix.lower() not in (".mp3", ".wav", ".ogg") or not music.is_file():
            raise ValueError(f"course.music must point to a local MP3, WAV or Ogg Vorbis file: {music}")
        if not 16 <= music.stat().st_size <= 64 * 1024 * 1024:
            raise ValueError(f"course.music must be between 16 bytes and 64 MiB: {music}")
    difficulty = difficulty or course.get("difficulty", "normal")
    if not isinstance(difficulty, str) or difficulty not in MIN_GAP:
        raise ValueError("course.difficulty must be one of " + ", ".join(MIN_GAP))
    course["difficulty"] = difficulty
    requested_gap = course.get("min_gap", MIN_GAP[difficulty]) if min_gap is None else min_gap
    course["min_gap"] = max(MIN_GAP[difficulty], number(requested_gap, 0, 600, "course.min_gap"))
    if "bpm" in course:
        number(course["bpm"], 60, 180, "course.bpm")
    offset = course.get("beat_offset_ms", 0) if beat_offset_ms is None else beat_offset_ms
    course["beat_offset_ms"] = number(offset, -250, 250, "course.beat_offset_ms")
    actions = read_actions(data.get("actions", "auto"))
    picture = read_picture(data.get("picture", {}), scene, lyrics, combo_side, combo_style)
    load_lyrics(course, music, actions, picture.get("lyrics", "off") != "off")
    return course, music, actions, picture


def check_course(path, **overrides):
    """Check the config and authored spacing without analyzing audio or rendering frames."""
    course, _, actions, picture = config(path, **overrides)
    settings = f"{course['difficulty']}, min_gap {course['min_gap']:g}s"
    if picture.get("lyrics", "off") != "off":
        count = sum(bool(visible_text(row["text"])) for row in course.get("lyric_lines", ()))
        settings += f", {count} visible lyric lines" if count else ", no lyric text to display"
    if actions == "auto":
        if uses_padwork(course) and "lyric_starts" in course:
            settings += f", {len(course['lyric_starts'])} timed lyric lines"
        if "chorus_starts" in course:
            if uses_padwork(course):
                settings += f", {len(course['chorus_starts'])} chorus marks ({course.get('chorus_combo', DEFAULT_CHORUS)})"
            else:
                settings += ", chorus marks inactive for this difficulty or movement set"
        return f"OK ({settings}): automatic course. Audio duration and generated actions are checked during preparation."
    arrange(actions, course, automatic=False)
    return (f"OK ({settings}): {len(actions)} manual actions, spacing checked. "
            "Audio duration is checked during preparation.")
