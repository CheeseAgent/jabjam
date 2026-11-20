"""Export a local JabJam course to a standalone MP4. Linux, Python 3.9+."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

from arena import Arena
from movements import MOVEMENTS
from choreography import MIN_GAP, arrange

ROOT = Path(__file__).resolve().parents[1]


def fields(obj, allowed, label):
    if not isinstance(obj, dict) or set(obj) - set(allowed):
        raise ValueError(f"{label}: expected an object with fields from {', '.join(allowed)}")
    return obj


def number(value, low, high, label):
    if type(value) not in (int, float) or not low <= value <= high:
        raise ValueError(f"{label} must be between {low} and {high}")
    return value


def config(path, song_title=None, difficulty=None, min_gap=None, beat_offset_ms=None):
    data = fields(json.loads(path.read_text()), ("version", "course", "actions", "picture"), "config")
    if type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("Expected config version 1")
    course = fields(data["course"], ("title", "song_title", "music", "difficulty", "bpm", "min_gap", "movement_set", "beat_offset_ms"), "course")
    if course.get("movement_set", "classic") not in ("classic", "mixed", "padwork"):
        raise ValueError("movement_set must be classic, mixed or padwork")
    if song_title is not None:
        course["song_title"] = song_title
    if "song_title" in course:
        title = course["song_title"]
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 128:
            raise ValueError("Use a song title of 1–128 characters")
    music = course["music"]
    if not isinstance(music, str) or not music:
        raise ValueError("Expected a local music path or builtin:demo")
    if music != "builtin:demo":
        music = (path.parent / music).resolve()
        if music.suffix.lower() not in (".mp3", ".wav", ".ogg") or not music.is_file():
            raise ValueError("Expected a local MP3, WAV or Ogg Vorbis file")
        if not 16 <= music.stat().st_size <= 64 * 1024 * 1024:
            raise ValueError("Audio file must fit within 64 MiB")
    difficulty = difficulty or course.get("difficulty", "normal")
    if difficulty not in ("easy", "normal"):
        raise ValueError("difficulty must be easy or normal")
    course["difficulty"] = difficulty
    requested_gap = course.get("min_gap", MIN_GAP[difficulty]) if min_gap is None else min_gap
    course["min_gap"] = max(MIN_GAP[difficulty], number(requested_gap, 0, 600, "min_gap"))
    if "bpm" in course:
        number(course["bpm"], 60, 180, "bpm")
    offset = course.get("beat_offset_ms", 0) if beat_offset_ms is None else beat_offset_ms
    course["beat_offset_ms"] = number(offset, -250, 250, "beat_offset_ms")
    actions = data.get("actions", "auto")
    if actions != "auto":
        if not isinstance(actions, list) or not 1 <= len(actions) <= 1000:
            raise ValueError("actions must be auto or a nonempty list of up to 1000 notes")
        last = -1
        for note in actions:
            fields(note, ("time", "action"), "note")
            t = number(note["time"], 0, 600, "note time")
            if note["action"] not in MOVEMENTS or t <= last:
                raise ValueError("Expected known actions with strictly increasing times")
            last = t
    picture = fields(data.get("picture", {}), ("size", "fps", "approach_seconds", "left_color", "right_color"), "picture")
    size = picture.get("size", [1280, 720])
    if size not in ([640, 360], [960, 540], [1280, 720]) or any(type(n) is not int for n in size):
        raise ValueError("Choose 640x360, 960x540 or 1280x720")
    fps = picture.get("fps", 24)
    if type(fps) is not int or fps not in (24, 25, 30):
        raise ValueError("fps must be 24, 25 or 30")
    number(picture.get("approach_seconds", 2), 0.7, 4, "approach_seconds")
    for key in ("left_color", "right_color"):
        if key in picture and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(picture[key])):
            raise ValueError(f"{key} must be a #RRGGBB color")
    return course, music, actions, picture


def prepare(course, music, actions, tmp):
    generated = tmp / "demo.wav"
    chart_file = tmp / "auto.json"
    if music == "builtin:demo" or actions == "auto":
        env = dict(os.environ)
        for key in ("DATA", "CONFIG", "CACHE"):
            env[f"XDG_{key}_HOME"] = str(tmp / key.lower())
        subprocess.run(["godot", "--headless", "--path", str(ROOT), "--script", "res://video/prepare.gd",
                        "--", str(music), str(generated), "auto" if actions == "auto" else "manual",
                        course.get("difficulty", "normal"), str(course.get("bpm", 0)), str(chart_file)],
                       env=env, check=True, timeout=240)
    audio = generated if music == "builtin:demo" else music
    probe = subprocess.check_output(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
                                    "-select_streams", "a:0", "-show_entries", "stream=codec_name,duration:stream_tags=title:format_tags=title",
                                    "-of", "json", str(audio)])
    metadata = json.loads(probe)
    streams = metadata["streams"]
    if not streams:
        raise ValueError("Audio track missing")
    if audio.suffix.lower() == ".ogg" and streams[0]["codec_name"] != "vorbis":
        raise ValueError("Expected Ogg Vorbis")
    duration = number(float(streams[0]["duration"]), 8, 600, "audio duration")
    chart = None
    if actions == "auto":
        chart = json.loads(chart_file.read_text())
        notes = chart["notes"]
        offset = course["beat_offset_ms"] / 1000.0
        notes = [dict(note, time=round(note["time"] + offset, 3)) for note in notes
                 if 3.0 <= note["time"] + offset < duration - 0.4]
    else:
        notes = actions
    if not notes:
        raise ValueError("No notes remain after beat offset correction")
    if notes[-1]["time"] >= duration:
        raise ValueError("Every action must fall before the end of the music")
    # Vorbis stores tags on the audio stream; MP3 usually stores them on the container.
    tags = {key.lower(): value for owner in (streams[0], metadata.get("format", {}))
            for key, value in owner.get("tags", {}).items()}
    fallback = "JabJam Demo Loop" if music == "builtin:demo" else audio.stem
    title = " ".join((course.get("song_title") or tags.get("title", "")).split()) or fallback
    return audio, duration, arrange(notes, course, actions == "auto", chart), title[:128], chart


def export(path, output, song_title=None, difficulty=None, min_gap=None, beat_offset_ms=None):
    course, music, actions, picture = config(path, song_title, difficulty, min_gap, beat_offset_ms)
    if output.suffix.lower() != ".mp4":
        raise ValueError("Output must end in .mp4")
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(dir=output.parent) as folder:
        tmp = Path(folder).resolve()
        audio, duration, notes, title, chart = prepare(course, music, actions, tmp)
        arena = Arena(title, picture, notes, duration)
        size = picture.get("size", [1280, 720])
        fps = picture.get("fps", 24)
        temp_mp4 = tmp / "render.mp4"
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-filter_threads", "1", "-f", "rawvideo",
               "-pixel_format", "rgb24", "-video_size", f"{size[0]}x{size[1]}", "-framerate", str(fps),
               "-i", "pipe:0", "-protocol_whitelist", "file,pipe", "-i", str(audio), "-map", "0:v", "-map", "1:a:0",
               "-c:v", "libx264", "-threads:v", "1", "-preset", "veryfast", "-tune", "zerolatency",
               "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
               "-metadata", f"title={title}", "-t", str(duration), "-movflags", "+faststart", str(temp_mp4)]
        with subprocess.Popen(cmd, stdin=subprocess.PIPE) as encoder:
            try:
                for frame in range(math.ceil(duration * fps)):
                    encoder.stdin.write(arena.frame(frame / fps).tobytes())
                encoder.stdin.close()
                if encoder.wait() != 0:
                    raise RuntimeError("FFmpeg failed to encode video")
            except BaseException:
                encoder.kill()
                raise
        os.replace(temp_mp4, output)
    if chart is not None:
        diagnostics = {"algorithm": chart.get("version"), "bpm": chart.get("bpm"),
                       "tempo_confidence": chart.get("confidence"),
                       "beat_offset_ms": course["beat_offset_ms"],
                       "sections": chart.get("sections", []), "notes": notes}
        output.with_suffix(".chart.json").write_text(
            json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n")
    shortest = min((b["time"] - a["time"] for a, b in zip(notes, notes[1:])), default=None)
    gap_text = f"{shortest:.3f}s" if shortest is not None else "n/a"
    print(f"{title} [{course['difficulty']}], shortest interval {gap_text}")
    print(f"{output}: {size[0]}x{size[1]} @ {fps} fps, {duration:.2f}s, {len(notes)} actions, "
          f"exported in {time.monotonic() - started:.2f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--song-title", help="Song name shown in the header and MP4 metadata")
    parser.add_argument("--difficulty", choices=MIN_GAP, help="Override the course difficulty")
    parser.add_argument("--min-gap", type=float, help="Minimum seconds between actions")
    parser.add_argument("--beat-offset-ms", type=float, help="Correct cue time by -250 to +250 milliseconds")
    args = parser.parse_args()
    try:
        export(args.config, args.output, args.song_title, args.difficulty, args.min_gap, args.beat_offset_ms)
    except (OSError, KeyError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
        sys.exit(f"JabJam export failed: {exc}")
