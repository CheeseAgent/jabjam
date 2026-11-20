"""Rebuild the cropped RGBA textures from the attached cutout. Offline art tools: Pillow, numpy, scipy."""
import argparse
from hashlib import sha256
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import binary_dilation, distance_transform_edt, label
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve

SOURCE = Path(__file__).with_name("milktea.png")
OUTPUT = SOURCE.parents[2] / "assets/coaches/milktea/rig"
DIGEST = "fc84c4fafdd20a460549b6382713a9699897d3c64d363ab2b19be1f59b4db4ee"
# Source coordinates are half-open. Keep padding stable: rig pivots use these crop origins.
BOXES = {
    "head": (78, 64, 498, 431), "tuft": (642, 283, 821, 398),
    "ear_left": (522, 30, 708, 296), "ear_right": (755, 32, 941, 300),
    "ear_back_left": (980, 68, 1140, 315), "ear_back_right": (1193, 68, 1348, 314),
    "torso": (165, 448, 398, 638), "pelvis": (131, 642, 429, 790),
    "upper_arm_left": (490, 419, 610, 546), "upper_arm_right": (1056, 420, 1180, 547),
    "lower_arm_left": (479, 545, 574, 677), "lower_arm_right": (1099, 546, 1191, 677),
    "glove_left": (465, 637, 614, 795), "glove_right": (1052, 637, 1202, 795),
    "thigh_left": (680, 435, 803, 575), "thigh_right": (857, 435, 978, 575),
    "shin_left": (681, 573, 791, 705), "shin_right": (871, 574, 980, 705),
    "foot_left": (644, 701, 795, 793), "foot_right": (868, 701, 1018, 793),
    "tail": (1248, 566, 1374, 691),
}
# Elliptical repair regions (cx, cy, rx, ry) cover the original dark cut ends only.
CAPS = {
    "ear_left": [(655, 280, 55, 21)], "ear_right": [(801, 280, 58, 23)],
    "ear_back_left": [(1031, 303, 42, 18)], "ear_back_right": [(1295, 303, 40, 18)],
    "tuft": [(732, 388, 91, 25)],
    "upper_arm_left": [(578, 441, 27, 18), (529, 530, 36, 20)],
    "upper_arm_right": [(1091, 442, 28, 18), (1138, 531, 36, 20)],
    "lower_arm_left": [(523, 557, 37, 17)], "lower_arm_right": [(1149, 558, 38, 18)],
    "thigh_left": [(739, 449, 52, 16), (737, 561, 48, 21)],
    "thigh_right": [(914, 449, 51, 16), (925, 561, 46, 21)],
    "shin_left": [(738, 584, 49, 19), (739, 693, 44, 16)],
    "shin_right": [(924, 585, 49, 19), (926, 693, 44, 16)],
    "foot_left": [(744, 710, 41, 12)], "foot_right": [(921, 710, 41, 12)],
}
CUFF = [(478, 690), (488, 673), (491, 661), (497, 652), (504, 647),
        (514, 644), (527, 642), (541, 642), (553, 643), (561, 646),
        (569, 652), (575, 666), (579, 677), (601, 689)]


def isolate(im):
    """Keep main connected silhouette, including its antialias fringe, discard sheet specks."""
    a = np.array(im)
    components, _ = label(a[:, :, 3] > 45)
    main = 1 + np.argmax(np.bincount(components.ravel())[1:])
    distance = distance_transform_edt(components != main)
    a[(distance > 1.5) | (a[:, :, 3] < 5)] = 0
    return Image.fromarray(a)


def repair_caps(im, name):
    pixels = np.array(im)
    x0, y0, _, _ = BOXES[name]
    y, x = np.indices(pixels.shape[:2])
    for cx, cy, rx, ry in CAPS.get(name, []):
        radius = ((x+x0-cx)/rx)**2 + ((y+y0-cy)/ry)**2
        # Extend adjacent *interior fur colour* across the dark end. Preserve the outer sides.
        # Use the median intact interior, not the nearest antialiased outline pixel.
        interior = (radius < 2) & (pixels[:, :, 1] > 200) & (pixels[:, :, 3] > 248)
        color = np.median(pixels[interior, :3], axis=0)
        blend = np.clip((1.05-radius)*5, 0, 1)[..., None]
        pixels[:, :, :3] = pixels[:, :, :3]*(1-blend) + color*blend
    pixels[pixels[:, :, 3] == 0] = 0
    return Image.fromarray(pixels)


def wrist(sheet, name):
    left = name.endswith("left")
    box = BOXES[name]
    im = sheet.crop(box)
    if name.startswith("glove"):
        pts = CUFF if left else sorted((1669-x, y) for x,y in CUFF)
        # Trace the cuff's upper rim. Supersampling preserves its curved silhouette.
        mask = Image.new("L", (im.width*4, im.height*4))
        polygon = [(box[0]-1, pts[0][1]), *pts, (box[2]+1, pts[-1][1]),
                   (box[2]+1, box[3]), (box[0]-1, box[3])]
        ImageDraw.Draw(mask).polygon([((x-box[0])*4, (y-box[1])*4) for x,y in polygon], fill=255)
        a = np.asarray(im.getchannel("A"), dtype=float) * np.asarray(mask.resize(im.size, Image.Resampling.LANCZOS))/255
        im.putalpha(Image.fromarray(a.astype("uint8")))
    else:
        # The hand behind the cuff is absent. Extend the last intact fur scanline
        # into a rounded wrist plug; it stays inside the cuff throughout rotation.
        a = np.array(im)
        row = 636 - box[1]
        for y in range(row+1, im.height):
            depth = (y-row)/(im.height-row)
            shrink = .22*depth**2
            indices = np.rint((np.arange(im.width)-im.width/2)/(1-shrink)+im.width/2).astype(int)
            a[y] = a[row, np.clip(indices, 0, im.width-1)]
            a[y, (indices < 0) | (indices >= im.width)] = 0
        im = Image.fromarray(a)
    return isolate(im)


