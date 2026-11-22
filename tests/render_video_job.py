"""Render via the public CLI, report container resources and check the actual encoded media."""
import argparse
import array
from fractions import Fraction
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import time

from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "video"))
from choreography import MIN_GAP
from course import COUNTER_SIDES, COUNTER_STYLES, SCENES, TITLE_STYLES, WAVE_STYLES, fixed_scene
from lyrics import LYRIC_STYLES


def run(*args):
    return subprocess.check_output([str(a) for a in args])


def cgroup(name):
    path = Path("/sys/fs/cgroup") / name
    return path.read_text().strip() if path.exists() else None


def frame(path, t):
    # Seek half a millisecond before the expected frame to avoid rounding up.
    data = run("ffmpeg", "-loglevel", "error", "-ss", f"{max(0,t-.0005):.6f}", "-i", path,
               "-frames:v", 1, "-threads", 1, "-f", "image2pipe", "-c:v", "png", "-")
    with Image.open(io.BytesIO(data)) as im:
        return im.convert("RGB").resize((1280, 720))


def pcm(path, start, duration):
    samples = array.array("h")
    samples.frombytes(run("ffmpeg", "-v", "error", "-ss", start, "-i", path, "-t", duration,
                          "-vn", "-ac", 1, "-ar", 8000, "-f", "s16le", "-"))
    return samples


def check(condition, message):
    if not condition:
        raise ValueError(message)


def verify_course(path, config, source):
    streams = json.loads(run("ffprobe", "-v", "error", "-show_streams", "-of", "json", path))["streams"]
    video, = [s for s in streams if s["codec_type"] == "video"]
    audio, = [s for s in streams if s["codec_type"] == "audio"]
    picture = config.get("picture", {})
    fps = picture.get("fps", 24)
    check([video["width"], video["height"]] == picture.get("size", [1280,720]), "Unexpected dimensions")
    check((video["codec_name"], audio["codec_name"], video["pix_fmt"]) == ("h264","aac","yuv420p"), "Wrong format")
    check(Fraction(video["avg_frame_rate"]) == fps, "Unexpected frame rate")
    dur = float(audio["duration"])
    check(abs(float(video["duration"])-dur) <= 1/fps+.03, "Audio/video duration mismatch")
    check(abs(float(audio["start_time"])-float(video["start_time"])) < 1/fps, "Track start mismatch")
    check(abs(int(video["nb_frames"])-dur*fps) <= 2, "Missing frames")
    check(max(map(abs, pcm(path, 0, dur))) > 100, "Silent audio")
    if source is not None:
        original = float(run("ffprobe","-v","error","-select_streams","a:0","-show_entries",
                             "stream=duration","-of","csv=p=0",source))
        check(abs(original-dur) < .12, "Export truncated or extended the source track")
    return dur


