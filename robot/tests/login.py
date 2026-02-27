from pathlib import Path

from robot.app import App
from robot.tests.browser_login import browser_login_test
from robot.utils import assert_image, click_image, screenshot, type_text

REGION = (0, 0, 800, 600)


class LoginTest:
    def __init__(self, app: App):
        self.app = app

    async def runTest(self, username: str, password: str, test_id: str):
        IMGDIR = Path("robot/tests/images")

        # Browser login
        await browser_login_test(username, password, test_id)

        # # Login
        # await click_image(self.app, IMGDIR / "LoginLink.png")
        # await screenshot(self.app, "login_screen", test_id)
        # await click_image(self.app, IMGDIR / "Email.png")
        # await type_text(username, interval=0.05)
        # await click_image(self.app, IMGDIR / "Password.png")
        # await type_text(password, interval=0.05)
        # await click_image(self.app, IMGDIR / "LoginButton.png")

        # Introduction
        await assert_image(
            self.app, IMGDIR / "introduction" / "assert_welcome_title.png", timeout=10
        )
        await screenshot(self.app, "introduction_screen", test_id)
        await click_image(self.app, IMGDIR / "introduction" / "click_enter.png")
        await assert_image(
            self.app, IMGDIR / "introduction" / "assert_blob_face.png", timeout=10
        )
        await click_image(self.app, IMGDIR / "introduction" / "click_skip.png")
        await click_image(self.app, IMGDIR / "introduction" / "click_name_field.png")
        await type_text("visualTesting", interval=0.05)
        await click_image(self.app, IMGDIR / "introduction" / "click_confirm.png")
        await assert_image(self.app, IMGDIR / "Game_center.png", timeout=15)

        # Game center
        await screenshot(self.app, "game_center_screen", test_id)
        await click_image(self.app, IMGDIR / "Game_center.png", timeout=5)
        await assert_image(self.app, IMGDIR / "Please_connect.png", timeout=5)
        await click_image(self.app, IMGDIR / "Back.png")

        # Logout
        await click_image(self.app, IMGDIR / "Settings.png")
        await click_image(self.app, IMGDIR / "Logout.png")
        await assert_image(self.app, IMGDIR / "LoginTitle.png", timeout=15)
