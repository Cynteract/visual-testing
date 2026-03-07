import asyncio

from robot.app import App, AppState
from robot.config import get_small_image_dir
from robot.tests.shared.app_state import is_cookie_present
from robot.tests.shared.browser_login import browser_login_cookie_absent
from robot.utils import assert_image, click_image, screenshot, type_text

REGION = (0, 0, 800, 600)


class LoginTest:
    def __init__(self, app: App):
        self.app = app

    async def clean_app_state_smoke_test(
        self, username: str, password: str, test_id: str
    ):
        img_dir = get_small_image_dir()

        assert (
            not is_cookie_present()
        ), "Cookie for my.cynteract.com should not be present before login test"

        # wait for startup video
        if self.app.state == AppState.Launched:
            await asyncio.sleep(8)
        else:
            # wait for app to come to foreground
            await asyncio.sleep(0.5)

        # Browser login
        await browser_login_cookie_absent(username, password, test_id)

        # # Login
        # await click_image(self.app, img_dir / "LoginLink.png")
        # await screenshot(self.app, "login_screen", test_id)
        # await click_image(self.app, img_dir / "Email.png")
        # await type_text(username, interval=0.05)
        # await click_image(self.app, img_dir / "Password.png")
        # await type_text(password, interval=0.05)
        # await click_image(self.app, img_dir / "LoginButton.png")

        # Introduction
        await assert_image(
            self.app, img_dir / "introduction" / "assert_welcome_title.png", timeout=10
        )
        await screenshot(self.app, "introduction_screen", test_id)
        await click_image(self.app, img_dir / "introduction" / "click_enter.png")
        await assert_image(
            self.app, img_dir / "introduction" / "assert_blob_face.png", timeout=10
        )
        await click_image(self.app, img_dir / "introduction" / "click_skip.png")
        await click_image(self.app, img_dir / "introduction" / "click_name_field.png")
        await type_text("visualTesting", interval=0.05)
        await click_image(self.app, img_dir / "introduction" / "click_confirm.png")
        await assert_image(self.app, img_dir / "Game_center.png", timeout=15)

        # Game center
        await screenshot(self.app, "game_center_screen", test_id)
        await click_image(self.app, img_dir / "Game_center.png", timeout=5)
        await assert_image(self.app, img_dir / "Please_connect.png", timeout=5)
        await click_image(self.app, img_dir / "Back.png")

        # Logout
        await click_image(self.app, img_dir / "Settings.png")
        await click_image(self.app, img_dir / "Logout.png")
        await assert_image(self.app, img_dir / "LoginTitle.png", timeout=15)
