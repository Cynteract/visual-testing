import asyncio

from robot.app import App
from robot.config import get_small_image_dir
from robot.navigation import Navigation
from robot.pages import Pages
from robot.reset import reset_player_data
from robot.utils import assert_image, click_image, screenshot, type_text

img_dir = get_small_image_dir()


async def test_please_connect(app: App, navigation: Navigation, test_id):
    await navigation.go_to_page(Pages.please_connect)
    assert await navigation.detect_current_page() == Pages.please_connect
    await screenshot(app, "please_connect", test_id)


async def test_home_page(app, navigation: Navigation, test_id):
    await navigation.go_to_page(Pages.home)
    await screenshot(app, "home", test_id)


async def test_buddy_page(app, navigation: Navigation, test_id):
    await navigation.go_to_page(Pages.buddy_page)
    await screenshot(app, "buddy", test_id)


async def test_help_page(app, navigation: Navigation, test_id):
    await navigation.go_to_page(Pages.help_page)
    await screenshot(app, "help", test_id)


async def test_achievements_page(app, navigation: Navigation, test_id):
    await navigation.go_to_page(Pages.achievements)
    await screenshot(app, "achievements", test_id)
    for tab_image, name, dwell in [
        ("achievements/click_level.png", "achievements_level", 0.5),
        ("achievements/click_trend.png", "achievements_trend", 0.5),
        ("achievements/click_my_diary.png", "achievements_my_diary", 0.5),
        ("achievements/click_rank.png", "achievements_rank", 0.5),
        ("achievements/click_achievements.png", "achievements_tab", 0.5),
        ("achievements/click_mood.png", "achievements_mood", 0.5),
        # the leaderboard tab fetches its rows over the network, so wait longer
        ("achievements/click_leaderboard.png", "achievements_leaderboard", 10.0),
        
    ]:
        # tabs live in the top bar, so restrict the search there to stay unique
        await click_image(
            app,
            img_dir / tab_image,
            region=(0.0, 0.0, 1.0, 0.15),
        )
        await asyncio.sleep(dwell)
        await screenshot(app, name, test_id)


async def test_introduction_page(app, navigation: Navigation, test_id):
    if not await navigation.detect_current_page() == Pages.introduction:
        await navigation.go_to_page(Pages.login)
        reset_player_data()
        await navigation.go_to_page(Pages.introduction)

    assert await navigation.detect_current_page() == Pages.introduction
    await screenshot(app, "introduction_welcome", test_id)
    await click_image(app, img_dir / "introduction/click_enter.png")
    await assert_image(app, img_dir / "introduction/assert_blob_face.png", timeout=10)
    await click_image(app, img_dir / "introduction/click_skip.png")
    await screenshot(app, "introduction_buddy_name", test_id)
    await click_image(app, img_dir / "introduction/click_name_field.png")
    await type_text("visualTesting", interval=0.05)
    await click_image(app, img_dir / "introduction/click_confirm.png")
    assert await navigation.detect_current_page() == Pages.home
