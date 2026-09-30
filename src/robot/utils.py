import asyncio
from pathlib import Path

import cv2
import pynput

from robot.app import App
from robot.config import get_screenshot_dir
from robot.timeout import Timeout

mouse = pynput.mouse.Controller()
keyboard = pynput.keyboard.Controller()

# Shared Unity controls can differ by a few percent between game canvases.
GAME_UI_SCALES = (1.0, 0.94, 0.96, 0.98, 1.02, 1.04, 1.06, 1.08, 1.10, 1.12, 1.14)


def best_template_match(large, target, scales=(1.0,)):
    """Return (score, (x, y, width, height)) for the strongest fitting scale."""
    best_score = -1.0
    best_box = None
    for scale in scales:
        scaled = target if scale == 1.0 else cv2.resize(
            target, None, fx=scale, fy=scale,
            interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC,
        )
        h, w = scaled.shape
        if h > large.shape[0] or w > large.shape[1]:
            continue
        result = cv2.matchTemplate(large, scaled, cv2.TM_CCOEFF_NORMED)
        _, score, _, point = cv2.minMaxLoc(result)
        if score > best_score:
            best_score = score
            best_box = (point[0], point[1], w, h)
    return best_score, best_box


async def tween_mouse_to(target: tuple[int, int], velocity: float = 2000):
    start = mouse.position
    distance = ((start[0] - target[0]) ** 2 + (start[1] - target[1]) ** 2) ** 0.5
    fps = 60
    steps = max(1, int(distance / velocity * fps))
    for step in range(1, steps + 1):
        t = step / steps
        new_x = int(start[0] + (target[0] - start[0]) * t)
        new_y = int(start[1] + (target[1] - start[1]) * t)
        mouse.position = (new_x, new_y)
        await asyncio.sleep(1 / fps)


async def type_text(text: str, interval: float = 0.05):
    for char in text:
        keyboard.press(char)
        keyboard.release(char)
        await asyncio.sleep(interval)


async def type_key(
    key: pynput.keyboard.Key | str, modifiers: list[pynput.keyboard.Key] | None = None,
    hold: float = 0,
):
    if modifiers:
        for modifier in modifiers:
            keyboard.press(modifier)
    keyboard.press(key)
    if hold:
        await asyncio.sleep(hold)
    keyboard.release(key)
    if modifiers:
        for modifier in modifiers:
            keyboard.release(modifier)


async def click_image(
    app: App,
    image_path: Path,
    timeout: int = 5,
    confidence: float | None = None,
    region: tuple[float, float, float, float] | None = None,
):
    """Clicks the center of the given image on the screen, waiting until it appears if necessary."""
    timer = Timeout(
        timeout,
        f"Image {image_path} not found on screen within {timeout} seconds",
    )
    while True:
        bbox_or_null = await app.locate(
            image_path, confidence=confidence, region=region
        )
        if bbox_or_null:
            await tween_mouse_to(
                (
                    (bbox_or_null[0] + bbox_or_null[2]) // 2,
                    (bbox_or_null[1] + bbox_or_null[3]) // 2,
                )
            )
            mouse.click(pynput.mouse.Button.left, 1)
            await asyncio.sleep(0.2)
            return
        timer.check()
        await asyncio.sleep(0.5)


