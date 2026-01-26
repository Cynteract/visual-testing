from pathlib import Path


def get_screenshot_dir(test_id: str) -> Path:
    return Path.home() / "Documents" / "visual_testing" / "screenshots" / test_id
