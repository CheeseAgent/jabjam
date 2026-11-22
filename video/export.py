"""Check a local JabJam course, write its editable timeline, or render an MP4. Linux, Python 3.9+."""
import argparse
from contextlib import closing, nullcontext
from itertools import repeat
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from course import COUNTER_SIDES, COUNTER_STYLES, SCENES, TITLE_STYLES, WAVE_STYLES, check_course, config, fixed_scene, number
from choreography import MIN_GAP, arrange, uses_padwork
from lyrics import LYRIC_STYLES, visible_text

ROOT = Path(__file__).resolve().parents[1]


def calibrated_notes(timeline, offset_ms, duration):
    """Shift the final onsets once and keep boundary-clipped combos intact or absent."""
    shifted = [dict(note, time=round(note["time"] + offset_ms / 1000.0, 3)) for note in timeline]

    def in_song(note):
        return 3.0 <= note["time"] < duration - 0.4

    clipped = {note["combo_no"] for note in shifted if "combo_no" in note and not in_song(note)}
    return [note for note in shifted if in_song(note) and note.get("combo_no") not in clipped]


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
        timeline = arrange(chart["notes"], course, True, chart)
        notes = calibrated_notes(timeline, course["beat_offset_ms"], duration)
    else:
        notes = arrange(actions, course, False)
    if not notes:
        if actions == "auto" and uses_padwork(course) and "lyric_starts" in course:
            raise ValueError("No whole combination fits the timed lyric lines. Check line times, song version and min_gap")
        raise ValueError("No actions fit after spacing and beat offset. Reduce min_gap or try movement_set classic")
    last_time = notes[-1]["time"]
    if last_time >= duration:
        raise ValueError(f"Last action at {last_time:g}s must fall before the end of the music ({duration:g}s)")
    # Vorbis stores tags on the audio stream; MP3 usually stores them on the container.
    tags = {key.lower(): value for owner in (streams[0], metadata.get("format", {}))
            for key, value in owner.get("tags", {}).items()}
    fallback = "JabJam Demo Loop" if music == "builtin:demo" else audio.stem
    title = " ".join((course.get("song_title") or tags.get("title", "")).split()) or fallback
    return audio, duration, notes, title[:128], chart


def display_beats(course, chart, duration):
    if chart is None:
        return course.get("display_beats", [])
    offset = course["beat_offset_ms"] / 1000
    shifted = (round(t + offset, 3) for t in chart["beats"])
    return [t for t in shifted if 0 <= t < duration]


