"""Parse a local LRC once for both choreography and optional on-screen lyrics."""
import re


TIMESTAMP = re.compile(r"\[(\d+):([0-5]\d)(?:[.:](\d{1,3}))?\]")
OFFSET = re.compile(r"\[offset:\s*([+-]?\d+)\s*\]", re.IGNORECASE)
WORD_TIME = re.compile(r"<\d+:[0-5]\d(?:[.:]\d{1,3})?>")
MARKER = re.compile(r"(?:句\s*|(?:line|cue)\s*#?\s*)\d+", re.IGNORECASE)
LYRIC_STYLES = ("off", "fade", "rise", "pulse")


def read_lrc_lines(path):
    by_time = {}
    offset_ms = 0
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        offset = OFFSET.fullmatch(line)
        if offset:
            offset_ms = int(offset[1])
            continue
        # Several leading tags can repeat the same lyric at different times.
        stamps = []
        stamp = TIMESTAMP.match(line)
        while stamp:
            minutes, seconds, fraction = stamp.groups()
            stamps.append(60000 * int(minutes) + 1000 * int(seconds) + int((fraction or "").ljust(3, "0")))
            line = line[stamp.end():].lstrip()
            stamp = TIMESTAMP.match(line)
        words = "" if re.fullmatch(r"\[[^\]]*\]", line) else WORD_TIME.sub("", line).strip()
        for timestamp in stamps:
            if not by_time.get(timestamp):
                by_time[timestamp] = words
    if not any(by_time.values()):
        raise ValueError(f"{path.name} contains no timed lyric lines. Use [mm:ss.xx] followed by words")
    # A positive LRC display offset makes all lines arrive earlier.
    aligned = {}
    for t, words in sorted(by_time.items()):
        at = max(0, t - offset_ms) / 1000
        if not aligned.get(at):
            aligned[at] = words
    return [{"time": t, "text": words} for t, words in aligned.items()]


def visible_text(line):
    return "" if MARKER.fullmatch(line.strip()) else line.strip()


def read_lrc_starts(path):
    return [row["time"] for row in read_lrc_lines(path) if row["text"]]
