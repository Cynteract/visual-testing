import asyncio
import time
from pathlib import Path

import pynput

from test_runner.app import App
from test_runner.config import get_screenshot_dir

REGION = (0, 0, 800, 600)


class LoginTest:
    def __init__(self, app: App):
        self.app = app
        self.mouse = pynput.mouse.Controller()
        self.keyboard = pynput.keyboard.Controller()

    async def tween_mouse_to(self, target: tuple[int, int], velocity: float = 2000):
        start = self.mouse.position
        distance = ((start[0] - target[0]) ** 2 + (start[1] - target[1]) ** 2) ** 0.5
        fps = 60
        steps = int(distance / velocity * fps)
        for step in range(1, steps + 1):
            t = step / steps
            new_x = int(start[0] + (target[0] - start[0]) * t)
            new_y = int(start[1] + (target[1] - start[1]) * t)
            self.mouse.position = (new_x, new_y)
            await asyncio.sleep(1 / fps)

    async def type_text(self, text: str, interval: float = 0.05):
        for char in text:
            self.keyboard.press(char)
            self.keyboard.release(char)
            await asyncio.sleep(interval)

    async def clickImage(self, imagePath: Path, timeout: int = 5):
        start_time = time.time()
        while True:
            bboxOrNull = self.app.locate(imagePath)
            if bboxOrNull:
                await self.tween_mouse_to(
                    (
                        (bboxOrNull[0] + bboxOrNull[2]) // 2,
                        (bboxOrNull[1] + bboxOrNull[3]) // 2,
                    )
                )
                self.mouse.click(pynput.mouse.Button.left, 1)
                await asyncio.sleep(0.2)
                return
            elif time.time() - start_time > timeout:
                raise RuntimeError(
                    f"Image {imagePath} not found on screen within {timeout} seconds"
                )
            await asyncio.sleep(0.5)

    async def assertImage(self, imagePath: Path, timeout: int = 5) -> None:
        start_time = time.time()
        while True:
            bboxOrNull = self.app.locate(imagePath)
            if bboxOrNull:
                return
            elif time.time() - start_time > timeout:
                raise RuntimeError(
                    f"Image {imagePath} not found on screen within {timeout} seconds"
                )
            await asyncio.sleep(0.5)

    async def screenshot(self, name: str, test_id: str):
        screenshot_dir = get_screenshot_dir(test_id)
        image_path = screenshot_dir / (name + ".png")
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.app.screenshot(image_path)

    async def runTest(self, username: str, password: str, test_id: str):
        IMGDIR = Path("test_runner/tests/images")

        # Login
        await self.clickImage(IMGDIR / "LoginLink.png")
        await self.screenshot("login_screen", test_id)
        await self.clickImage(IMGDIR / "Email.png")
        await self.type_text(username, interval=0.05)
        await self.clickImage(IMGDIR / "Password.png")
        await self.type_text(password, interval=0.05)
        await self.clickImage(IMGDIR / "LoginButton.png")

        # Game center
        await self.screenshot("game_center_screen", test_id)
        await self.clickImage(IMGDIR / "Game_center.png", timeout=15)
        await self.assertImage(IMGDIR / "Please_connect.png", timeout=15)
        await self.clickImage(IMGDIR / "Back.png")

        # Logout
        await self.clickImage(IMGDIR / "Settings.png")
        await self.clickImage(IMGDIR / "Logout.png")
        await self.assertImage(IMGDIR / "LoginTitle.png", timeout=15)
