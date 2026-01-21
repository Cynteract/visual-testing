from pyscreeze import Box
from pyautogui import ImageNotFoundException, Point
import pyautogui
import os
import time
from pathlib import Path


def clickImage(imagePath: Path, timeout: int = 5):
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
        time.sleep(0.5)


def assertImage(imagePath: Path, timeout: int = 5) -> Box:
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
        time.sleep(0.5)


def runTest():
    # Load .env file
    env = {}
    with open(".env") as f:
        for line in f:
            key, value = line.strip().split("=", 1)
            env[key] = value

    IMGDIR = Path("test_runner/tests/images")
    # Open the application
    binary_path = env.get("BINARY_PATH")
    if not binary_path:
        raise RuntimeError("BINARY_PATH is not set in the .env file")
    # os.startfile(binary_path)  # Open the application

    # Wait for the application to load
    # time.sleep(5)  # Adjust the sleep time as needed

    # Login
    clickImage(IMGDIR / "LoginLink.png")
    clickImage(IMGDIR / "Email.png")
    pyautogui.typewrite(env.get("USER"), interval=0.1)
    clickImage(IMGDIR / "Password.png")
    pyautogui.typewrite(env.get("PASSWORD"), interval=0.1)
    clickImage(IMGDIR / "LoginButton.png")

    # Game center
    clickImage(IMGDIR / "Game_center.png", timeout=15)
    assertImage(IMGDIR / "Please_connect.png", timeout=15)
    clickImage(IMGDIR / "Back.png")

    # Logout
    clickImage(IMGDIR / "Settings.png")
    clickImage(IMGDIR / "Logout.png")
    assertImage(IMGDIR / "LoginTitle.png", timeout=15)
