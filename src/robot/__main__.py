import argparse
import logging
from dataclasses import dataclass
from pathlib import Path

import pytest

from shared.utils import load_env_file


@dataclass
class RobotArguments:
    binary_path: str | None
    username: str
    password: str
    test_id: str = "default"


def main(args: RobotArguments):
    assert args.binary_path is not None, "Binary path must be provided"
    # run pytest
    logging.info(f"Start robot with binary {args.binary_path} .")
    pytest.main(
        [
            "-x",
            str(Path(__file__).parent / "tests"),
            "--username",
            args.username,
            "--password",
            args.password,
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
        "--username",
        type=str,
        required=env.get("USERNAME") is None,
        default=env.get("USERNAME"),
        help="Username for login.",
    )
    parser.add_argument(
        "--password",
        type=str,
        required=env.get("PASSWORD") is None,
        default=env.get("PASSWORD"),
        help="Password for login.",
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
        username=args.username,
        password=args.password,
        test_id=args.test_id,
    )
    main(arguments)
