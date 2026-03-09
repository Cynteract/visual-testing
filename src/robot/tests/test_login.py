from pathlib import Path

import pytest

from robot.app import App, AppState
from robot.config import get_small_image_dir, password, username
from robot.reset import reset_app_state
from robot.tests.shared.app_navigation import Pages, go_to_page, wait_for_page
from robot.tests.shared.browser_actions import login_with_browser_cookie_absent
from robot.utils import (
    assert_any_image,
    assert_image,
    click_image,
    left_click,
    screenshot,
    type_text,
)

REGION = (0, 0, 800, 600)
img_dir = get_small_image_dir()


@pytest.mark.asyncio
async def test_first_start_login(binary_path, test_id):
    async with App() as app:
        # close app if it is already running from previous test
        try:
            await app.find_by_path(Path(binary_path), timeout=0.2)
        except TimeoutError:
            pass
        if app.state == AppState.Grabbed:
            app.close()

        # reset and restart app for first start experience
        reset_app_state()
        await app.find_or_start_by_path(Path(binary_path))
        app.resize(800, 600)
        app.enforce_size()
        await wait_for_page(app, Pages.startup, timeout=15)

        # reject app update
        await assert_image(app, img_dir / "startup/assert_update_now.png", timeout=5)
        await click_image(app, img_dir / "startup/click_no.png")

        # skip second intro video
        await left_click()

        # browser login
        await login_with_browser_cookie_absent(username, password, test_id)

        # assert logged in
        await _assert_logged_in(app, timeout=20)


@pytest.mark.asyncio
async def test_email_password_login(app, test_id):
    await go_to_page(app, Pages.login)

    # login
    await click_image(app, img_dir / "login/click_login_link.png")
    await screenshot(app, "login_screen", test_id)
    await click_image(app, img_dir / "login/click_email.png")
    await type_text(username, interval=0.05)
    await click_image(app, img_dir / "login/click_password.png")
    await type_text(password, interval=0.05)
    await click_image(app, img_dir / "login/click_login_button.png")

    # assert logged in
    await _assert_logged_in(app, timeout=10)


async def _assert_logged_in(app: App, timeout: float):
    await assert_any_image(
        app,
        [
            img_dir / "introduction/assert_welcome_title.png",
            img_dir / "home/click_game_center.png",
        ],
        timeout=timeout,
    )
