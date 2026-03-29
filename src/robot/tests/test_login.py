import asyncio
from pathlib import Path

from robot.app import App
from robot.config import get_frame_size, get_small_image_dir, password, username
from robot.navigation import Navigation
from robot.pages import Pages
from robot.reset import reset_app_state
from robot.tests.shared.browser_actions import login_with_browser_cookie_absent
from robot.timeout import Timeout
from robot.utils import click_image, screenshot, type_text

img_dir = get_small_image_dir()


async def test_first_start_login(
    app: App, binary_path: Path, navigation: Navigation, test_id
):
    app.close()
    # reset and restart app for first start experience
    reset_app_state()
    await app.find_or_start_by_path(binary_path)
    await app.resize_client_frame(*get_frame_size())
    app.enforce_size()
    await navigation.wait_for_page(Pages.update, timeout=15)
    # the browser might cover the Cynteract window
    await navigation.trigger_transition(Pages.login)

    # browser login
    await login_with_browser_cookie_absent(username, password, test_id)

    # assert logged in
    await _assert_logged_in(app, navigation, timeout=20)


async def test_email_password_login(app, navigation: Navigation, test_id):
    await navigation.go_to_page(Pages.login)

    # login
    await click_image(app, img_dir / "login/click_login_link.png")
    await screenshot(app, "login_email_password", test_id)
    await click_image(app, img_dir / "login/click_email.png")
    await type_text(username, interval=0.05)
    await click_image(app, img_dir / "login/click_password.png")
    await type_text(password, interval=0.05)
    await click_image(app, img_dir / "login/click_login_button.png")

    # assert logged in
    await _assert_logged_in(app, navigation, timeout=10)


async def _assert_logged_in(app: App, navigation: Navigation, timeout: float):
    timer = Timeout(timeout, "Failed to log in within {timeout} seconds")
    while True:
        timer.check()
        try:
            current_page = await navigation.detect_current_page()
        except TimeoutError:
            continue
        if current_page == Pages.home or current_page == Pages.introduction:
            return
        await asyncio.sleep(0.5)
