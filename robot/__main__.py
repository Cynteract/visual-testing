import argparse
import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from robot.app import App
from robot.tests.login import LoginTest
from shared.utils import load_env_file


@dataclass
class RobotArguments:
    binary_path: str | None
    username: str
    password: str
    test_id: str = "default"


from .reset import reset_app_state, reset_player_data


async def main(args: RobotArguments):
    assert args.binary_path is not None, "Binary path must be provided"
    logging.info("Reset app state before starting tests.")
    reset_app_state()
    reset_player_data(args.username, args.password)
    logging.info(f"Start robot with binary {args.binary_path} .")
    app_path = Path(args.binary_path)
    app = App()
    state = await app.find_or_start_by_path(app_path)
    app.resize(800, 600)
    app.enforce_size()
    if state == App.State.Launching:
        # wait for app to finish launching
        await asyncio.sleep(10)
    else:
        # wait for app to come to foreground
        await asyncio.sleep(1)
    test = LoginTest(app)
    await test.runTest(args.username, args.password, args.test_id)


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
    asyncio.run(main(arguments))