def faces(head, sheet):
    # Reconstruct only the fur underneath removable features. A harmonic fill
    # extends colour from their intact boundaries, preserving cheeks and band.
    base = np.array(head)
    x0, y0, _, _ = BOXES["head"]
    mask = Image.new("1", head.size)
    draw = ImageDraw.Draw(mask)
    regions = [
        [(178,214),(182,204),(202,196),(221,196),(238,212),(232,219),(211,211),(201,212),(180,221)],
        [(339,214),(350,201),(366,195),(380,198),(398,213),(392,220),(373,211),(358,211),(343,221)],
        [(161,280),(165,256),(177,239),(197,232),(218,233),(239,248),(249,270),(248,296),(238,312),(225,319),(193,318),(174,309),(165,296)],
        [(329,278),(334,254),(350,236),(369,230),(392,234),(408,247),(417,270),(417,294),(405,310),(389,318),(360,319),(339,308),(331,296)],
        [(250,310),(267,307),(289,314),(309,308),(327,309),(327,339),(318,361),(305,375),(287,380),(271,375),(259,361),(252,339)],
    ]
    for region in regions:
        draw.polygon([(x-x0,y-y0) for x,y in region], fill=1)
    hole = binary_dilation(np.asarray(mask), iterations=2)
    yy, xx = np.where(hole)
    index = np.full(hole.shape, -1)
    index[hole] = np.arange(len(yy))
    ids = np.arange(len(yy))
    rows, cols, values = [ids], [ids], [np.full(len(ids), 4)]
    rhs = np.zeros((len(ids),3))
    for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
        adjacent = index[yy+dy,xx+dx]
        inside = adjacent >= 0
        rows.append(ids[inside])
        cols.append(adjacent[inside])
        values.append(np.full(inside.sum(), -1))
        rhs[~inside] += base[yy[~inside]+dy, xx[~inside]+dx, :3]
    matrix = coo_matrix((np.concatenate(values), (np.concatenate(rows), np.concatenate(cols)))).tocsc()
    # Feather into intact fur around the outside of the repaired area.
    mask = Image.fromarray(binary_dilation(hole, iterations=5).astype("uint8")*255)
    original = base.copy()
    original[:, :, 3] = np.minimum(base[:, :, 3], np.asarray(mask.filter(ImageFilter.GaussianBlur(2))))
    original[original[:, :, 3] == 0] = 0
    base[hole, :3] = np.rint(spsolve(matrix, rhs)).astype("uint8")
    yield "head", Image.fromarray(base)
    yield "face_open", Image.fromarray(original)
    # Alternative expressions from the modular strip; same head pivot in all poses.
    for name, eyes, mouth, brows in [
        ("happy", ((506,843,599,890),(627,844,721,893)), (79,990,166,1076), None),
        ("focus", ((983,838,1062,917),(1088,837,1168,917)), (222,1014,309,1057), None),
        ("sparkle", ((285,827,368,914),(387,827,468,915)), (79,990,166,1076),
         ((57,940,120,972),(166,940,229,972))),
    ]:
        out = Image.new("RGBA", head.size)
        features = [(eyes[0], (205,278)), (eyes[1], (374,278)), (mouth, (290,343))]
        if brows:
            features += [(brows[0], (207,208)),(brows[1], (368,208))]
        for crop,(cx,cy) in features:
            part = isolate(sheet.crop(crop))
            if crop == mouth:
                part.thumbnail((73,69), Image.Resampling.LANCZOS)
            out.alpha_composite(part, (cx-x0-part.width//2, cy-y0-part.height//2))
        yield "face_"+name, out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    dest = parser.parse_args().out
    if sha256(SOURCE.read_bytes()).hexdigest() != DIGEST:
        raise ValueError("Unexpected source sheet. Recalibrate crop coordinates before rebuilding.")
    dest.mkdir(parents=True, exist_ok=True)
    with Image.open(SOURCE) as sheet:
        for name, box in BOXES.items():
            if name.startswith(("glove", "lower_arm")):
                part = wrist(sheet, name)
            else:
                part = isolate(sheet.crop(box))
            if name == "head":
                for key, face in faces(part, sheet):
                    face.save(dest / (key+".png"))
            else:
                if name.startswith(("upper_arm", "lower_arm", "thigh", "shin", "foot")):
                    # A separate ink silhouette under both rotating segments keeps
                    # the outer elbow/ankle line without drawing a line across the joint.
                    ink = Image.new("RGBA", part.size, (64, 37, 24, 0))
                    alpha = part.getchannel("A").filter(ImageFilter.MaxFilter(7))
                    zone = Image.new("L", part.size)
                    x0, y0, _, _ = box
                    for cx, cy, rx, ry in CAPS[name]:
                        ImageDraw.Draw(zone).ellipse((cx-x0-rx-3, cy-y0-ry-3,
                                                      cx-x0+rx+3, cy-y0+ry+3), fill=255)
                    ink.putalpha(Image.fromarray(np.minimum(np.asarray(alpha),np.asarray(zone))))
                    ink.save(dest / ("ink_"+name+".png"))
                repair_caps(part, name).save(dest / (name+".png"))


if __name__ == "__main__":
    main()
