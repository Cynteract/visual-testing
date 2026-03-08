from pathlib import Path

import PIL.ImageGrab
import pytest
import pytest_asyncio

from robot.app import App
from robot.config import get_screenshot_dir
from robot.reset import reset_app_state, reset_player_data


def pytest_addoption(parser):
    parser.addoption("--username", action="store", default="default username")
    parser.addoption("--password", action="store", default="default password")
    parser.addoption("--test-id", action="store", default="default test id")
    parser.addoption("--binary-path", action="store", default="default binary path")


@pytest.fixture
def username(pytestconfig):
    return pytestconfig.getoption("username")


@pytest.fixture
def password(pytestconfig):
    return pytestconfig.getoption("password")


@pytest.fixture
def test_id(pytestconfig):
    return pytestconfig.getoption("test_id")


@pytest.fixture
def binary_path(pytestconfig):
    return pytestconfig.getoption("binary_path")


@pytest_asyncio.fixture
async def app(binary_path):
    async with App() as app:
        await app.find_or_start_by_path(Path(binary_path))
        app.resize(800, 600)
        app.enforce_size()
        yield app


@pytest.fixture
def no_app_state():
    reset_app_state()


@pytest.fixture
def no_player_data(username, password):
    reset_player_data(username, password)


def pytest_runtest_makereport(item, call):
    # Check if the test raised an exception (failed)
    if call.excinfo is not None:
        print(f"Test {item.name} failed!")
        # take screenshot of the whole screen for debugging
        test_id = item.funcargs.get("test_id", "default")
        screenshot_dir = get_screenshot_dir(test_id)
        with PIL.ImageGrab.grab() as img:
            img.save(screenshot_dir / f"ERROR.png")
