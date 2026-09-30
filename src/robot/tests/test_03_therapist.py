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
        ("user_list", "therapist_user_list"),
        ("add_user", "therapist_add_user"),
        ("settings", "therapist_settings"),
    ]:
        await click_image(
            app, img_dir / f"therapist/click_{tab}.png", region=_REGIONS[tab]
        )
        await screenshot(app, label, test_id)
        if tab == "settings":
            from robot.utils import assert_image, click_image_max

            # wait for the therapist settings page, then logout from it
            await assert_image(
                app, img_dir / "therapist/assert_therapist_settings.png"
            )
            await click_image_max(
                app, img_dir / "therapist/click_logout.png", confidence=0.6
            )
            await navigation.wait_for_page(Pages.login, timeout=20)
        else:
            await click_image(
                app, img_dir / "therapist/click_back.png", region=_REGIONS["back"]
            )
