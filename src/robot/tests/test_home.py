from robot.app import App
from robot.config import get_small_image_dir
from robot.reset import reset_player_data
from robot.tests.shared.app_navigation import Navigation
from robot.tests.shared.pages import Pages
from robot.utils import assert_image, click_image, screenshot, type_text

img_dir = get_small_image_dir()


async def test_please_connect(app: App, navigation: Navigation, test_id):
    await navigation.go_to_page(Pages.please_connect)
    assert await navigation.detect_current_page() == Pages.please_connect
    await screenshot(app, "please_connect", test_id)


async def test_home_page(app, navigation: Navigation, test_id):
    await navigation.go_to_page(Pages.home)
    await screenshot(app, "home", test_id)


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
