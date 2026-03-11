import argparse
import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

import pytest

from shared.utils import load_env_file


@dataclass
class RobotArguments:
    binary_path: str | None
    test_id: str = "default"


async def async_main(args: RobotArguments):
    # avoid RuntimeError: Cannot run the event loop while another loop is running
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, main, args)


def main(args: RobotArguments):
    assert args.binary_path is not None, "Binary path must be provided"
    # run pytest
    logging.info(f"Start robot with binary {args.binary_path} .")
    pytest.main(
        [
            "-x",
            str(Path(__file__).parent / "tests"),
            "--test-id",
            args.test_id,
            "--binary-path",
            args.binary_path,
        ]
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    env = load_env_file()
    parser = argparse.ArgumentParser(description="Run tests on Cynteract App.")
    parser.add_argument(
        "--binary-path",
        type=str,
        required=env.get("BINARY_PATH") is None,
        default=env.get("BINARY_PATH"),
        help="Path to the Cynteract App binary.",
    )
    parser.add_argument(
        "--test-id",
        type=str,
        required=False,
        default="default",
        help="Test ID for screenshots.",
    )
    args = parser.parse_args()
    arguments = RobotArguments(
        binary_path=args.binary_path,
        test_id=args.test_id,
    )
    main(arguments)