def export(path, output, song_title=None, difficulty=None, min_gap=None, beat_offset_ms=None, scene=None,
           lyrics=None, combo_side=None, combo_style=None, title_style=None, wave_style=None, background_video=None):
    from arena import Arena
    from audio_wave import song_envelope
    from background_video import video_frames

    course, music, actions, picture = config(path, song_title, difficulty, min_gap, beat_offset_ms, scene,
                                             lyrics, combo_side, combo_style, title_style, wave_style, background_video)
    if output.suffix.lower() != ".mp4":
        raise ValueError("Output must end in .mp4")
    clip = picture.get("background_video", "off")
    if clip != "off" and output.exists() and output.samefile(clip):
        raise ValueError("Output must be different from the background video")
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(dir=output.parent) as folder:
        tmp = Path(folder).resolve()
        audio, duration, notes, title, chart = prepare(course, music, actions, tmp)
        envelope = song_envelope(audio, duration) if picture.get("wave_style", "off") != "off" else b""
        arena = Arena(title, picture, notes, duration, beats=display_beats(course, chart, duration),
                      bpm=course.get("bpm", 120), lyric_lines=course.get("lyric_lines", ()), envelope=envelope)
        size = picture.get("size", [1280, 720])
        fps = picture.get("fps", 24)
        temp_mp4 = tmp / "render.mp4"
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-filter_threads", "1", "-f", "rawvideo",
               "-pixel_format", "rgb24", "-video_size", f"{size[0]}x{size[1]}", "-framerate", str(fps),
               "-i", "pipe:0", "-protocol_whitelist", "file,pipe", "-i", str(audio), "-map", "0:v", "-map", "1:a:0",
               "-c:v", "libx264", "-threads:v", "1", "-preset", "veryfast", "-tune", "zerolatency",
               "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
               "-metadata", f"title={title}", "-t", str(duration), "-movflags", "+faststart", str(temp_mp4)]
        frames = closing(video_frames(clip, fps)) if clip != "off" else nullcontext(repeat(None))
        with frames as backdrops, subprocess.Popen(cmd, stdin=subprocess.PIPE) as encoder:
            try:
                for frame in range(math.ceil(duration * fps)):
                    image = arena.frame(frame / fps, background_frame=next(backdrops))
                    encoder.stdin.write(image.tobytes())
                encoder.stdin.close()
                if encoder.wait() != 0:
                    raise RuntimeError("FFmpeg failed to encode video")
            except BaseException:
                encoder.kill()
                raise
        os.replace(temp_mp4, output)
    if chart is not None:
        diagnostics = {"algorithm": chart.get("version"), "bpm": chart.get("bpm"), "difficulty": course["difficulty"],
                       "tempo_confidence": chart.get("confidence"),
                       "beat_offset_ms": course["beat_offset_ms"],
                       "source_beats": chart["beats"], "sections": chart.get("sections", []), "notes": notes}
        if uses_padwork(course) and "lyric_starts" in course:
            diagnostics["lyric_starts"] = course["lyric_starts"]
        if uses_padwork(course) and "chorus_starts" in course:
            diagnostics["chorus_starts"] = course["chorus_starts"]
        diagnostics["combo_count"] = sum(note.get("combo_step") == 1 for note in notes)
        diagnostics["lyric_style"] = picture.get("lyrics", "off")
        diagnostics["visible_lyric_lines"] = (sum(bool(visible_text(row["text"])) for row in course.get("lyric_lines", ()))
                                              if diagnostics["lyric_style"] != "off" else 0)
        output.with_suffix(".chart.json").write_text(
            json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n")
    shortest = min((b["time"] - a["time"] for a, b in zip(notes, notes[1:])), default=None)
    gap_text = f"{shortest:.3f}s" if shortest is not None else "n/a"
    print(f"{title} [{course['difficulty']}], shortest interval {gap_text}")
    print(f"{output}: {size[0]}x{size[1]} @ {fps} fps, {duration:.2f}s, {len(notes)} actions, "
          f"exported in {time.monotonic() - started:.2f}s")


def write_course(path, output, **overrides):
    """Save the same notes the renderer would use as an editable course."""
    if output.suffix.lower() != ".json":
        raise ValueError("Editable course output must end in .json")
    course, music, actions, picture = config(path, **overrides)
    if output.exists() and (output.samefile(path) or (music != "builtin:demo" and output.samefile(music))):
        raise ValueError("Editable course output must be different from the source course and music")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as folder:
        tmp = Path(folder).resolve()
        _, duration, notes, title, chart = prepare(course, music, actions, tmp)
        if chart is not None:
            course["display_beats"] = display_beats(course, chart, duration)
        course["song_title"] = title
        if music != "builtin:demo":
            course["music"] = os.path.relpath(music, output.parent.resolve())
        if picture.get("background_video", "off") != "off":
            picture["background_video"] = os.path.relpath(picture["background_video"], output.parent.resolve())
        editable = {"version": 1, "course": course, "actions": notes, "picture": picture}
        ready = tmp / "course.json"
        ready.write_text(json.dumps(editable, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(ready, output)
    print(f"{output}: {len(notes)} editable actions")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path, help="Source course JSON")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("output", nargs="?", type=Path, help="MP4 to render")
    mode.add_argument("--write-course", type=Path, metavar="EDITED.json",
                      help="Write the final actions to a separate course JSON for editing")
    mode.add_argument("--check", action="store_true", help="Check course settings and authored action spacing")
    parser.add_argument("--song-title", help="Song name used in the header, opening title and MP4 metadata")
    parser.add_argument("--difficulty", choices=MIN_GAP, help="Override the course difficulty")
    parser.add_argument("--min-gap", type=float, help="Minimum seconds between actions")
    parser.add_argument("--beat-offset-ms", type=float, help="Correct cue time by -250 to +250 milliseconds")
    parser.add_argument("--scene", type=fixed_scene, choices=SCENES, help="Choose one arena for the entire song")
    parser.add_argument("--lyrics", choices=LYRIC_STYLES, help="On-screen timed lyrics, off by default")
    parser.add_argument("--combo-side", choices=COUNTER_SIDES, help="Counter position; auto is opposite the coach")
    parser.add_argument("--combo-style", choices=COUNTER_STYLES, help="Visual style of the on-screen streak")
    parser.add_argument("--title-style", choices=TITLE_STYLES, help="Opening song title for the first three seconds")
    parser.add_argument("--wave-style", choices=WAVE_STYLES, help="Stage waveform driven by the song audio")
    parser.add_argument("--background-video", metavar="PATH|off", help="Local video backdrop (CLI paths use the current directory)")
    args = parser.parse_args()
    try:
        overrides = dict(song_title=args.song_title, difficulty=args.difficulty, min_gap=args.min_gap,
                         beat_offset_ms=args.beat_offset_ms, scene=args.scene, lyrics=args.lyrics,
                         combo_side=args.combo_side, combo_style=args.combo_style, title_style=args.title_style,
                         wave_style=args.wave_style, background_video=args.background_video)
        if args.check:
            print(check_course(args.config, **overrides))
        elif args.write_course is not None:
            write_course(args.config, args.write_course, **overrides)
        else:
            export(args.config, args.output, **overrides)
    except (OSError, KeyError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
        sys.exit(f"JabJam export failed: {exc}")
