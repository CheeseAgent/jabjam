"""Seekable visual cues on the song clock. The counter follows the authored workout."""
from bisect import bisect_right
from functools import lru_cache
from math import cos, floor, pi
import re

from PIL import Image, ImageDraw

from lettering import font, text
from lyrics import visible_text
from movements import MOVEMENTS, LEFT

MINT = (117, 244, 213)
GOLD = (255, 206, 128)
WHITE = (247, 250, 252)
INK = (17, 28, 43)


@lru_cache(maxsize=64)
def caption_card(value):
    """Wrap Latin words and CJK characters within two lines on the 720p canvas."""
    face = font(27, True)
    rows = [""]
    for token in re.findall(r"[A-Za-z0-9’'-]+|\s+|.", value[:360]):
        parts = [token] if face.getlength(token) <= 700 else token
        for part in parts:
            if face.getlength(rows[-1] + part) > 700:
                if len(rows) == 2:
                    last = rows[-1].rstrip()
                    while last and face.getlength(last + "…") > 700:
                        last = last[:-1]
                    rows[-1] = last + "…"
                    break
                rows.append("")
            if rows[-1] or not part.isspace():
                rows[-1] += part
        else:
            continue
        break
    width = max(50, round(max(face.getlength(row.rstrip()) for row in rows)) + 46)
    card = Image.new("RGBA", (width, 14 + 31 * len(rows)))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 0, width-1, card.height-1), radius=14, fill=(*INK, 221))
    for index, row in enumerate(rows):
        d.text((width//2, 8 + 31 * index), row.rstrip(), font=face, fill=WHITE, anchor="mt")
    return card


class WorkoutHud:
    def __init__(self, picture, notes, times, beats, bpm, lyric_lines):
        self.notes, self.times = notes, times
        self.beats = beats
        self.period = 60 / bpm
        self.lyric_style = picture.get("lyrics", "off")
        self.words = [visible_text(row["text"]) for row in lyric_lines]
        self.starts = [row["time"] for row in lyric_lines]
        self.side = picture.get("combo_side", "auto")
        if self.side == "auto":
            coach = picture.get("coach", {})
            self.side = "right" if coach.get("enabled") and coach.get("side") == "left" else "left"
        self.style = picture.get("combo_style", "arcade")
        self.counts = []
        for i, at in enumerate(times):
            reset = i == 0 or at - times[i-1] >= self.reset_after(times[i-1])
            self.counts.append(1 if reset else self.counts[-1] + 1)

    def beat(self, t):
        """Return local beat length and phase; authored charts can supply just a BPM."""
        i = bisect_right(self.beats, t) - 1
        if len(self.beats) < 2:
            return self.period, (t / self.period) % 1
        i = max(0, min(i, len(self.beats)-2))
        period = self.beats[i+1] - self.beats[i]
        return period, ((t - self.beats[i]) / period) % 1

    def reset_after(self, t):
        return max(2.0, 4 * self.beat(t)[0])

    def draw(self, im, t, index):
        if self.lyric_style != "off":
            self.draw_lyrics(im, t)
        if self.side != "off" and index and self.counts[index-1] >= 2:
            age = t - self.times[index-1]
            if age < self.reset_after(self.times[index-1]):
                self.draw_counter(im, self.counts[index-1], age)
        if index < len(self.notes) and self.notes[index].get("combo_step") == 1:
            if not index or t - self.times[index-1] >= .25:
                self.draw_callout(im, t, index)

    def draw_callout(self, im, t, index):
        note = self.notes[index]
        remaining = (note["time"] - t) / self.beat(note["time"])[0]
        if remaining > 2 and not index:
            return
        countdown = remaining <= 2
        if countdown:
            lead = "左起" if MOVEMENTS[note["action"]].side == LEFT else "右起"
            title = f"下一组  ·  {lead}  ·  {note['combo_name']}"
        else:
            title = "回架"
        width = min(630, round(font(24, True).getlength(title)) + (82 if countdown else 42))
        left = 640 - width//2
        d = ImageDraw.Draw(im, "RGBA")
        d.rounded_rectangle((left, 572, left + width, 615), radius=17, fill=(*INK, 232))
        text(im, (left+21, 581), title, 24, WHITE, True)
        if countdown:
            for n in range(2):
                x = left + width - 40 + n*14
                d.ellipse((x, 590, x+8, 598), fill=MINT if n == 0 or remaining <= 1 else (85, 103, 122))

    def draw_lyrics(self, im, t):
        i = bisect_right(self.starts, t) - 1
        if i < 0 or not self.words[i]:
            return
        start = self.starts[i]
        end = min(start + 7, self.starts[i+1] if i+1 < len(self.starts) else start+7)
        if t >= end:
            return
        age = t - start
        ramp = min(1., age/.16, (end-t)/.20)
        card = caption_card(self.words[i])
        y = 132
        if self.lyric_style == "rise":
            y += round(17 * max(0., 1-age/.32)**2)
        x = (im.width - card.width)//2
        mask = card.getchannel("A")
        if ramp < 1:
            mask = mask.point(lambda a: round(a*ramp))
        im.paste(card, (x, y), mask)
        if self.lyric_style == "rise":
            ImageDraw.Draw(im, "RGBA").rounded_rectangle((x+7, y+10, x+10, y+card.height-11),
                                                         radius=2, fill=(*MINT, round(235*ramp)))
        elif self.lyric_style == "pulse":
            pulse = (1 + cos(2*pi*self.beat(t)[1])) / 2
            d = ImageDraw.Draw(im, "RGBA")
            d.rounded_rectangle((x, y, x+card.width-1, y+card.height-1), radius=14,
                                outline=(*GOLD, round(ramp*(65+160*pulse))), width=2)
            half = round((card.width-30) * (.16+.32*pulse))
            d.rounded_rectangle((640-half, y+card.height-4, 640+half, y+card.height-2),
                                radius=1, fill=(*GOLD, round(ramp*(115+140*pulse))))

    def draw_counter(self, im, count, age):
        cx = 122 if self.side == "left" else 1158
        cy = 377
        d = ImageDraw.Draw(im, "RGBA")
        accent = GOLD if count % 10 == 0 else MINT
        pop = max(0., 1-age/.24)
        if self.style == "minimal":
            d.rounded_rectangle((cx-91, cy-22, cx+91, cy+23), radius=13, fill=(*INK, 220))
            text(im, (cx, cy-11), f"{count} COMBO", 26, WHITE, True, "center")
            return
        if self.style == "ring":
            d.ellipse((cx-44, cy-44, cx+44, cy+44), fill=(*INK, 232), outline=(91, 108, 127), width=3)
            d.arc((cx-42, cy-42, cx+42, cy+42), -90, -90+36*((count-1)%10+1), fill=accent, width=5)
            text(im, (cx, cy-21), str(count), 29, WHITE, True, "center")
            text(im, (cx, cy+13), "COMBO", 12, accent, True, "center")
            return
        d.polygon([(cx-74,cy-32),(cx+85,cy-32),(cx+72,cy+33),(cx-88,cy+33)], fill=(*INK, 232))
        size = 32 + floor(8*pop)
        text(im, (cx+2,cy-24), str(count), size, (62, 124, 140), True, "center")
        text(im, (cx,cy-26), str(count), size, WHITE, True, "center")
        text(im, (cx,cy+16), "COMBO", 15, accent, True, "center")
        d.line((cx-83,cy+27,cx-65,cy-24), fill=accent, width=3)
