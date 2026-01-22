import asyncio
import time
from pathlib import Path

import pyautogui
from pyautogui import ImageNotFoundException, Point
from pyscreeze import Box


async def clickImage(imagePath: Path, timeout: int = 5):
    start_time = time.time()
    while True:
        try:
            locationOrNull = pyautogui.locateOnScreen(
                str(imagePath.absolute()), confidence=0.8
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
                str(imagePath.absolute()), confidence=0.8
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


async def runTest():
    # Load .env file
    env = {}
    with open(".env") as f:
        for line in f:
            key, value = line.strip().split("=", 1)
            env[key] = value

    IMGDIR = Path("test_runner/tests/images")

    # Login
    await clickImage(IMGDIR / "LoginLink.png")
    await clickImage(IMGDIR / "Email.png")
    pyautogui.typewrite(env.get("USER"), interval=0.05)
    await clickImage(IMGDIR / "Password.png")
    pyautogui.typewrite(env.get("PASSWORD"), interval=0.05)
    await clickImage(IMGDIR / "LoginButton.png")

    # Game center
    await clickImage(IMGDIR / "Game_center.png", timeout=15)
    await assertImage(IMGDIR / "Please_connect.png", timeout=15)
    await clickImage(IMGDIR / "Back.png")

    # Logout
    await clickImage(IMGDIR / "Settings.png")
    await clickImage(IMGDIR / "Logout.png")
    await assertImage(IMGDIR / "LoginTitle.png", timeout=15)
