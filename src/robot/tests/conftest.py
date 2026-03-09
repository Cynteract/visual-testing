import asyncio
from pathlib import Path

import PIL.ImageGrab
import pytest
import pytest_asyncio

from robot.app import App, AppState
from robot.config import get_screenshot_dir
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
    return pytestconfig.getoption("binary_path")


@pytest_asyncio.fixture
async def app(binary_path):
    async with App() as app:
        await app.find_or_start_by_path(Path(binary_path))
        app.resize(800, 600)
        app.enforce_size()
        if app.state == AppState.Launched:
            await asyncio.sleep(3)
        yield app


def pytest_runtest_makereport(item, call):
    # Check if the test raised an exception (failed)
    if call.excinfo is not None:
        print(f"Test {item.name} failed!")
        # take screenshot of the whole screen for debugging
        test_id = item.funcargs.get("test_id", "default")
        screenshot_dir = get_screenshot_dir(test_id)
        with PIL.ImageGrab.grab() as img:
            img.save(screenshot_dir / f"ERROR.png")
