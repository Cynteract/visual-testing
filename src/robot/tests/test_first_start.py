import asyncio

import pytest

from robot.app import AppState
from robot.config import get_small_image_dir
from robot.tests.shared.browser_login import browser_login_cookie_absent
from robot.utils import assert_image, click_image, screenshot, type_text

REGION = (0, 0, 800, 600)


@pytest.mark.asyncio
async def test_first_login(
    no_app_state, no_player_data, app, username, password, test_id
):
    img_dir = get_small_image_dir()

    # reject app update
    await assert_image(app, img_dir / "startup" / "assert_update_now.png", timeout=5)
    await click_image(app, img_dir / "startup" / "click_no.png")

    # wait for startup video
    if app.state == AppState.Launched:
        await asyncio.sleep(8)
    else:
        # wait for app to come to foreground
        await asyncio.sleep(0.5)

    # browser login
    await browser_login_cookie_absent(username, password, test_id)

    # # login
    # await click_image(app, img_dir / "LoginLink.png")
    # await screenshot(app, "login_screen", test_id)
    # await click_image(app, img_dir / "Email.png")
    # await type_text(username, interval=0.05)
    # await click_image(app, img_dir / "Password.png")
    # await type_text(password, interval=0.05)
    # await click_image(app, img_dir / "LoginButton.png")

    # introduction
    await assert_image(
        app, img_dir / "introduction" / "assert_welcome_title.png", timeout=10
    )
    await screenshot(app, "introduction_screen", test_id)
    await click_image(app, img_dir / "introduction" / "click_enter.png")
    await assert_image(
        app, img_dir / "introduction" / "assert_blob_face.png", timeout=10
    )
    await click_image(app, img_dir / "introduction" / "click_skip.png")
    await click_image(app, img_dir / "introduction" / "click_name_field.png")
    await type_text("visualTesting", interval=0.05)
    await click_image(app, img_dir / "introduction" / "click_confirm.png")
    await assert_image(app, img_dir / "Game_center.png", timeout=15)

    # game center
    await screenshot(app, "game_center_screen", test_id)
    await click_image(app, img_dir / "Game_center.png", timeout=5)
    await assert_image(app, img_dir / "Please_connect.png", timeout=5)
    await click_image(app, img_dir / "Back.png")

    # logout
    await click_image(app, img_dir / "Settings.png")
    await click_image(app, img_dir / "Logout.png")
    await assert_image(app, img_dir / "LoginTitle.png", timeout=15)
