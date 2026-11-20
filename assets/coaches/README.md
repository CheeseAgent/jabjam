# Coach art packs

The bundled [Milktea cutout rig](milktea/rig/rig.json) uses its own joint and motion schema. Read the [rig handoff](../../docs/coach-avatar.md) for pivots, z-order, viewer-side naming and the sample.

## Sprite clips (v1)

The coach module renders a placeholder vector bunny by default. Replace it with transparent
PNG sequences without changing beat detection, choreography, course actions, or the arena.

To add a skin, create assets/coaches/<skin-id>/manifest.json, for example:

{
  "version": 1,
  "clips": {
    "idle": ["idle/00.png", "idle/01.png"],
    "left_jab.prepare": ["left_jab/prepare_00.png", "left_jab/prepare_01.png"],
    "left_jab.strike": ["left_jab/strike_00.png"],
    "left_jab.recover": ["left_jab/recover_00.png"]
  }
}

Complete the prepare, strike and recover clips for all eight stable IDs from
video/movements.py (including step_left and step_right). A missing requested clip is a
hard error rather than silently showing an incorrect exercise. Each frame is a full-body,
transparent RGBA PNG on a consistent canvas, with the feet touching the bottom margin;
all frames in a skin must use the same character placement and dimensions. Paths must
remain inside their skin directory. Do not commit licensed music or unlicensed artwork.

In the course picture settings, select:
  "coach": {"enabled": true, "renderer": "sprite", "skin": "milktea"}

The clip is chosen from the song timestamp, never from how many frames have elapsed.
The strike clip begins at the exact note.time. Video at 24fps quantizes to video frames.
The punch-side IDs are the VIEWER's screen side, not the character's anatomical side:
left means the glove visible on the left side of the screen.
