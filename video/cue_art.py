"""Draw action symbols in viewer coordinates. Timing and scoring do not belong here."""
from movements import LEFT

# Front-face shapes in units of one tile radius.
JAB = [(-.22, .70), (.22, .70), (.22, -.05), (.57, -.05),
       (0, -.78), (-.57, -.05), (-.22, -.05)]
# Left swing points right. Its mirror on the right lane points left.
LEFT_HOOK = [(-.65, .65), (-.65, .16), (-.42, -.18), (-.02, -.26),
             (.10, -.26), (.10, -.66), (.77, -.10), (.10, .49),
             (.10, .10), (-.10, .10), (-.26, .20), (-.26, .65)]
# Scooping J: a low curved pocket and an upward arrowhead at the inside shoulder.
LEFT_UPPERCUT = [(-.78, .08), (-.69, .43), (-.46, .66), (-.13, .73),
                 (.19, .62), (.42, .39), (.50, .04), (.50, -.22),
                 (.80, -.22), (.32, -.84), (-.16, -.22), (.13, -.22),
                 (.13, .06), (.07, .25), (-.11, .37), (-.32, .36),
                 (-.49, .24), (-.55, .06)]
PUNCH_SHAPES = {"jab": JAB, "hook": LEFT_HOOK, "uppercut": LEFT_UPPERCUT}


def punch_icon(draw, x, y, radius, move, color):
    mirror = 1 if move.side == LEFT else -1
    points = [(x + mirror * dx * radius, y + dy * radius)
              for dx, dy in PUNCH_SHAPES[move.kind]]
    draw.polygon(points, fill=color)


def foot_pad(draw, x, y, radius, move, color):
    """A low, flat landing pad with a split sole and an outward direction arrow."""
    width = radius * 1.5
    height = radius * .54
    ink = (13, 31, 44)
    draw.polygon([(x-width, y), (x-width*.7, y-height), (x+width*.7, y-height),
                  (x+width, y), (x+width*.7, y+height), (x-width*.7, y+height)],
                 fill=color, outline=(206, 235, 230), width=max(1, round(radius*.04)))
    # On either lane the toe is above the heel; the chevron points outwards.
    sole_x = x - move.side * radius * .38
    draw.ellipse((sole_x-radius*.20, y-height*.84, sole_x+radius*.22, y+height*.13), fill=ink)
    draw.ellipse((sole_x-radius*.16, y+height*.28, sole_x+radius*.14, y+height*.76), fill=ink)
    if move.kind in ("advance", "retreat"):
        direction = -1 if move.kind == "advance" else 1
        arrow = [(-.34, -.06), (-.34, .25), (0, .25), (0, .70), (.65, 0), (0, -.70), (0, -.25), (-.34, -.25)]
        draw.polygon([(x+dx*radius, y+direction*dy*height) for dx, dy in arrow], fill=ink)
    else:
        chevron = [(.05, -.57), (.42, -.57), (.83, 0), (.42, .57), (.05, .57), (.46, 0)]
        draw.polygon([(x+move.side*dx*radius, y+dy*height) for dx, dy in chevron], fill=ink)


def step_landing(draw, x, y, radius, move, color, phase):
    """Keep the print planted on the beat and send a ripple across the floor."""
    radius_x = radius * (1.55 + .9 * phase)
    radius_y = radius * (.56 + .38 * phase)
    draw.ellipse((x-radius_x, y-radius_y, x+radius_x, y+radius_y),
                 outline=color, width=max(1, round(5*(1-phase))))
    foot_pad(draw, x, y, radius*(1-.55*phase), move, color)


def duck_icon(draw, x, y, radius, color):
    """Bent knees and a downward arrow: dodge, not another punch."""
    ink = (13, 31, 44)
    width = max(2, round(radius * .11))
    draw.ellipse((x-radius*.26,y-radius*.66,x+radius*.26,y-radius*.14),fill=ink)
    draw.line([(x,y-radius*.03),(x,y+radius*.34),(x-radius*.42,y+radius*.54)],
              fill=ink,width=width,joint="curve")
    draw.line([(x,y+radius*.34),(x+radius*.42,y+radius*.54)],
              fill=ink,width=width,joint="curve")
    draw.polygon([(x-radius*.18,y+radius*.52),(x+radius*.18,y+radius*.52),
                  (x,y+radius*.82)],fill=color)
