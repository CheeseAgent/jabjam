"""A compact, seekable amplitude envelope from the song, and three stage visualizers."""
from array import array
from math import cos, pi, sin, sqrt
import subprocess
import sys

from PIL import ImageDraw

ENVELOPE_HZ = 100
SAMPLES_PER_BIN = 80


def song_envelope(audio, duration):
    """One byte per 10 ms of source audio. A single pass also works for hand-authored charts."""
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-threads", "1", "-protocol_whitelist", "file,pipe",
           "-i", str(audio), "-map", "0:a:0", "-t", str(duration), "-ac", "1",
           "-ar", str(ENVELOPE_HZ * SAMPLES_PER_BIN), "-f", "s16le", "pipe:1"]
    peaks = array("H")
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as decoder:
        for chunk in iter(lambda: decoder.stdout.read(2 * SAMPLES_PER_BIN * ENVELOPE_HZ), b""):
            pcm = array("h")
            pcm.frombytes(chunk)
            if sys.byteorder != "little":
                pcm.byteswap()
            for pos in range(0, len(pcm), SAMPLES_PER_BIN):
                group = pcm[pos:pos + SAMPLES_PER_BIN]
                rms = sqrt(sum(v*v for v in group) / len(group))
                peak = max(max(group), -min(group))
                peaks.append(round(.65*rms + .35*peak))
        if decoder.wait() or not peaks:
            raise ValueError(f"Cannot read the song for the waveform: {audio}")
    reference = max(900, sorted(peaks)[int(.98 * len(peaks))])
    return bytes(round(255 * min(1, level / reference) ** .78) for level in peaks)


def draw_wave(im, style, envelope, t, colors):
    # The newest value sits at the inner end of each wing. A seek reads the same 640 ms.
    end = min(len(envelope), int(t * ENVELOPE_HZ + 1e-7) + 1)
    window = envelope[max(0, end - 64):end].rjust(64, b"\0")
    d = ImageDraw.Draw(im, "RGBA")
    for side, color in zip((-1, 1), colors):
        def x(fraction):
            return 640 + side * (228 + 366 * fraction)

        y = 267
        shadow = (10, 23, 39, 160)
        if style == "ribbon":
            upper, lower = [], []
            for i, value in enumerate(reversed(window)):
                fraction = i / 63
                amplitude = (value / 255) * (14 + 36*sin(pi*fraction))
                upper.append((x(fraction), y - amplitude))
                lower.append((x(fraction), y + amplitude*.68))
            d.polygon(upper + lower[::-1], fill=(*color, 70))
            d.line(upper, fill=shadow, width=9)
            d.line(upper, fill=(*color, 246), width=5)
            d.line(lower, fill=(*color, 188), width=3)
        elif style == "bars":
            for i in range(32):
                level = max(window[62-2*i:64-2*i]) / 255
                cx = round(x(i / 31))
                half = round(2 + 40 * level)
                d.rounded_rectangle((cx-4, y-half-1, cx+4, y+half+1), radius=3, fill=shadow)
                d.rounded_rectangle((cx-3, y-half, cx+3, y+half), radius=2, fill=(*color, 205))
                if half > 6:
                    d.line((cx-2, y-half, cx+2, y-half), fill=(249, 246, 223, 230), width=2)
        elif style == "orbit":
            cx, cy = 640 + side * 408, y + 16
            points = []
            # Mirror the history around the circle so the seam closes at the current sample.
            for i in range(126):
                angle = 2*pi*i/126 - pi/2
                level = window[63 - min(i, 126-i)] / 255
                radius = 49 + 40*level
                points.append((cx + radius*cos(angle), cy + radius*sin(angle)))
            d.ellipse((cx-46, cy-46, cx+46, cy+46), outline=(*color, 95), width=1)
            d.line(points + points[:1], fill=shadow, width=9)
            d.line(points + points[:1], fill=(*color, 240), width=4)
