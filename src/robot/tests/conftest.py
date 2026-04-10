import logging
import os
from pathlib import Path

import PIL.ImageGrab
import pytest
import pytest_asyncio

from robot.app import App
from robot.config import get_data_dir, get_frame_size
from robot.device_emulator import DeviceEmulator
from robot.device_types import DeviceTypes
from robot.navigation import Navigation
from robot.pages import Pages
from robot.player_log_monitor import PlayerLogMonitor
from robot.state_machine import UIStateMachine
from robot.states import DefinedUIState, Games
from robot.utils import keyboard
from shared.utils import load_env_file

env = load_env_file()


def pytest_addoption(parser):
    parser.addoption("--test-id", action="store", default="default")
    parser.addoption(
        "--binary-path",
        action="store",
        default=env.get("BINARY_PATH"),
        required=env.get("BINARY_PATH") is None,
    )


@pytest.fixture
def test_id(pytestconfig):
    return pytestconfig.getoption("test_id")


@pytest.fixture
def binary_path(pytestconfig):
    return Path(pytestconfig.getoption("binary_path"))


@pytest_asyncio.fixture
async def app(binary_path):
    async with App() as app:
        if os.environ.get("DEBUG") is not None:
            app.debug_dir = get_data_dir(test_id="debug")
        await app.find_or_start_by_path(binary_path)
        await app.resize_client_frame(*get_frame_size())
        app.enforce_size()
        yield app


@pytest.fixture
def player_log_monitor():
    yield PlayerLogMonitor()


@pytest.fixture
async def state_machine(app):
    yield UIStateMachine(
        initial_state=DefinedUIState(
            page=Pages._restart,
            game=Games.no_game,
            device=DeviceTypes.not_connected,
        )
    )


@pytest_asyncio.fixture
async def device_emulator(
    state_machine: UIStateMachine, player_log_monitor: PlayerLogMonitor
):
    async with DeviceEmulator(
        keyboard, state_machine, player_log_monitor
    ) as device_emulator:
        yield device_emulator


@pytest_asyncio.fixture
async def navigation(
    app: App, state_machine: UIStateMachine, device_emulator: DeviceEmulator
):
    nav = Navigation(
        app,
        device_emulator,
        state_machine,
    )
    yield nav


def pytest_runtest_makereport(item, call):
    # Check if the test raised an exception (failed)
    if call.excinfo is not None:
        logging.error(f"Test {item.name} failed!")
        # take screenshot of the whole screen for debugging
        test_id = item.funcargs.get("test_id")
        data_dir = get_data_dir(test_id)
        data_dir.mkdir(parents=True, exist_ok=True)
        with PIL.ImageGrab.grab() as img:
            img.save(data_dir / f"ERROR.png")
