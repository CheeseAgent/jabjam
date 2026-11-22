"""Animated song title plates. All animation is on the original song clock."""
from PIL import Image, ImageDraw

from lettering import font

TITLE_SECONDS = 3.0
CREAM = (255, 247, 220)
MINT = (128, 242, 208)
CORAL = (255, 127, 105)
NAVY = (17, 29, 46)


def fitted_lines(title, width, height):
    """Prefer a large single line, then wrap at spaces or CJK character boundaries."""
    for size in (56, 48, 40, 34, 29, 25, 21, 18, 15):
        face = font(size, True)
        rows = []
        rest = title
        while rest:
            low, high = 1, len(rest)
            while low < high:
                mid = (low + high + 1) // 2
                if face.getlength(rest[:mid]) <= width:
                    low = mid
                else:
                    high = mid - 1
            cut = low
            if cut < len(rest) and not rest[cut].isspace():
                space = rest.rfind(" ", 0, cut)
                if space >= cut * .6:
                    cut = space
            rows.append(rest[:cut].rstrip())
            rest = rest[cut:].lstrip()
        if len(rows) * (size + 5) <= height:
            return face, rows
    return face, rows


class OpeningTitle:
    def __init__(self, title, style):
        self.style = style
        self.card = Image.new("RGBA", (704, 134))
        d = ImageDraw.Draw(self.card)
        left, right, ink = 28, 676, CREAM
        if style == "cinema":
            # The translucent ends keep the course's own scenery visible.
            for x in range(704):
                opacity = min(1, (x+1)/74, (704-x)/74)
                d.line((x, 5, x, 129), fill=(14, 25, 42, round(216*opacity)))
            for y in (9, 125):
                d.line((83, y, 343, y), fill=(231, 197, 128, 190))
                d.line((361, y, 621, y), fill=(231, 197, 128, 190))
                d.polygon([(348,y), (352,y-3), (356,y), (352,y+3)], fill=CREAM)
        elif style == "arcade":
            d.polygon([(46,13), (701,13), (662,132), (7,132)], fill=(*CORAL, 230))
            d.polygon([(40,3), (693,3), (654,121), (1,121)], fill=(*NAVY, 248))
            d.line((42,5,688,5), fill=MINT, width=4)
            for x in (37, 48, 59):
                d.polygon([(x,35),(x+5,35),(x-13,89),(x-18,89)], fill=MINT)
            left, right = 82, 644
        else:  # vinyl: a die-cut record sleeve and its centre label
            d.rounded_rectangle((4,7,700,132), radius=18, fill=(25, 21, 36, 190))
            d.rounded_rectangle((1,2,697,126), radius=18, fill=(246, 224, 188, 250))
            d.ellipse((15,9,125,119), fill=(39, 43, 57))
            for radius in (49, 43, 36):
                d.arc((70-radius,64-radius,70+radius,64+radius), 110, 286, fill=(116, 133, 138), width=2)
            d.ellipse((49,43,91,85), fill=CORAL)
            d.ellipse((66,60,74,68), fill=CREAM)
            d.line((140,17,140,111), fill=(165, 132, 107), width=2)
            left, right, ink = 161, 672, NAVY
        face, rows = fitted_lines(title, right-left, 105)
        step = face.size + 5
        y = 64 - (len(rows)-1)*step/2
        for row in rows:
            anchor = "lm" if style == "vinyl" else "mm"
            x = left if style == "vinyl" else (left+right)/2
            if style == "arcade":
                d.text((x+2,y+3), row, font=face, fill=(70, 128, 141), anchor=anchor)
            d.text((x,y), row, font=face, fill=ink, anchor=anchor)
            y += step
        self.alpha = self.card.getchannel("A")

    def draw(self, im, t):
        if not 0 <= t < TITLE_SECONDS:
            return
        entry = max(0, 1 - t/.32) ** 2
        opacity = min(1 - .36*entry, (TITLE_SECONDS-t)/.42)
        dx = {"cinema": 0, "arcade": -48, "vinyl": 32}[self.style]
        dy = 9 if self.style == "cinema" else 0
        mask = self.alpha if opacity >= 1 else self.alpha.point(lambda a: round(a*opacity))
        im.paste(self.card, (round(288 + dx*entry), round(251 + dy*entry)), mask)
