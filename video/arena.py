"""First-person rhythm arena, drawn one frame at a time on a 1280x720 canvas."""
from bisect import bisect_left, bisect_right
from math import ceil, cos, floor, pi, sin
from pathlib import Path
from random import Random
from PIL import Image, ImageColor, ImageDraw, ImageOps

from course import ART_HORIZONS, fixed_scene
from audio_wave import draw_wave
from background_video import STAGE_SIZE, STAGE_TOP
from movements import MOVEMENTS, LEFT
from cue_art import punch_icon, foot_pad, step_landing, duck_icon
from coach_avatar import CoachLayer
from lettering import font, text
from opening_title import OpeningTitle, TITLE_SECONDS
from workout_hud import WorkoutHud, combo_caption

INK = (11, 21, 36)
WHITE = (240, 248, 252)
DUSK = (135, 158, 181)
HORIZON = 210
HIT_Y = 510
SHATTER = 0.58
PYLON_DEPTHS = (.14, .20, .29, .42, .61, .88, 1.27)


def blend(a, b, p):
    return tuple(round(x + (y - x) * p) for x, y in zip(a, b))


class Arena:
    def __init__(self, title, picture, notes, duration, *, beats=(), bpm=120, lyric_lines=(), envelope=b""):
        # Snap the presentation only. The chart and audio keep their source timestamps.
        fps = picture.get("fps", 24)
        last_frame = ceil(duration * fps) - 1
        self.times = [min(last_frame, floor(note["time"] * fps + .5)) / fps for note in notes]
        self.notes = [dict(note, time=t) for note, t in zip(notes, self.times)]
        self.duration = duration
        self.lead = picture.get("approach_seconds", 2)
        self.size = tuple(picture.get("size", [1280, 720]))
        self.scene = fixed_scene(picture.get("scene", "neon"))
        self.has_video = picture.get("background_video", "off") != "off"
        self.neon = self.scene == "neon" and not self.has_video
        self.horizon = HORIZON if self.has_video else ART_HORIZONS.get(self.scene, HORIZON)
        title_style = picture.get("title_style", "off")
        self.opening = OpeningTitle(title, title_style) if title_style != "off" else None
        self.wave_style = picture.get("wave_style", "off")
        self.envelope = envelope
        if self.wave_style != "off" and not envelope:
            raise ValueError("A song envelope is required for the waveform")
        self.colors = [ImageColor.getrgb(picture.get("left_color", "#63edce")),
                       ImageColor.getrgb(picture.get("right_color", "#ff916d"))]
        self.halo = Image.new("L", (96, 96))
        glow = ImageDraw.Draw(self.halo)
        for radius in range(47, 0, -1):
            glow.ellipse((48-radius, 48-radius, 48+radius, 48+radius),
                         fill=round(155*(1-radius/48)**1.4))
        self.has_steps = any(MOVEMENTS[note["action"]].kind in ("step", "advance", "retreat") for note in notes)
        self.base = self.background(title)
        self.coach = CoachLayer(self.notes, picture.get("coach", {}))
        self.hud = WorkoutHud(picture, self.notes, self.times, beats, bpm, lyric_lines)

    def skyline(self, im, d):
        # All skyline lights and the graduated solar disc are painted once per course.
        dusk = (87, 66, 104)
        for y in range(77, HORIZON + 1):
            d.line((0, y, 1280, y), fill=blend((17, 23, 46), dusk, ((y-77)/(HORIZON-77))**1.6))
        rng = Random(41)
        for _ in range(100):
            x, y = rng.randrange(1280), rng.randrange(80, HORIZON-16)
            d.point((x, y), fill=(89, 99, 132))
        glow = self.halo.resize((290, 158))
        im.paste((178, 123, 116), (495, 105, 785, 263), glow)
        # Narrow bands break up the lower half of the disc at the horizon.
        radius, center_y = 49, HORIZON - 28
        for dy in range(-radius, HORIZON-center_y+1):
            if dy > 0 and dy % 8 < 1 + dy//13:
                continue
            half = (radius**2 - dy**2)**.5
            tint = blend((245, 201, 158), (205, 111, 134), (dy+radius)/(2*radius))
            d.line((640-half, center_y+dy, 640+half, center_y+dy), fill=tint)
        for base, facade, lights in [
            (HORIZON-2, (61, 57, 84), (105, 91, 108)),
            (HORIZON+2, (32, 40, 62), (82, 105, 121)),
        ]:
            x = -7
            while x < 1280:
                width = rng.randrange(9, 32)
                height = rng.randrange(7, 30) + round(abs(x-640)*.025)
                top = base-height
                d.rectangle((x, top, x+width, base), fill=facade)
                if rng.randrange(4) == 0:
                    d.rectangle((x+3, top-4, x+width//2, top), fill=facade)
                for row in range(top+4, base-2, 5):
                    if rng.randrange(3) == 0:
                        d.line((x+3, row, x+width//2, row), fill=lights)
                x += width + rng.randrange(2, 7)

    def pylons(self, d, sign, color):
        # Repeat a bevelled steel section in perspective, from back to front.
        for z in PYLON_DEPTHS:
            def project(dx, dy):
                return (640 + sign*dx*z, HORIZON + dy*z)

            rim = blend((35, 42, 65), color, .20*z)
            beam = [(765,-183), (598,-153), (522,-103), (522,63), (610,140),
                    (654,149), (562,51), (562,-92), (611,-129), (765,-155)]
            d.polygon([project(x, y) for x, y in beam], fill=(26, 35, 53))
            d.line([project(x, y) for x, y in beam[:5]], fill=rim, width=max(1, round(3*z)))
            d.line([project(736,-166), project(605,-141), project(551,-106)],
                   fill=blend(INK, color, .46), width=max(1, round(5*z)))
            d.line([project(540,26), project(540,57), project(598,111)],
                   fill=blend(INK, color, .38), width=max(1, round(4*z)))

    def runway_lights(self, d, t, index):
        # Dashes advance outside the cue lanes. Only the rail on the struck side brightens.
        hit_side, heat = 0, 0
        if index:
            age = t - self.times[index-1]
            hit_side = MOVEMENTS[self.notes[index-1]["action"]].side
            heat = max(0, 1-age/SHATTER)**2
        for side, color in zip((-1, 1), self.colors):
            accent = .48 * heat if side == hit_side else 0
            for i in range(10):
                phase = (i + t*1.8) % 10 / 10
                depth = phase*phase
                tail = max(0, phase-.034)**2
                light = blend((47, 58, 81), color, .12 + (.30+accent)*phase)
                for edge in (565, 900):
                    d.line((640+side*edge*tail, HORIZON+422*tail,
                            640+side*edge*depth, HORIZON+422*depth),
                           fill=light, width=max(1, round(5*depth)))

    def illustrated_stage(self, im):
        with Image.open(Path(__file__).resolve().parents[1] / "assets/arenas" / (self.scene + ".jpg")) as source:
            stage = ImageOps.fit(source, STAGE_SIZE, method=Image.Resampling.LANCZOS)
        im.paste(stage, (0, STAGE_TOP))
        self.stage_guides(im)

    def stage_guides(self, im):
        # Keep the score and two lanes readable over detailed or moving artwork.
        overlay = ImageDraw.Draw(im, "RGBA")
        shade = 65 if self.has_video else 0
        for y in range(77, 157):
            alpha = shade + round(155 * (1 - (y - 77) / 80))
            overlay.line((0, y, 1279, y), fill=(*INK, alpha))
        for sign, color in zip((-1, 1), self.colors):
            overlay.polygon([(640, self.horizon), (640+sign*505, 632), (640+sign*147, 632)],
                            fill=(*INK, 105 if self.has_video else 53))
            overlay.line((640, self.horizon, 640+sign*505, 632), fill=(*color, 125), width=2)

    def procedural_stage(self, im, d):
        for y in range(77, 632):
            factor = max(0, 1 - abs(y-HORIZON)/360)
            d.line((0, y, 1280, y), fill=blend((11, 20, 34), (34, 58, 79), factor))
        if self.neon:
            self.skyline(im, d)
        # Opposing banks of light and receding trusses frame the vanishing point.
        for sign, color in zip((-1, 1), self.colors):
            if not self.neon:
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
        if self.neon:
            for side, color in zip((-1, 1), self.colors):
                self.pylons(d, side, color)

    def background(self, title):
        im = Image.new("RGBA", (1280, 720), (*INK, 65)) if self.has_video else Image.new("RGB", (1280, 720), INK)
        d = ImageDraw.Draw(im)
        if self.has_video:
            self.stage_guides(im)
        elif self.scene in ART_HORIZONS:
            self.illustrated_stage(im)
        else:
            self.procedural_stage(im, d)
        d.line((0,HIT_Y,1280,HIT_Y),fill=(135,159,176),width=2)
        for side, color in zip((-1,1), self.colors):
            x = 640+side*255
            for dx, dy in ((-1,-1),(1,-1),(-1,1),(1,1)):
                cx, cy = x+dx*85, HIT_Y+dy*65
                d.line([(cx-dx*20,cy),(cx,cy),(cx,cy-dy*16)], fill=blend(INK,color,.85),width=3)
            d.ellipse((x-91,HIT_Y+53,x+91,HIT_Y+69),outline=blend(INK,color,.55),width=2)
        if self.has_video:
            # Paste moving pixels through this cached mask; solid hit guides remain opaque.
            stage = (0, STAGE_TOP, STAGE_SIZE[0], STAGE_TOP + STAGE_SIZE[1])
            self.video_mask = ImageOps.invert(im.getchannel("A").crop(stage))
            im = im.convert("RGB")
            d = ImageDraw.Draw(im)
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

    def position(self, side, u):
        p=.25*u+.75*u*u
        return 640+side*(23+232*p), self.horizon+(HIT_Y-self.horizon)*p, 11+58*p

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
        if move.kind == "duck":
            duck_icon(d,x,y-r*.06,r*.94,color)
        else:
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

    def frame(self, t, *, background_frame=None):
        im=self.base.copy()
        if self.has_video:
            if background_frame is None:
                raise ValueError("A decoded background frame is required for this course")
            im.paste(background_frame, (0, STAGE_TOP), self.video_mask)
        d=ImageDraw.Draw(im)
        index=bisect_right(self.times,t)
        end=bisect_right(self.times,t+self.lead)
        if self.neon:
            self.runway_lights(d, t, index)
        if self.wave_style != "off":
            draw_wave(im, self.wave_style, self.envelope, t, self.colors)
        opening = self.opening is not None and 0 <= t < TITLE_SECONDS
        if opening:
            self.opening.draw(im, t)
        for j in range(end - 1, index - 1, -1):
            move = MOVEMENTS[self.notes[j]["action"]]
            color = self.colors[0 if move.side == LEFT else 1]
            progress = 1 - (self.times[j] - t) / self.lead
            if move.kind in ("step", "advance", "retreat"):
                x, y, radius = self.position(move.side, progress)
                foot_pad(d, x, y + radius, radius, move, color)
            else:
                self.block(d, move, progress, color)
        for j in range(bisect_left(self.times, t - SHATTER), index):
            move = MOVEMENTS[self.notes[j]["action"]]
            color = self.colors[0 if move.side == LEFT else 1]
            age = t - self.times[j]
            if move.kind in ("step", "advance", "retreat"):
                x, y, radius = self.position(move.side, 1)
                step_landing(d, x, y + radius, radius, move, color, age / SHATTER)
            else:
                self.burst(im, d, move.side, move.kind == "hook", age, color)
        self.coach.draw(im, t)
        im.paste(self.base.crop((0,632,1280,720)),(0,632))
        if not opening and t < self.times[0] - self.lead:
            if self.has_video or self.scene in ART_HORIZONS:
                ImageDraw.Draw(im, "RGBA").rounded_rectangle((385, 273, 895, 392), radius=16, fill=(*INK, 192))
            text(im,(640,295),"跟随拍点 · 准备开始",36,WHITE,True,"center")
            text(im,(640,352),"直箭头打直拳   /   横弯打摆拳   /   上挑打上勾拳",20,DUSK,False,"center")
        cue = None
        just_hit = index > 0 and t - self.times[index - 1] < .25
        if just_hit:
            cue = self.notes[index - 1]
            move = MOVEMENTS[cue["action"]]
            verb = "落步" if move.kind in ("step", "advance", "retreat") else ("闪躲" if move.kind == "duck" else "击打")
            label = f"{verb}  /  {move.label}"
        elif index < len(self.notes):
            cue = self.notes[index]
            label = "准备  /  " + MOVEMENTS[cue["action"]].label
        else:
            label = "收势  /  放松"
        text(im,(640,650),label,26,WHITE,True,"center")
        hint = "空中方块出拳或闪躲   /   地面脚印完成侧步、前后跟步" if self.has_steps else "方块到线时出拳或下潜"
        text(im,(640,692),hint,15,DUSK,False,"center")
        if cue and cue.get("combo_name") and (just_hit or cue["combo_step"] > 1):
            caption = f"组合拳  /  {combo_caption(cue)}     {cue['combo_step']}/{cue['combo_total']}"
            text(im,(640,107),caption,25,WHITE,True,"center")
        self.hud.draw(im, t, index)
        elapsed=int(t)
        text(im,(42,104),f"{elapsed//60:02d}:{elapsed%60:02d}",25,WHITE,True)
        count_color = WHITE if self.has_video or self.scene in ART_HORIZONS else DUSK
        text(im,(1234,106),f"{index:02d}  /  {len(self.notes):02d}",22,count_color,True,"right")
        d.line((0,717,1280*t/self.duration,717),fill=self.colors[0],width=4)
        return im if self.size==im.size else im.resize(self.size,Image.Resampling.BILINEAR)
