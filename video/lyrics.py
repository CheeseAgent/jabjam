"""Read line onsets from a local LRC companion. Only timestamps enter the course."""
import re


TIMESTAMP = re.compile(r"\[(\d+):([0-5]\d)(?:[.:](\d{1,3}))?\]")
OFFSET = re.compile(r"\[offset:\s*([+-]?\d+)\s*\]", re.IGNORECASE)


def read_lrc_starts(path):
    starts_ms = set()
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
        if line and not re.fullmatch(r"\[[^\]]*\]", line):
            starts_ms.update(stamps)
    if not starts_ms:
        raise ValueError(f"{path.name} contains no timed lyric lines. Use [mm:ss.xx] followed by words")
    # A positive LRC display offset makes all lines arrive earlier.
    return sorted({max(0, t - offset_ms) / 1000 for t in starts_ms})
