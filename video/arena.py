"""First-person rhythm arena, drawn one frame at a time on a 1280x720 canvas."""
from bisect import bisect_left, bisect_right
from functools import lru_cache
from math import cos, pi, sin
from PIL import Image, ImageColor, ImageDraw, ImageFont

from movements import MOVEMENTS, LEFT
from cue_art import punch_icon, foot_pad, step_landing

INK = (11, 21, 36)
WHITE = (240, 248, 252)
DUSK = (135, 158, 181)
HORIZON = 210
HIT_Y = 510
SHATTER = 0.58


def blend(a, b, p):
    return tuple(round(x + (y - x) * p) for x, y in zip(a, b))


@lru_cache(maxsize=32)
def font(size, bold):
    name = "Bold" if bold else "Regular"
    return ImageFont.truetype(f"/usr/share/fonts/opentype/noto/NotoSansCJK-{name}.ttc", size, index=2)


@lru_cache(maxsize=320)
def lettering(value, size, color, bold):
    face = font(size, bold)
    x0, y0, x1, y1 = face.getbbox(value)
    mask = Image.new("L", (max(1, x1-x0), max(1, y1-y0)))
    ImageDraw.Draw(mask).text((-x0, -y0), value, font=face, fill=255)
    return Image.new("RGB", mask.size, color), mask


def text(im, xy, value, size, color=WHITE, bold=False, align="left"):
    label, mask = lettering(value, size, color, bold)
    x, y = xy
    if align == "center":
        x -= label.width / 2
    elif align == "right":
        x -= label.width
    im.paste(label, (round(x), round(y)), mask)


