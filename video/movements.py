"""Video action vocabulary. JSON IDs are stable; labels can be translated freely."""
from dataclasses import dataclass

# Horizontal direction on the viewer's screen.
LEFT = -1
RIGHT = 1


@dataclass(frozen=True)
class Movement:
    label: str
    kind: str
    side: int


MOVEMENTS = {
    "left_jab": Movement("左直拳", "jab", LEFT),
    "right_jab": Movement("右直拳", "jab", RIGHT),
    "left_hook": Movement("左摆拳", "hook", LEFT),
    "right_hook": Movement("右摆拳", "hook", RIGHT),
    "left_uppercut": Movement("左上勾拳", "uppercut", LEFT),
    "right_uppercut": Movement("右上勾拳", "uppercut", RIGHT),
    "step_left": Movement("向左侧步", "step", LEFT),
    "step_right": Movement("向右侧步", "step", RIGHT),
}
