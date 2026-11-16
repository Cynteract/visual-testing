"""Slider comparison bounds in the robot's 850 x 600 screenshots."""

from visual_regression_tracker.types import IgnoreArea

# Fixed bounds preserve position checks; never follow the handle dynamically.
# Include both rows for two-axis games, plus a small margin around the tracks.
SLIDER_BOUNDS = {
    "asteroid_storm": (672, 541, 804, 587),
    "brick_breaker": (672, 552, 804, 576),
    "fruit_frenzy": (660, 549, 800, 573),
    "gravity_gambit": (671, 552, 803, 575),
    "highway_hazzard": (663, 550, 801, 574),
    "jump_and_roll": (672, 540, 804, 587),
    "maze_escape": (672, 540, 804, 587),
    "sphere_runner": (672, 558, 804, 581),
    "tunnel_runner": (672, 552, 803, 575),
    "whack_a_blob": (672, 552, 804, 576),
}


def slider_ignore_areas(name: str, size: tuple[int, int]):
    suffix = next((s for s in ("_far_left", "_far_right") if name.endswith(s)), None)
    if suffix is None:
        return None
    game = name[:-len(suffix)]
    if game not in SLIDER_BOUNDS or size != (850, 600):
        raise ValueError(f"Slider comparison bounds need review: {name}, {size}")
    left, top, right, bottom = SLIDER_BOUNDS[game]
    width, height = size
    return [
        IgnoreArea(x=0, y=0, width=width, height=top),
        IgnoreArea(x=0, y=bottom, width=width, height=height - bottom),
        IgnoreArea(x=0, y=top, width=left, height=bottom - top),
        IgnoreArea(x=right, y=top, width=width - right, height=bottom - top),
    ]
