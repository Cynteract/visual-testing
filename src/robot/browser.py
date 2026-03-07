import enum
import logging
import shutil
import winreg
from pathlib import Path

import plyvel

from robot.app import WindowMatcher


class DefaultBrowser(enum.Enum):
    CHROME = "Chrome"
    FIREFOX = "Firefox"
    EDGE = "Edge"


def detect_default_browser() -> DefaultBrowser:
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoiceLatest\ProgId",
    )
    prog_id = winreg.QueryValueEx(key, "ProgId")[0]
    winreg.CloseKey(key)

    if "ChromeHTML" in prog_id:
        return DefaultBrowser.CHROME
    elif "FirefoxURL" in prog_id:
        return DefaultBrowser.FIREFOX
    else:
        return DefaultBrowser.EDGE


def has_local_storage(domain: str):
    browser = detect_default_browser()
    if browser == DefaultBrowser.CHROME:
        db_path = (
            Path.home()
            / "AppData/Local/Google/Chrome/User Data/Default/Local Storage/leveldb"
        )
        db = plyvel.DB(str(db_path))
        for key, _ in db:
            decoded_key = key.decode("utf-8")
            if decoded_key.startswith(f"_https://{domain}"):
                return True
        return False


def delete_local_storage(domain: str):
    browser = detect_default_browser()
    if browser == DefaultBrowser.CHROME:
        db_path = (
            Path.home()
            / "AppData/Local/Google/Chrome/User Data/Default/Local Storage/leveldb"
        )
        db = plyvel.DB(str(db_path))
        for key, _ in db:
            decoded_key = key.decode("utf-8")
            if decoded_key.startswith(f"_https://{domain}"):
                logging.info(
                    f"Deleting Chrome local storage key {decoded_key} for domain {domain}"
                )
                db.delete(key)
        db.close()
    elif browser == DefaultBrowser.FIREFOX:
        profiles_path = Path.home() / "AppData/Roaming/Mozilla/Firefox/Profiles"
        for path in profiles_path.glob(
            f"*.default-release/storage/default/https+++{domain}"
        ):
            if path.is_dir():
                logging.info(f"Deleting Firefox local storage at {path}")
                shutil.rmtree(path)


def get_browser_window_matcher(website_title: str) -> WindowMatcher:
    browser = detect_default_browser()
    if browser == DefaultBrowser.CHROME:
        return WindowMatcher(title=website_title, class_name="Chrome_WidgetWin_1")
    elif browser == DefaultBrowser.FIREFOX:
        return WindowMatcher(
            title=f"{website_title} — Mozilla Firefox", class_name="MozillaWindowClass"
        )
    else:
        raise ValueError(f"Unsupported browser for login: {browser}")
