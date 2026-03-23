import logging
import os
from pathlib import Path

import PIL.ImageGrab
import pytest
import pytest_asyncio

from robot.app import App
from robot.config import get_data_dir, get_frame_size
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
        app.resize_client_frame(*get_frame_size())
        app.enforce_size()
        yield app


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
