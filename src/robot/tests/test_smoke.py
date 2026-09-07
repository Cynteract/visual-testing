import pytest

from robot.config import get_small_image_dir
from robot.device_emulator import DeviceEmulator
from robot.navigation import Navigation
from robot.pages import Pages
from robot.states import Games
from robot.utils import assert_image

img_dir = get_small_image_dir()


@pytest.mark.asyncio
async def test_smoke(
    app, navigation: Navigation, device_emulator: DeviceEmulator, test_id
):
    # pin the game explicitly - with 12 games now reachable via the same generic
    # game_center path, an unqualified Pages.gameplay target would be ambiguous
    await navigation.go_to_page(Pages.gameplay, Games.sphere_runner)
    await device_emulator.turn_far_left()
    await assert_image(
        app, img_dir / "sphere_runner/assert_far_left.png", confidence=0.95
    )
    await device_emulator.turn_far_right()
    await assert_image(
        app, img_dir / "sphere_runner/assert_far_right.png", confidence=0.95
    )