class Arena:
    def __init__(self, title, picture, notes, duration):
        self.notes = notes
        self.times = [note["time"] for note in notes]
        self.duration = duration
        self.lead = picture.get("approach_seconds", 2)
        self.size = tuple(picture.get("size", [1280, 720]))
        self.colors = [ImageColor.getrgb(picture.get("left_color", "#63edce")),
                       ImageColor.getrgb(picture.get("right_color", "#ff916d"))]
        self.halo = Image.new("L", (96, 96))
        glow = ImageDraw.Draw(self.halo)
        for radius in range(47, 0, -1):
            glow.ellipse((48-radius, 48-radius, 48+radius, 48+radius),
                         fill=round(155*(1-radius/48)**1.4))
        self.has_steps = any(MOVEMENTS[note["action"]].kind == "step" for note in notes)
        self.base = self.background(title)

    def background(self, title):
        im = Image.new("RGB", (1280, 720), INK)
        d = ImageDraw.Draw(im)
        for y in range(77, 632):
            factor = max(0, 1 - abs(y-HORIZON)/360)
            d.line((0, y, 1280, y), fill=blend((11, 20, 34), (34, 58, 79), factor))
        # Opposing banks of light and receding trusses frame the vanishing point.
        for sign, color in zip((-1, 1), self.colors):
            for index in range(8):
                z = .77 ** index
                edge = 640 + sign * 750 * z
                top = HORIZON - 156 * z
                bottom = HORIZON + 190 * z
                d.line((edge, top, edge, bottom), fill=(46, 70, 89), width=max(1, round(6*z)))
                d.line((edge, top, edge - sign*150*z, top+30*z),
                       fill=blend(INK, color, .46*z), width=max(1, round(4*z)))
            d.polygon([(640,HORIZON), (640+sign*505,632), (640+sign*147,632)],
                      fill=blend((21,36,53),color,.07))
            for at in (155, 485, 740, 1080, 1520):
                d.line((640,HORIZON,640+sign*at,632),fill=(48,70,90),width=2)
            d.line((640,HORIZON,640+sign*486,632),fill=blend(INK,color,.52),width=3)
        for i in range(1,12):
            y=HORIZON + (i/11)**2.6 * 420
            d.line((0,y,1280,y),fill=(41,61,79),width=1)
        d.line((0,HORIZON,1280,HORIZON),fill=(83,109,125))
        d.line((0,HIT_Y,1280,HIT_Y),fill=(135,159,176),width=2)
        for side, color in zip((-1,1), self.colors):
            x = 640+side*255
            for dx, dy in ((-1,-1),(1,-1),(-1,1),(1,1)):
                cx, cy = x+dx*85, HIT_Y+dy*65
                d.line([(cx-dx*20,cy),(cx,cy),(cx,cy-dy*16)], fill=blend(INK,color,.85),width=3)
            d.ellipse((x-91,HIT_Y+53,x+91,HIT_Y+69),outline=blend(INK,color,.55),width=2)
        # Header remains legible even with a crowded chart.
        d.rectangle((0,0,1280,76),fill=(12,21,35))
        d.line((0,76,1280,76),fill=(57,77,95))
        for i in range(3):
            x=42+11*i
            d.polygon([(x,46),(x+9,24),(x+16,24),(x+7,46)],fill=self.colors[0])
        text(im,(88,24),"JABJAM",30,WHITE,True)
        d.line((239,20,239,56),fill=(79,94,110))
        title_size=28
        while title_size > 18 and font(title_size,True).getlength(title)>660:
            title_size-=1
        if font(title_size, True).getlength(title) > 660:
            while font(title_size, True).getlength(title + "…") > 660:
                title = title[:-1]
            title += "…"
        text(im,(264,24),title,title_size,WHITE,True)
        text(im,(1234,31),"RHYTHM  /  BOXING",18,DUSK,True,"right")
        d.rectangle((0,632,1280,719),fill=(12,21,35))
        for sign,color in zip((-1,1),self.colors):
            x=42 if sign<0 else 1055
            d.rounded_rectangle((x,651,x+9,690),radius=4,fill=color)
            text(im,(x+22,657),"左侧  /  LEFT" if sign<0 else "右侧  /  RIGHT",20,color,True)
        return im

    @staticmethod
    def position(side, u):
        p=.25*u+.75*u*u
        return 640+side*(23+232*p), HORIZON+300*p, 11+58*p

    def block(self, d, move, u, color):
        side = move.side
        x,y,r = self.position(side,u)
        depth=r*.32
        # Back edges point towards the vanishing point.
        back=-side*depth
        edge=x-side*r
        d.polygon([(x-r,y-r),(x-r+back,y-r-depth*.76),(x+r+back,y-r-depth*.76),(x+r,y-r)],
                  fill=blend(color,WHITE,.40))
        d.polygon([(edge,y-r),(edge+back,y-r-depth*.76),(edge+back,y+r-depth*.76),(edge,y+r)],
                  fill=blend(color,INK,.42))
        d.rounded_rectangle((x-r,y-r,x+r,y+r),radius=max(1,int(r*.12)),fill=color,
                            outline=blend(color,WHITE,.70),width=max(1,int(r*.05)))
        d.line((x-r*.72,y+r*.78,x+r*.72,y+r*.78),fill=blend(color,INK,.28),width=max(1,int(r*.05)))
        punch_icon(d,x,y-r*.06,r*.94,move,INK)

    def burst(self, im, d, side, hook, age, color):
        x, y, _ = self.position(side, 1)
        phase = min(1.0, age / SHATTER)
        travel = 1 - (1 - phase) ** 2.6
        heat = (1 - phase) ** 1.5
        hot = blend(color, WHITE, .80)
        drift = -side * 48 * travel if hook else 0

        # A local bloom lights the rail, then two shock fronts peel away.
        width = round(150 + 230 * travel)
        mask = self.halo.resize((width, round(width * .76)))
        im.paste(blend(INK, color, heat * .64), (round(x-width/2), round(y-mask.height/2),
                 round(x-width/2)+width, round(y-mask.height/2)+mask.height), mask)
        for radius, weight in ((52 + 158 * travel, 5), (42 + 115 * travel, 2)):
            bounds = (x-radius, y-radius*.70, x+radius, y+radius*.70)
            rim = blend((46, 68, 85), hot, heat)
            for start in (12, 111, 197, 292):
                d.arc(bounds, start, start + 62, fill=rim, width=max(1, round(weight * heat)))

        # Faceted chunks tumble outwards; thinner streaks overtake them.
        for i in range(22):
            angle = 2*pi*i/22 + .12*sin(i*7)
            dx, dy = cos(angle), sin(angle)
            distance = 18 + (105 + (i*47 % 108))*travel
            cx = x + dx*distance + drift
            cy = y + dy*distance*.76 + 50*phase*phase
            spin = angle + (1 if i % 2 else -1)*phase*(1+i%4)
            ax, ay = cos(spin), sin(spin)
            length = (21 + i*7 % 17)*(1-phase)
            wing = length*(.28 + .09*(i%4))
            tip = (cx+ax*length, cy+ay*length)
            tail = (cx-ax*length, cy-ay*length)
            left = (cx-ay*wing, cy+ax*wing)
            right = (cx+ay*wing*.65, cy-ax*wing*.65)
            d.polygon([tip, left, tail], fill=blend((45,63,81), color, heat))
            d.polygon([tip, right, tail], fill=blend((48,68,85), hot, heat))
            trail = distance + 18 + (i%3)*15
            sx, sy = x + dx*trail + drift, y + dy*trail*.76
            d.line((sx, sy, sx+dx*30*heat, sy+dy*23*heat), fill=blend(INK, hot, heat), width=2)
        if phase < .4:
            flare = (1-phase/.4)**2
            star = []
            for i in range(16):
                angle = i*pi/8
                length = (92 if i%4 == 0 else 52) if i%2 == 0 else 13
                star.append((x+cos(angle)*length*flare, y+sin(angle)*length*flare*.8))
            d.polygon(star, fill=hot)

    def frame(self,t):
        im=self.base.copy()
        d=ImageDraw.Draw(im)
        index=bisect_right(self.times,t)
        end=bisect_right(self.times,t+self.lead)
        for j in range(end - 1, index - 1, -1):
            move = MOVEMENTS[self.notes[j]["action"]]
            color = self.colors[0 if move.side == LEFT else 1]
            progress = 1 - (self.times[j] - t) / self.lead
            if move.kind == "step":
                x, y, radius = self.position(move.side, progress)
                foot_pad(d, x, y + radius, radius, move, color)
            else:
                self.block(d, move, progress, color)
        for j in range(bisect_left(self.times, t - SHATTER), index):
            move = MOVEMENTS[self.notes[j]["action"]]
            color = self.colors[0 if move.side == LEFT else 1]
            age = t - self.times[j]
            if move.kind == "step":
                x, y, radius = self.position(move.side, 1)
                step_landing(d, x, y + radius, radius, move, color, age / SHATTER)
            else:
                self.burst(im, d, move.side, move.kind == "hook", age, color)
        im.paste(self.base.crop((0,632,1280,720)),(0,632))
        if t < self.times[0] - self.lead:
            text(im,(640,295),"跟随拍点 · 准备开始",36,WHITE,True,"center")
            text(im,(640,352),"直箭头打直拳   /   横弯打摆拳   /   上挑打上勾拳",20,DUSK,False,"center")
        if index and t - self.times[index - 1] < .25:
            move = MOVEMENTS[self.notes[index - 1]["action"]]
            verb = "落步" if move.kind == "step" else "击打"
            label = f"{verb}  /  {move.label}"
        elif index < len(self.notes):
            label = "准备  /  " + MOVEMENTS[self.notes[index]["action"]].label
        else:
            label = "收势  /  放松"
        text(im,(640,650),label,26,WHITE,True,"center")
        hint = "空中方块出拳   /   地面脚印侧步" if self.has_steps else "方块到线时出拳"
        text(im,(640,692),hint,15,DUSK,False,"center")
        elapsed=int(t)
        text(im,(42,104),f"{elapsed//60:02d}:{elapsed%60:02d}",25,WHITE,True)
        text(im,(1234,106),f"{index:02d}  /  {len(self.notes):02d}",22,DUSK,True,"right")
        d.line((0,717,1280*t/self.duration,717),fill=self.colors[0],width=4)
        return im if self.size==im.size else im.resize(self.size,Image.Resampling.BILINEAR)
