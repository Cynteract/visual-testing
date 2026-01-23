import asyncio
import time
from pathlib import Path

import pyautogui
from pyautogui import ImageNotFoundException, Point
from pyscreeze import Box

REGION = (0, 0, 800, 600)


async def clickImage(imagePath: Path, timeout: int = 5):
    start_time = time.time()
    while True:
        try:
            locationOrNull = pyautogui.locateOnScreen(
                str(imagePath.absolute()), confidence=0.8, region=REGION
            )
            assert locationOrNull is not None
            location: Box = locationOrNull
            currentPosition: Point = pyautogui.position()
            distance = (
                (currentPosition.x - location.left) ** 2
                + (currentPosition.y - location.top) ** 2
            ) ** 0.5
            tweenTime = min(0.5, distance / 500)
            pyautogui.moveTo(location, duration=tweenTime)
            pyautogui.click(location)
            return
        except ImageNotFoundException:
            if time.time() - start_time > timeout:
                raise RuntimeError(
                    f"Image {imagePath} not found on screen within {timeout} seconds"
                )
        await asyncio.sleep(0.5)


async def assertImage(imagePath: Path, timeout: int = 5) -> Box:
    start_time = time.time()
    while True:
        try:
            locationOrNull = pyautogui.locateOnScreen(
                str(imagePath.absolute()), confidence=0.8, region=REGION
            )
            assert locationOrNull is not None
            location: Box = locationOrNull
            return location
        except ImageNotFoundException:
            if time.time() - start_time > timeout:
                raise AssertionError(
                    f"Image {imagePath} not found on screen within {timeout} seconds"
                )
        await asyncio.sleep(0.5)


async def screenshot(name: str, test_id: str):
    base_dir = Path.home() / "Documents" / "visual_testing" / "screenshots"
    image_path = base_dir / test_id / (name + ".png")
    image_path.parent.mkdir(parents=True, exist_ok=True)
    pyautogui.screenshot(str(image_path.absolute()), REGION)
    # benchmark screenshot time
    start_time = time.time()
    for _ in range(10):
        pyautogui.screenshot(str(image_path.absolute()), REGION)
    end_time = time.time()
    avg_time = (end_time - start_time) / 10
    print(f"Average screenshot time: {avg_time:.4f} seconds")


async def runTest(username: str, password: str, test_id: str):
    IMGDIR = Path("test_runner/tests/images")

    # Login
    await clickImage(IMGDIR / "LoginLink.png")
    await screenshot("login_screen", test_id)
    await clickImage(IMGDIR / "Email.png")
    pyautogui.typewrite(username, interval=0.05)
    await clickImage(IMGDIR / "Password.png")
    pyautogui.typewrite(password, interval=0.05)
    await clickImage(IMGDIR / "LoginButton.png")

    # Game center
    await screenshot("game_center_screen", test_id)
    await clickImage(IMGDIR / "Game_center.png", timeout=15)
    await assertImage(IMGDIR / "Please_connect.png", timeout=15)
    await clickImage(IMGDIR / "Back.png")

    # Logout
    await clickImage(IMGDIR / "Settings.png")
    await clickImage(IMGDIR / "Logout.png")
    await assertImage(IMGDIR / "LoginTitle.png", timeout=15)
