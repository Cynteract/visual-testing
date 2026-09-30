import logging

import pytest

from robot.device_emulator import DeviceEmulator
from robot.navigation import Navigation
from robot.pages import Pages
from robot.states import Games


@pytest.mark.asyncio
async def test_smoke(
    app, navigation: Navigation, device_emulator: DeviceEmulator, test_id, pytestconfig
):
    import asyncio

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

        # let the game settle before pausing out of it
        await asyncio.sleep(5)

        # quit back to home
        await navigation.go_to_page(Pages.home)
        exit_flow = "cancel, results, home" if game == Games.weekly_test else "pause, home"
        logging.info("Smoke passed: %s (gameplay, %s)", game.value, exit_flow)
