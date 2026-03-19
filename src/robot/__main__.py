import argparse
import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

import pytest

from robot.app import AppState
from robot.config import get_data_dir
from shared.utils import load_env_file


@dataclass
class RobotArguments:
    binary_path: str | None
    test_id: str = "default"
    close_app_after_tests: bool = True


async def async_main(args: RobotArguments):
    # avoid RuntimeError: Cannot run the event loop while another loop is running
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, main, args)


def main(args: RobotArguments):
    assert args.binary_path is not None, "Binary path must be provided"
    # run pytest
    logging.info(f"Start robot with binary {args.binary_path} .")
    exit_code = pytest.main(
        [
            "-x",
            str(Path(__file__).parent / "tests"),
            "--test-id",
            args.test_id,
            "--binary-path",
            args.binary_path,
            "--html",
            str(get_data_dir(args.test_id) / "report.html"),
        ]
    )
    if args.close_app_after_tests:
        from robot.app import App

        async def close_app():
            assert args.binary_path is not None
            async with App() as app:
                await app.find_by_path(Path(args.binary_path), timeout=5)
                if app.state == AppState.Grabbed:
                    logging.info("Closing app after tests.")
                    app.close()

        asyncio.run(close_app())
    if exit_code != 0:
        exit_code_name = pytest.ExitCode(exit_code).name
        raise RuntimeError(f"Tests failed with exit code {exit_code_name}.")


if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s %(message)s", level=logging.INFO)

    env = load_env_file()

    argparser = argparse.ArgumentParser(description="Run tests on Cynteract App.")
    argparser.add_argument(
        "--binary-path",
        type=str,
        required=env.get("BINARY_PATH") is None,
        default=env.get("BINARY_PATH"),
        help="Path to the Cynteract App binary.",
    )
    argparser.add_argument(
        "--test-id",
        type=str,
        required=False,
        default=RobotArguments.test_id,
        help="Test ID for screenshots.",
    )
    args = argparser.parse_args()

    arguments = RobotArguments(
        binary_path=args.binary_path,
        test_id=args.test_id,
        close_app_after_tests=False,
    )
    main(arguments)
