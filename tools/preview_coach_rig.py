"""Recreate the assembled art and QA plates using the same renderer as the course."""
import math
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "video"))
from coach_avatar import RigCoach
from coach_timeline import CoachPose
from movements import MOVEMENTS

OUT = ROOT / "docs/coach-preview"
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-{}.ttc"
BG, PANEL, WHITE, MUTED = "#132330", "#203443", "#fff5e8", "#b4cbd0"
MINT, CORAL = "#84dcce", "#ff998a"


def text(d, pos, value, size, color=WHITE, bold=False):
    font = ImageFont.truetype(FONT.format("Bold" if bold else "Regular"), size, index=2)
    d.text(pos,value,fill=color,font=font,anchor="lt")


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
    sheet = Image.new("RGB",(960,1240),BG)
    d = ImageDraw.Draw(sheet)
    text(d,(24,18),"关节旋转  /  屏幕左侧",34,bold=True)
    text(d,(26,73),"圆点是实际转轴。下方角度包含绑定角，为相对父节点的顺时针旋转。",19,MINT)
    rows = [("左直拳","left_jab"),("左摆拳","left_hook"),("左上勾拳","left_uppercut"),("向左侧步","step_left")]
    for r,(label,action) in enumerate(rows):
        step = action.startswith("step")
        parts = (["thigh_left","shin_left","foot_left"] if step else
                 ["upper_arm_left","lower_arm_left","glove_left"])
        crop = (90,409,324,592) if step else (20,234,272,452)
        for col,(title,p) in enumerate([
            ("待机",CoachPose("idle",None,0)),("预备",CoachPose("prepare",action,.44)),
            ("落拍",CoachPose("strike",action,0))]):
            x,y = 16+col*314,116+r*279
            d.rounded_rectangle((x,y,x+302,y+266),12,fill=PANEL)
            text(d,(x+12,y+9),label+"  /  "+title,19,bold=True)
            w = rig.transforms(p)
            im = rig.frame(p)
            draw = ImageDraw.Draw(im)
            points = [(w[n][0],w[n][1]) for n in parts]
            draw.line(points,fill=CORAL,width=3)
            for px,py in points:
                draw.ellipse((px-4,py-4,px+4,py+4),fill=MINT,outline="#172938",width=1)
            img = im.crop(crop)
            img.thumbnail((274,191),Image.Resampling.LANCZOS)
            sheet.paste(img,(x+(302-img.width)//2,y+34),img)
            values = []
            for n in parts:
                b = next(item for item in rig.bones if item["id"] == n)
                values.append(round(math.degrees(w[n][2]-w[b["parent"]][2])))
            names = ("髋","膝","踝") if step else ("肩","肘","腕")
            text(d,(x+12,y+233),"   ".join(f"{k} {v}°" for k,v in zip(names,values)),16,MUTED)
    sheet.save(OUT/"joint-rotations.jpg",quality=90,subsampling=0)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rig = RigCoach("milktea").rig
    rig.frame(CoachPose("idle",None,0)).save(OUT/"assembled.png")
    poses(rig)
    joints(rig)


if __name__ == "__main__":
    main()
