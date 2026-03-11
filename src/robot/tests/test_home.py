import pytest

from robot.config import get_small_image_dir
from robot.reset import reset_player_data
from robot.tests.shared.app_navigation import (
    Pages,
    detect_current_page,
    go_to_page,
    transition,
)
from robot.utils import assert_image, click_image, screenshot, type_text

REGION = (0, 0, 800, 600)
img_dir = get_small_image_dir()


@pytest.mark.asyncio
async def test_please_connect(app, test_id):
    await go_to_page(app, Pages.home)
    await transition(app, Pages.home, Pages.game_center)
    assert await detect_current_page(app) == Pages.please_connect
    await screenshot(app, "please_connect", test_id)


@pytest.mark.asyncio
async def test_home_page(app, test_id):
    await go_to_page(app, Pages.home)
    await screenshot(app, "home", test_id)


@pytest.mark.asyncio
async def test_introduction_page(app, test_id):
    if not await detect_current_page(app) == Pages.introduction:
        await go_to_page(app, Pages.login)
        reset_player_data()
        await transition(app, Pages.login, Pages._next)

    assert await detect_current_page(app) == Pages.introduction
    await screenshot(app, "introduction_welcome", test_id)
    await click_image(app, img_dir / "introduction/click_enter.png")
    await assert_image(app, img_dir / "introduction/assert_blob_face.png", timeout=10)
    await click_image(app, img_dir / "introduction/click_skip.png")
    await screenshot(app, "introduction_buddy_name", test_id)
    await click_image(app, img_dir / "introduction/click_name_field.png")
    await type_text("visualTesting", interval=0.05)
    await click_image(app, img_dir / "introduction/click_confirm.png")
    assert await detect_current_page(app) == Pages.home
