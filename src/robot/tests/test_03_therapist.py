from robot.app import App
from robot.config import get_small_image_dir
from robot.navigation import Navigation
from robot.pages import Pages
from robot.utils import click_image, screenshot

img_dir = get_small_image_dir()

# the four home buttons are visually identical, so each click is restricted to its
# own vertical band; the back button sits in the top-left of every tab
_REGIONS = {
    "user_list": (0.45, 0.25, 1.0, 0.36),
    "add_user": (0.45, 0.38, 1.0, 0.49),
    "settings": (0.45, 0.50, 1.0, 0.61),
    "back": (0.0, 0.0, 0.25, 0.12),
}


async def test_therapist_page(app: App, navigation: Navigation, test_id):
    await navigation.go_to_page(Pages.therapist_page)
    await screenshot(app, "therapist", test_id)

    for tab, label in [
        ("settings", "therapist_settings"),
        ("add_user", "therapist_add_user"),
        ("user_list", "therapist_user_list"),
    ]:
        await click_image(
            app, img_dir / f"therapist/click_{tab}.png", region=_REGIONS[tab]
        )
        await screenshot(app, label, test_id)
        await click_image(
            app, img_dir / "therapist/click_back.png", region=_REGIONS["back"]
        )
