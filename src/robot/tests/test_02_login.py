import asyncio

from robot.app import App
from robot.config import get_small_image_dir, password, username
from robot.navigation import Navigation
from robot.pages import Pages
from robot.timeout import Timeout
from robot.utils import click_image, screenshot, type_text

img_dir = get_small_image_dir()


async def test_email_password_login(app, navigation: Navigation, test_id):
    await navigation.go_to_page(Pages.login)

    # login via the internal email/password form
    await screenshot(app, "login_email_password", test_id)
    await click_image(app, img_dir / "login/click_login_link.png")
    await click_image(app, img_dir / "login/click_email.png")
    await type_text(username, interval=0.05)
    await click_image(app, img_dir / "login/click_password.png")
    await type_text(password, interval=0.05)
    await click_image(app, img_dir / "login/click_login_button.png")

    # assert logged in
    await _assert_logged_in(app, navigation, timeout=10)


async def _assert_logged_in(app: App, navigation: Navigation, timeout: float):
    timer = Timeout(timeout, f"Failed to log in within {timeout} seconds")
    while True:
        timer.check()
        try:
            current_page = await navigation.detect_current_page()
        except TimeoutError:
            continue
        if current_page == Pages.home or current_page == Pages.introduction:
            return
        await asyncio.sleep(0.5)
