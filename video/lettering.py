"""Cached CJK type shared by the arena and workout overlays."""
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont


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


def text(im, xy, value, size, color=(240, 248, 252), bold=False, align="left"):
    label, mask = lettering(value, size, color, bold)
    x, y = xy
    if align == "center":
        x -= label.width / 2
    elif align == "right":
        x -= label.width
    im.paste(label, (round(x), round(y)), mask)
