from pathlib import Path


def get_builds_download_dir() -> Path:
    return Path.home() / "Documents" / "visual_testing" / "builds"


def get_screenshot_dir(test_id: str) -> Path:
    return Path.home() / "Documents" / "visual_testing" / "screenshots" / test_id


def get_small_image_dir() -> Path:
    return Path(__file__).parent / "tests" / "images"
