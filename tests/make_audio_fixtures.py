"""Regenerate original test-only pulse tracks; requires ffmpeg on the developer machine."""
import math
import pathlib
import struct
import subprocess
import tempfile
import wave

root = pathlib.Path(__file__).parent / "fixtures"
root.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as directory:
    wav_path = pathlib.Path(directory) / "pulse.wav"
    rate = 16000
    with wave.open(str(wav_path), "wb") as out:
        out.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        samples = bytearray()
        for index in range(rate * 24):
            time = index / rate
            beat = time % 0.5
            amp = 0 if 8 <= time < 12 else (0.18 if time < 8 else 0.8)
            value = amp * math.exp(-beat * 40) * math.sin(2 * math.pi * 220 * time)
            samples.extend(struct.pack("<h", int(value * 32767)))
        out.writeframes(samples)
    for suffix, codec in (("mp3", "libmp3lame"), ("ogg", "libvorbis")):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav_path), "-c:a", codec,
                        str(root / ("pulse." + suffix))], check=True)
