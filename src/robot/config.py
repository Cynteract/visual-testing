from pathlib import Path

from shared.utils import load_env_file


def get_data_dir(test_id: str) -> Path:
    return Path.home() / "Documents" / "visual_testing" / test_id


def get_screenshot_dir(test_id: str) -> Path:
    return get_data_dir(test_id) / "screenshots"


def get_small_image_dir() -> Path:
    return Path(__file__).parent / "tests" / "images"


def get_frame_size() -> tuple[int, int]:
    # Cynteract app allows aspect ratios between 4:3 and 21:9 for window size, not considering window decorations.
    # Window decorations can vary between theme and screen scaling.
    # We need some padding to the limiting aspect ratios to avoid the app's force rescaling.
    return (850, 600)


env = load_env_file()

assert "ROBOT_USERNAME" in env, "ROBOT_USERNAME must be set in .env file"
assert "ROBOT_PASSWORD" in env, "ROBOT_PASSWORD must be set in .env file"

username = env["ROBOT_USERNAME"]
password = env["ROBOT_PASSWORD"]
