import asyncio
import logging

import cv2
import numpy as np
from PIL import ImageGrab

import pytest

from robot.device_emulator import DeviceEmulator
from robot.navigation import Navigation
from robot.pages import Pages
from robot.states import Games
from robot.utils import screenshot
from robot.config import get_small_image_dir
from robot.timeout import Timeout


# games whose in-game slider is mirrored relative to the sphere_runner references:
# turning far-left moves the slider to the position that sphere_runner's
# assert_far_right.png depicts (and vice versa).
_SLIDER_INVERTED = {Games.gravity_gambit}

# games with no free-movement slider at all (e.g. the structured weekly test),
# so the far-left/far-right slider check does not apply.
_SLIDER_SKIP = {Games.weekly_test}


def input_slider_match(app, direction, invert=False):
    """Match the cyan track silhouette, excluding white handles and background."""
    if invert:
        direction = "right" if direction == "left" else "left"
    with ImageGrab.grab(bbox=app._get_bounding_box()) as capture:
        frame = cv2.cvtColor(np.asarray(capture), cv2.COLOR_RGB2BGR)
    height, width = frame.shape[:2]
    frame = frame[int(height * 0.75):, int(width * 0.65):]
    reference = cv2.imread(str(get_small_image_dir() / f"sphere_runner/assert_far_{direction}.png"))
    assert reference is not None
    masks = [cv2.inRange(cv2.cvtColor(image, cv2.COLOR_BGR2HSV),
                        (85, 100, 220), (110, 255, 255))
             for image in (frame, reference)]
    # Tight vertical crop avoids the neighbouring row in two-axis games.
    target = masks[1][5:23]
    best = (-1.0, None)
    for percent in range(85, 126):
        scaled = cv2.resize(target, None, fx=percent / 100, fy=percent / 100,
                            interpolation=cv2.INTER_NEAREST)
        _, score, _, point = cv2.minMaxLoc(cv2.matchTemplate(
            masks[0], scaled, cv2.TM_CCOEFF_NORMED))
        if score > best[0]:
            best = (score, (*point, scaled.shape[1], scaled.shape[0]))
    return best


@pytest.mark.asyncio
async def test_smoke(
    app, navigation: Navigation, device_emulator: DeviceEmulator, test_id, pytestconfig
):
    # Establish the patient session before discovering or launching games.
    await navigation.go_to_page(Pages.home)
    await device_emulator.connect("strap")

    # discover the games in the game_center list's top-to-bottom order (the scroll
    # only moves down, so the loop must visit them in that same visual order)
    await navigation.go_to_page(Pages.game_center)
    games = await navigation.discover_game_center_order()
    assert games, "No games discovered in the game center"
    logging.info("Discovered games: %s", ", ".join(game.value for game in games))
    await navigation.reset_game_center_scroll(games[0])
    logging.info("Game list reset in place to %s", games[0].value)
    start_game = pytestconfig.getoption("smoke_from")
    if start_game is not None:
        names = [game.value for game in games]
        assert start_game in names, f"Requested game {start_game} not found: {names}"
        games = games[names.index(start_game):]
        logging.info("Running games from %s: %s", start_game, ", ".join(game.value for game in games))

    for game in games:
        logging.info("Smoke test: %s", game.value)
        await navigation.go_to_page(Pages.gameplay, game)

        if game in _SLIDER_SKIP:
            await asyncio.sleep(5)
            logging.info("Skipping slider check for %s", game.value)
        else:
            # Gameplay is detected: check both directions immediately, then exit.
            slider_y = None
            first_endpoint = None
            restart_used = False

            async def restart_if_finished():
                nonlocal restart_used
                if game != Games.brick_breaker or not await navigation.locate_max(
                    "game/assert_game_finished.png", 0.95,
                    region=(0.2, 0.1, 0.8, 0.35),
                ):
                    return False
                if restart_used:
                    raise AssertionError(
                        "brick_breaker: game finished again after the single recovery restart"
                    )
                restart_used = True
                await screenshot(app, "brick_breaker_before_restart", test_id)
                # Reset the actual device before restarting; changing only the
                # tracked rotation would make the next incremental input wrong.
                await device_emulator.reset_rotation()
                await navigation.click_image_max(
                    "game/click_finished_restart.png", confidence=0.95,
                    region=(0.2, 0.25, 0.5, 0.5),
                )
                await navigation.wait_for_page(Pages.gameplay)
                logging.info("Brick Breaker restarted; retaining verified movement checks")
                return True

            try:
                for direction, turn in (
                    ("left", device_emulator.turn_far_left),
                    ("right", device_emulator.turn_far_right),
                ):
                    await restart_if_finished()
                    await turn()
                    timer = Timeout(8, f"{game.value}: input {direction} did not produce the required slider endpoint")
                    while True:
                        if await restart_if_finished():
                            # This direction has not passed yet. Neutral was
                            # restored before restart, so send it again.
                            await turn()
                            timer = Timeout(8, f"{game.value}: input {direction} did not produce the required slider endpoint after restart")
                            continue
                        endpoints = ("left", "right") if first_endpoint is None else (
                            "right" if first_endpoint == "left" else "left",
                        )
                        found = False
                        for endpoint in endpoints:
                            score, box = input_slider_match(app, endpoint, invert=game in _SLIDER_INVERTED)
                            if score >= 0.95 and box is not None and (
                                slider_y is None or abs(box[1] - slider_y) < 5
                            ):
                                slider_y = box[1]
                                if first_endpoint is None:
                                    first_endpoint = endpoint
                                found = True
                                break
                        if found:
                            break
                        timer.check()
                        await asyncio.sleep(0.2)
                    await screenshot(app, f"{game.value}_far_{direction}", test_id)
                    logging.info("Movement passed: %s input %s, slider %s", game.value, direction, endpoint)
                if game == Games.brick_breaker:
                    # Stop the round before the console round-trip needed to
                    # restore neutral; otherwise the last lives can expire.
                    await restart_if_finished()
                    await navigation.go_to_page(Pages.pause_menu)
            except Exception:
                await screenshot(app, f"{game.value}_movement_failure", test_id)
                raise
            finally:
                await device_emulator.reset_rotation()

        # quit back to home
        await navigation.go_to_page(Pages.home)
        exit_flow = "cancel, results, home" if game == Games.weekly_test else "pause, home"
        logging.info("Smoke passed: %s (gameplay, %s)", game.value, exit_flow)
