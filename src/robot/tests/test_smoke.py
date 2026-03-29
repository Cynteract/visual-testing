import pytest

from robot.config import get_small_image_dir
from robot.device_emulator import DeviceEmulator
from robot.navigation import Navigation
from robot.pages import Pages
from robot.utils import assert_image

img_dir = get_small_image_dir()


@pytest.mark.asyncio
async def test_smoke(
    app, navigation: Navigation, device_emulator: DeviceEmulator, test_id
):
    await navigation.go_to_page(Pages.gameplay)
    await device_emulator.turn_far_left()
    await assert_image(
        app, img_dir / "sphere_runner/assert_far_left.png", confidence=0.95
    )
    await device_emulator.turn_far_right()
    await assert_image(
        app, img_dir / "sphere_runner/assert_far_right.png", confidence=0.95
    )