def check_choreography(path, config, source):
    # This fixture has isolated notes at known timestamps. Inspect decoded pixels,
    # including the arrow tip on each side, independently of the rendering module.
    fps=config["picture"]["fps"]
    lead=config["picture"]["approach_seconds"]
    shots=[]
    for note in config["actions"][:4]:
        at=note["time"]
        hook=note["action"].endswith("hook")
        side=-1 if note["action"].startswith("left") else 1
        t=(round(at*fps)-2)/fps
        im=frame(path,t)
        u=1-(at-t)/lead
        fraction=.25*u+.75*u*u
        cx=640+side*(23+232*fraction)
        cy=210+300*fraction
        r=11+58*fraction
        def intensity(dx,dy):
            patch=(round(cx+dx*r),round(cy+dy*r))
            return max(im.getpixel(patch))
        check(intensity(.75,.55)>150, f"Missing approaching block for {note}")
        if hook:
            # Left hook points right on the left lane; right hook points left on the right lane.
            check(intensity(-side*.61,-.15)<85 and intensity(side*.61,-.15)>150,
                  f"Wrong hook arrow direction for {note}")
        else:
            check(intensity(0,-.64)<85 and intensity(.48,-.64)>150, f"Wrong jab arrow for {note}")
        # The block arrives intact on the last frame before the beat; fragments fan out on the beat.
        center=640+side*255
        last=frame(path,at-1/fps)
        impact=frame(path,at)
        after=frame(path,at+3/fps)
        area=(center-115,384,center+115,500)
        check(ImageStat.Stat(ImageChops.difference(last.crop(area),impact.crop(area))).mean[1]>8,
              f"Missing beat transition for {note}")
        wings=[(center-112,441,center-66,506),(center+66,441,center+112,506)]
        moving=sum(sum(max(p)>115 for p in ImageChops.difference(last.crop(box),after.crop(box)).getdata())
                   for box in wings)
        check(moving>120,f"Missing scattered fragments for {note}")
        prior=frame(path,at-.5)
        check(ImageStat.Stat(ImageChops.difference(im.crop(area),prior.crop(area))).mean[1]>12,
              f"Block did not approach for {note}")
        shots.extend([im,after])
    for t in (3.75,18.25):
        src=pcm(source,t,.5)
        out=pcm(path,t,.5)
        dot=sum(a*b for a,b in zip(src,out))
        corr=dot/max(1,math.sqrt(sum(a*a for a in src)*sum(b*b for b in out)))
        check(corr>.85,f"Source and output audio lost alignment at {t}s ({corr:.3f})")
    sheet=Image.new("RGB",(1280,720))
    for index,im in enumerate(shots):
        # Four punches across, preview on row one and burst on row two.
        sheet.paste(im.resize((320,180)),(320*(index//2),180*(index%2)))
    sheet.crop((0,0,1280,360)).save(path.with_suffix(".jpg"),quality=92)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("config",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("--check-cues",action="store_true",help="Check the four-punch regression fixture")
    p.add_argument("--song-title")
    p.add_argument("--difficulty", choices=MIN_GAP)
    p.add_argument("--min-gap", type=float)
    p.add_argument("--beat-offset-ms", type=float)
    p.add_argument("--scene", type=fixed_scene, choices=SCENES)
    p.add_argument("--lyrics", choices=LYRIC_STYLES)
    p.add_argument("--combo-side", choices=COUNTER_SIDES)
    p.add_argument("--combo-style", choices=COUNTER_STYLES)
    p.add_argument("--title-style", choices=TITLE_STYLES)
    p.add_argument("--wave-style", choices=WAVE_STYLES)
    p.add_argument("--background-video")
    args=p.parse_args()
    config=json.loads(args.config.read_text())
    started=time.monotonic()
    cmd = [sys.executable, str(ROOT/"video/export.py"), args.config, args.output]
    for flag, value in (("--song-title", args.song_title), ("--difficulty", args.difficulty),
                        ("--min-gap", args.min_gap), ("--beat-offset-ms", args.beat_offset_ms), ("--scene", args.scene),
                        ("--lyrics", args.lyrics), ("--combo-side", args.combo_side), ("--combo-style", args.combo_style),
                        ("--title-style", args.title_style), ("--wave-style", args.wave_style),
                        ("--background-video", args.background_video)):
        if value is not None:
            cmd.append(f"{flag}={value}")
    subprocess.run(cmd, check=True)
    elapsed=time.monotonic()-started
    peak=cgroup("memory.peak")
    report={"config":args.config.name,"elapsed_seconds":round(elapsed,2),"output_bytes":args.output.stat().st_size,
            "container_peak_bytes":int(peak) if peak and peak.isdecimal() else None,
            "container_limit_bytes":cgroup("memory.max"),"cpu_quota":cgroup("cpu.max")}
    music=config["course"]["music"]
    source=None if music=="builtin:demo" else args.config.parent/music
    duration=verify_course(args.output,config,source)
    if args.song_title:
        title = run("ffprobe", "-v", "error", "-show_entries", "format_tags=title",
                    "-of", "default=nw=1:nk=1", args.output).decode().strip()
        check(title == " ".join(args.song_title.split()), "Incorrect song title in MP4")
    if args.check_cues:
        check_choreography(args.output,config,source)
    report["duration_seconds"]=duration
    args.output.with_suffix(".resources.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report),flush=True)


if __name__=="__main__":
    main()
