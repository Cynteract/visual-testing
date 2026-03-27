import pytest

from robot.config import get_small_image_dir
from robot.tests.shared.app_navigation import Navigation
from robot.tests.shared.pages import Pages

img_dir = get_small_image_dir()


@pytest.mark.asyncio
async def test_smoke(app, navigation: Navigation, test_id):
    await navigation.go_to_page(Pages.game_center)
    await navigation.go_to_page(Pages.gameplay)
