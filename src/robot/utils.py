import asyncio
import time
from pathlib import Path

import pynput

from robot.app import App
from robot.config import get_screenshot_dir

mouse = pynput.mouse.Controller()
keyboard = pynput.keyboard.Controller()


async def tween_mouse_to(target: tuple[int, int], velocity: float = 2000):
    start = mouse.position
    distance = ((start[0] - target[0]) ** 2 + (start[1] - target[1]) ** 2) ** 0.5
    fps = 60
    steps = int(distance / velocity * fps)
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


async def type_key(key: pynput.keyboard.Key):
    keyboard.press(key)
    keyboard.release(key)


async def click_image(app: App, image_path: Path, timeout: int = 5):
    start_time = time.time()
    while True:
        bbox_or_null = app.locate(image_path)
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
        elif time.time() - start_time > timeout:
            raise RuntimeError(
                f"Image {image_path} not found on screen within {timeout} seconds"
            )
        await asyncio.sleep(0.5)


async def assert_image(app: App, image_path: Path, timeout: int = 5) -> None:
    start_time = time.time()
    while True:
        bbox_or_null = app.locate(image_path)
        if bbox_or_null:
            return
        elif time.time() - start_time > timeout:
            raise RuntimeError(
                f"Image {image_path} not found on screen within {timeout} seconds"
            )
        await asyncio.sleep(0.5)


async def screenshot(app: App, name: str, test_id: str):
    screenshot_dir = get_screenshot_dir(test_id)
    image_path = screenshot_dir / (name + ".png")
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    app.screenshot(image_path)
