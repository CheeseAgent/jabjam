"""Recreate the assembled art and QA plates using the same renderer as the course."""
import argparse
from functools import lru_cache
import math
import subprocess
import tempfile
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "video"))
from coach_avatar import RigCoach
from coach_timeline import CoachPose, CoachTimeline
from course import config
from movements import MOVEMENTS

OUT = ROOT / "docs/coach-preview"
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-{}.ttc"
BG, PANEL, WHITE, MUTED = "#132330", "#203443", "#fff5e8", "#b4cbd0"
MINT, CORAL = "#84dcce", "#ff998a"


@lru_cache(maxsize=24)
def font(size, bold):
    return ImageFont.truetype(FONT.format("Bold" if bold else "Regular"), size, index=2)


def text(d, pos, value, size, color=WHITE, bold=False):
    d.text(pos,value,fill=color,font=font(size,bold),anchor="lt")


def paste(canvas, image, xy, size):
    scaled = image.resize(size,Image.Resampling.LANCZOS)
    canvas.paste(scaled,xy,scaled)


def poses(rig):
    gallery = Image.new("RGB", (760, 1774), BG)
    d = ImageDraw.Draw(gallery)
    text(d,(26,22),"小奶茶  /  动作对照",36,bold=True)
    text(d,(27,76),"JabJam    ·    跟练者视角    ·    左右以屏幕为准",19,MINT)
    samples = [("待机",CoachPose("idle",None,.25)),("庆祝",CoachPose("celebrate",None,.42))]
    samples += [(move.label,CoachPose("strike",key,0)) for key,move in MOVEMENTS.items()]
    for i,(label,pose) in enumerate(samples):
        x,y = 16+(i%2)*370,116+(i//2)*329
        d.rounded_rectangle((x,y,x+356,y+316), radius=16, fill=PANEL)
        paste(gallery,rig.frame(pose),(x+65,y+6),(225,279))
        text(d,(x+16,y+269),label,24,bold=True)
        text(d,(x+16,y+298),pose.action or pose.state,13,MUTED)
    gallery.save(OUT/"key-poses.jpg",quality=90,subsampling=0)


def joints(rig):
    sheet = Image.new("RGB",(1280,1240),BG)
    d = ImageDraw.Draw(sheet)
    text(d,(24,18),"关节与步法  /  屏幕左侧",34,bold=True)
    text(d,(26,73),"圆点是转轴，角度相对父节点。侧步图的地面刻线固定在两脚的起始位置。",19,MINT)
    rows = [
        ("左直拳","left_jab",[("抱架","idle",0),("起手","prepare",.42),("前伸","prepare",.77),("拳面向前","strike",0)]),
        ("左摆拳","left_hook",[("抱架","idle",0),("回拉蓄力","prepare",.50),("横摆","prepare",.79),("落拍","strike",0)]),
        ("左上勾拳","left_uppercut",[("抱架","idle",0),("下沉蓄力","prepare",.50),("上行","prepare",.81),("落拍","strike",0)]),
        ("左侧步","step_left",[("前脚抬起","prepare",.64),("前脚落地","strike",0),("后脚跟上","recover",.48),("双脚站稳","recover",1)]),
    ]
    for r,(label,action,stages) in enumerate(rows):
        step = action.startswith("step")
        bones = ["thigh","shin","foot"] if step else ["upper_arm","lower_arm","glove"]
        crop = (84,415,336,589) if step else (46,244,309,452)
        for col,(title,state,phase) in enumerate(stages):
            pose = CoachPose(state,None if state == "idle" else action,phase)
            x,y = 16+col*314,116+r*279
            d.rounded_rectangle((x,y,x+302,y+266),12,fill=PANEL)
            text(d,(x+12,y+9),label+"  /  "+title,19,bold=True)
            w, _, yaw, _ = rig._sample(pose)
            im = rig.frame(pose)
            draw = ImageDraw.Draw(im)
            for side in (["left","right"] if step else ["left"]):
                parts = [name+"_"+side for name in bones]
                points = [w[n][:2] for n in parts]
                draw.line(points,fill=CORAL if side == "left" else MINT,width=3)
                for px,py in points:
                    draw.ellipse((px-4,py-4,px+4,py+4),fill=WHITE,outline="#172938",width=1)
            if step:
                draw.line((86,576,334,576),fill=MUTED)
                for px in [191,289]:
                    draw.line((px,572,px,582),fill=MINT,width=2)
            img = im.crop(crop)
            img.thumbnail((274,191),Image.Resampling.LANCZOS)
            sheet.paste(img,(x+(302-img.width)//2,y+34),img)
            values = []
            for part in bones:
                n = part+"_left"
                b = next(item for item in rig.bones if item["id"] == n)
                values.append(round(math.degrees(w[n][2]-w[b["parent"]][2])))
            names = ("左髋","膝","踝") if step else ("肩","肘","腕")
            text(d,(x+12,y+(233 if step else 222)),"   ".join(f"{k} {v}°" for k,v in zip(names,values)),16,MUTED)
            if not step:
                hips,chest = (round(math.degrees(yaw[k])) for k in ("hips","chest"))
                text(d,(x+12,y+244),f"侧转    髋 {hips}°   胸 {chest}°",15,MINT)
    sheet.save(OUT/"joint-rotations.jpg",quality=90,subsampling=0)


def review_video(rig, output):
    """Mobile close-up on the same song clock, at native cutout resolution."""
    _, audio, notes, picture = config(ROOT/"courses/coach-demo.json")
    timeline = CoachTimeline(notes,cutout=True)
    fps = picture["fps"]
    duration = float(subprocess.check_output(["ffprobe","-v","error","-select_streams","a:0",
                     "-show_entries","stream=duration","-of","csv=p=0",str(audio)]))
    width, height = 540, 680
    base = Image.new("RGB",(width,height),BG)
    d = ImageDraw.Draw(base)
    d.line((22,66,518,66),fill="#385363",width=1)
    d.line((42,637,498,637),fill="#71909b",width=2)
    for x in (30+191,30+289):
        d.line((x,637,x,643),fill=MINT,width=2)
    text(d,(22,653),"JabJam  /  小奶茶",14,MUTED)
    text(d,(391,653),"跟练者视角",14,MUTED)
    phase_labels = {"idle":"待机","prepare":"准备","strike":"落拍","recover":"收拳","celebrate":"庆祝"}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        partial = Path(tmp)/"review.mp4"
        command = ["ffmpeg","-nostdin","-v","error","-f","rawvideo","-pix_fmt","rgb24",
                   "-s",f"{width}x{height}","-r",str(fps),"-i","pipe:0","-i",str(audio),
                   "-map","0:v","-map","1:a:0","-c:v","libx264","-threads:v","1","-preset","fast",
                   "-crf","19","-pix_fmt","yuv420p","-c:a","aac","-b:a","96k","-t",str(duration),
                   "-movflags","+faststart",str(partial)]
        with subprocess.Popen(command, stdin=subprocess.PIPE) as encoder:
            try:
                for n in range(math.ceil(duration*fps)):
                    pose = timeline.at(n/fps)
                    actor = rig.frame(pose)
                    frame = base.copy()
                    frame.paste(actor,(30,62),actor)
                    draw = ImageDraw.Draw(frame)
                    move = MOVEMENTS.get(pose.action)
                    title = move.label if move else "小奶茶"
                    label = phase_labels[pose.state]
                    if move and move.kind == "step":
                        label = {"prepare":"前脚先迈","strike":"前脚落地","recover":"后脚跟上"}[pose.state]
                    elif move and pose.state == "prepare" and move.kind in ("hook","uppercut"):
                        label = "蓄力" if pose.phase <= .65 else "出拳"
                    text(draw,(24,20),title,29,WHITE,True)
                    text(draw,(402,26),label,19,MINT)
                    encoder.stdin.write(frame.tobytes())
                encoder.stdin.close()
                if encoder.wait() != 0:
                    raise RuntimeError("FFmpeg failed to encode the coach close-up")
            except BaseException:
                encoder.kill()
                raise
        partial.replace(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, help="Also write the native-size MP4 review")
    args = parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    rig = RigCoach("milktea").rig
    rig.frame(CoachPose("idle",None,0)).save(OUT/"assembled.png")
    poses(rig)
    joints(rig)
    if args.video:
        review_video(rig,args.video)


if __name__ == "__main__":
    main()