async def scrollbar_scroll_until_visible(
    app: App,
    target_image_path: Path,
    scrollbar_image_path: Path,
    confidence: float | None = None,
    target_region: tuple[float, float, float, float] | None = None,
    timeout: float = 60.0,
    step: int = 15,
) -> tuple[int, int, int, int] | None:
    """
    Drags the scrollbar thumb downward until the target image appears in `target_region`,
    then returns its bounding box. Returns None (instead of raising) when the target is
    not found - e.g. a game that isn't present in this build - so the caller can skip it.

    The mouse wheel freezes partway through this list (it only reaches ~6 of the games),
    so the scrollbar itself is the reliable scroll mechanism: locate the thumb and drag it
    down a small amount per step, re-checking the target after each step.
    """
    timer = Timeout(
        timeout,
        f"Image {target_image_path} not found via scrollbar within {timeout} seconds",
    )
    mouse = pynput.mouse.Controller()
    thumb = cv2.imread(str(scrollbar_image_path), cv2.IMREAD_GRAYSCALE)
    assert thumb is not None, f"Could not load scrollbar image at {scrollbar_image_path}"
    target = cv2.imread(str(target_image_path), cv2.IMREAD_GRAYSCALE)
    assert target is not None, f"Could not load target image at {target_image_path}"

    while True:
        # direct max-match in the region (same approach as the thumb below) - avoids
        # app.locate's clustering / too-many-matches guard rejecting a good match
        large = app._get_large_image().gray_image
        h, w = large.shape
        if target_region is not None:
            rx0 = int(w * target_region[0])
            ry0 = int(h * target_region[1])
            rx1 = int(w * target_region[2])
            ry1 = int(h * target_region[3])
        else:
            rx0, ry0, rx1, ry1 = 0, 0, w, h
        region_img = large[ry0:ry1, rx0:rx1]
        if target.shape[0] <= region_img.shape[0] and target.shape[1] <= region_img.shape[1]:
            tres = cv2.matchTemplate(region_img, target, cv2.TM_CCOEFF_NORMED)
            _, tmax, _, tloc = cv2.minMaxLoc(tres)
            if tmax >= (confidence if confidence is not None else 0.9):
                win = app._get_bounding_box()
                return (
                    win[0] + rx0 + tloc[0],
                    win[1] + ry0 + tloc[1],
                    win[0] + rx0 + tloc[0] + target.shape[1],
                    win[1] + ry0 + tloc[1] + target.shape[0],
                )

        # find the thumb by its single best match - the thin bar matches many nearby
        # positions, so take the max rather than app.locate's multi-cluster check
        large = app._get_large_image().gray_image
        if thumb.shape[0] > large.shape[0] or thumb.shape[1] > large.shape[1]:
            return None
        res = cv2.matchTemplate(large, thumb, cv2.TM_CCOEFF_NORMED)
        _, maxval, _, maxloc = cv2.minMaxLoc(res)
        if maxval < 0.8:
            return None  # thumb gone -> reached the bottom without finding the target

        win = app._get_bounding_box()
        cx = win[0] + maxloc[0] + thumb.shape[1] // 2
        cy = win[1] + maxloc[1] + thumb.shape[0] // 2

        mouse.position = (cx, cy)
        mouse.press(pynput.mouse.Button.left)
        for i in range(1, 11):
            mouse.position = (cx, cy + step * i // 10)
            await asyncio.sleep(0.02)
        mouse.release(pynput.mouse.Button.left)
        await asyncio.sleep(0.3)
        try:
            timer.check()
        except TimeoutError:
            return None


async def scrollbar_drag_step(
    app: App,
    scrollbar_image_path: Path,
    step: int = 15,
    direction: int = 1,
) -> bool:
    """Drag the scrollbar thumb by one `step` in `direction` (+1 down, -1 up).

    Returns True when the thumb actually moved (the list still has room to scroll in
    that direction), False when the thumb is gone or did not move (list is at its end).
    """
    thumb = cv2.imread(str(scrollbar_image_path), cv2.IMREAD_GRAYSCALE)
    assert thumb is not None, f"Could not load scrollbar image at {scrollbar_image_path}"

    def thumb_loc() -> tuple[int, int] | None:
        large = app._get_large_image().gray_image
        if thumb.shape[0] > large.shape[0] or thumb.shape[1] > large.shape[1]:
            return None
        res = cv2.matchTemplate(large, thumb, cv2.TM_CCOEFF_NORMED)
        _, maxval, _, maxloc = cv2.minMaxLoc(res)
        if maxval < 0.8:
            return None
        return maxloc

    before = thumb_loc()
    if before is None:
        return False

    win = app._get_bounding_box()
    cx = win[0] + before[0] + thumb.shape[1] // 2
    cy = win[1] + before[1] + thumb.shape[0] // 2

    mouse.position = (cx, cy)
    mouse.press(pynput.mouse.Button.left)
    for i in range(1, 11):
        mouse.position = (cx, cy + direction * step * i // 10)
        await asyncio.sleep(0.02)
    mouse.release(pynput.mouse.Button.left)
    await asyncio.sleep(0.3)

    after = thumb_loc()
    if after is None:
        return False
    return abs(after[1] - before[1]) > 1


async def match_best_image(
    app: App,
    image_paths: list[Path],
    region: tuple[float, float, float, float] | None = None,
    confidence: float = 0.8,
) -> tuple[int, float] | None:
    """Return (index, score) of the best-matching image in `region`, or None if none
    of them pass `confidence`. Used to detect which of several labels is on screen."""
    large = app._get_large_image().gray_image
    h, w = large.shape
    if region is not None:
        rx0 = int(w * region[0])
        ry0 = int(h * region[1])
        rx1 = int(w * region[2])
        ry1 = int(h * region[3])
    else:
        rx0, ry0, rx1, ry1 = 0, 0, w, h
    region_img = large[ry0:ry1, rx0:rx1]

    best_idx: int | None = None
    best_score = -1.0
    for idx, image_path in enumerate(image_paths):
        target = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if target is None:
            continue
        if target.shape[0] > region_img.shape[0] or target.shape[1] > region_img.shape[1]:
            continue
        res = cv2.matchTemplate(region_img, target, cv2.TM_CCOEFF_NORMED)
        _, tmax, _, _ = cv2.minMaxLoc(res)
        if tmax > best_score:
            best_score = tmax
            best_idx = idx

    if best_idx is None or best_score < confidence:
        return None
    return best_idx, best_score


def foreground_template(image_path: Path, target, foreground_only: bool):
    foreground_range = None
    if foreground_only and image_path.name == "click_menu.png":
        foreground_range = (220, 255)
        target = cv2.inRange(target[:, :20], *foreground_range)
    elif foreground_only:
        # Match the blue icon's silhouette rather than its captured backdrop.
        # Keeping the silhouette's empty pixels also rejects solid bright patches.
        source_color = cv2.imread(str(image_path))
        target = cv2.cvtColor(source_color, cv2.COLOR_BGR2GRAY)
        color = source_color.astype("int16")
        blue = (color[:, :, 0] > color[:, :, 2] + 50) & (color[:, :, 1] > color[:, :, 2] + 30)
        if not blue.any():
            raise ValueError(f"No blue foreground in {image_path}")
        import numpy as np
        intensity = int(np.median(target[blue]))
        foreground_range = (max(0, intensity - 8), min(255, intensity + 8))
        target = cv2.inRange(target, *foreground_range)
    return target, foreground_range


async def click_image_max(
    app: App,
    image_path: Path,
    confidence: float = 0.8,
    region: tuple[float, float, float, float] | None = None,
    timeout: float = 5.0,
    scales: tuple[float, ...] = (1.0,),
    foreground_only: bool = False,
):
    """Click the best (max) match of an image, bypassing app.locate's clustering
    guards that reject good matches with >20 above-threshold pixels."""
    timer = Timeout(
        timeout,
        f"Image {image_path} not found on screen within {timeout} seconds",
    )
    target = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    assert target is not None, f"Could not load image at {image_path}"
    target, foreground_range = foreground_template(image_path, target, foreground_only)
    while True:
        large = app._get_large_image().gray_image
        h, w = large.shape
        if region is not None:
            rx0 = int(w * region[0])
            ry0 = int(h * region[1])
            rx1 = int(w * region[2])
            ry1 = int(h * region[3])
        else:
            rx0, ry0, rx1, ry1 = 0, 0, w, h
        region_img = large[ry0:ry1, rx0:rx1]
        if foreground_range is not None:
            region_img = cv2.inRange(region_img, *foreground_range)
        maxval, box = best_template_match(region_img, target, scales)
        if box is not None and maxval >= confidence:
            win = app._get_bounding_box()
            cx = win[0] + rx0 + box[0] + box[2] // 2
            cy = win[1] + ry0 + box[1] + box[3] // 2
            mouse.position = (cx, cy)
            mouse.click(pynput.mouse.Button.left, 1)
            await asyncio.sleep(0.2)
            return
        timer.check()
        await asyncio.sleep(0.5)


async def assert_image(
    app: App, image_path: Path, timeout: float = 5.0, confidence: float | None = None
) -> None:
    timer = Timeout(
        timeout,
        f"Image {image_path} not found on screen within {timeout} seconds",
    )
    while True:
        bbox_or_null = await app.locate(image_path, confidence=confidence)
        if bbox_or_null:
            return
        timer.check()
        await asyncio.sleep(0.5)


async def screenshot(app: App, name: str, test_id: str):
    screenshot_dir = get_screenshot_dir(test_id)
    image_path = screenshot_dir / (name + ".png")
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    app.screenshot(image_path)
