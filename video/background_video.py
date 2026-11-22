"""Stream a local clip into the 720p stage, looping its video track at EOF."""
import subprocess

from PIL import Image

STAGE_TOP = 77
STAGE_SIZE = (1280, 555)


def video_frames(path, fps):
    width, height = STAGE_SIZE
    frame_bytes = width * height * 3
    # Crop in display coordinates, including anamorphic sources. Resize only the visible area.
    sar = "if(gt(sar,0),sar,1)"
    crop = f"crop=w='min(iw,ih*{width}/{height}/({sar}))':h='min(ih,iw*({sar})*{height}/{width})'"
    filters = f"setpts=PTS-STARTPTS,fps={fps}:start_time=0:eof_action=pass,{crop},scale={width}:{height},setsar=1"
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-threads", "1", "-filter_threads", "1",
           "-protocol_whitelist", "file,pipe", "-i", str(path), "-map", "0:V:0", "-an", "-sn", "-dn",
           "-vf", filters, "-threads:v", "1", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"]
    while True:
        # Reopen on video EOF so a longer soundtrack in the clip cannot delay the loop.
        with subprocess.Popen(cmd, stdout=subprocess.PIPE) as decoder:
            try:
                seen_frame = False
                while True:
                    data = decoder.stdout.read(frame_bytes)
                    if not data:
                        break
                    if len(data) != frame_bytes:
                        raise ValueError(f"Incomplete background video frame: {path}")
                    seen_frame = True
                    yield Image.frombytes("RGB", STAGE_SIZE, data)
                if decoder.wait() or not seen_frame:
                    raise ValueError(f"Cannot decode the background video track: {path}")
            finally:
                if decoder.poll() is None:
                    decoder.kill()
