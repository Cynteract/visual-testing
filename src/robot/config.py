from pathlib import Path

from shared.utils import load_env_file


def get_builds_download_dir() -> Path:
    return Path.home() / "Documents" / "visual_testing" / "builds"


def get_screenshot_dir(test_id: str) -> Path:
    return Path.home() / "Documents" / "visual_testing" / "screenshots" / test_id


def get_small_image_dir() -> Path:
    return Path(__file__).parent / "tests" / "images"


env = load_env_file()

assert "ROBOT_USERNAME" in env, "ROBOT_USERNAME must be set in .env file"
assert "ROBOT_PASSWORD" in env, "ROBOT_PASSWORD must be set in .env file"

username = env["ROBOT_USERNAME"]
password = env["ROBOT_PASSWORD"]
