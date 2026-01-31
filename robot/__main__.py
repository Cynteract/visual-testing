import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path

from robot.app import App
from robot.tests.login import LoginTest


@dataclass
class RobotArguments:
    binary_path: str | None
    username: str
    password: str
    test_id: str = "default"


async def main(args: RobotArguments):
    assert args.binary_path is not None, "Binary path must be provided"
    print(f"Starting tests with binary at {args.binary_path}")
    app_path = Path(args.binary_path)
    app = App(app_path)
    state = await app.open()
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
    parser = argparse.ArgumentParser(description="Run tests on Cynteract App.")
    parser.add_argument(
        "--binary-path",
        type=str,
        required=True,
        help="Path to the Cynteract App binary.",
    )
    parser.add_argument(
        "--username", type=str, required=True, help="Username for login."
    )
    parser.add_argument(
        "--password", type=str, required=True, help="Password for login."
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
