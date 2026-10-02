import asyncio
import enum
import logging
import shutil
import winreg
from pathlib import Path

import plyvel
import psutil
import pywinctl

from robot.app import WindowMatcher, title_matches
from robot.timeout import Timeout


class DefaultBrowser(enum.Enum):
    CHROME = "Chrome"
    FIREFOX = "Firefox"
    EDGE = "Edge"
    BRAVE = "Brave"


# map a browser process name to its browser type. Process names are ground truth and
# don't depend on the (sometimes stale) Windows default-browser registry.
BROWSER_BY_PROCESS = {
    "chrome.exe": DefaultBrowser.CHROME,
    "msedge.exe": DefaultBrowser.EDGE,
    "brave.exe": DefaultBrowser.BRAVE,
    "firefox.exe": DefaultBrowser.FIREFOX,
}


def browser_type_of(window) -> DefaultBrowser | None:
    try:
        return BROWSER_BY_PROCESS.get(psutil.Process(window.getPID()).name().lower())
    except Exception:
        return None


async def find_browser_window(
    website_title: str, timeout: float = 15.0
) -> tuple[pywinctl.Window, DefaultBrowser]:
    """Primary detection: find the browser window showing the website.

    Matches by the window's process (a known browser) plus a tight title match, so it
    works regardless of what the Windows default-browser registry claims.
    """
    timer = Timeout(
        timeout,
        f"No browser window found for {website_title} within {timeout} seconds",
    )
    while True:
        for window in pywinctl.getAllWindows():
            browser = browser_type_of(window)
            if browser is None:
                continue
            if title_matches(window.title, website_title):
                return window, browser
        timer.check()
        await asyncio.sleep(0.5)


def detect_default_browser() -> DefaultBrowser:
    """Fallback detection: read the Windows default-browser registry.

    Mirrors the app: the standard ``UserChoice`` key first, the legacy
    ``UserChoiceLatest`` key as a fallback, without throwing when either is missing.
    """
    prog_id = _read_prog_id(
        r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
    )
    if prog_id is None:
        prog_id = _read_prog_id(
            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoiceLatest"
        )

    if prog_id is None:
        return DefaultBrowser.EDGE
    if "ChromeHTML" in prog_id:
        return DefaultBrowser.CHROME
    elif "FirefoxURL" in prog_id:
        return DefaultBrowser.FIREFOX
    elif "MSEdgeHTM" in prog_id:
        return DefaultBrowser.EDGE
    elif "BraveHTML" in prog_id:
        return DefaultBrowser.BRAVE
    else:
        return DefaultBrowser.EDGE


def _read_prog_id(key_path: str) -> str | None:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
        try:
            prog_id, _ = winreg.QueryValueEx(key, "ProgId")
            return prog_id
        finally:
            winreg.CloseKey(key)
    except OSError:
        return None


def delete_local_storage(domain: str):
    # delete the domain's local storage from every supported browser. The app can use a
    # different browser than the registry default, so clearing them all guarantees the
    # session is actually removed regardless of which one held it.
    leveldb_dirs = [
        (
            "Chrome",
            Path.home()
            / "AppData/Local/Google/Chrome/User Data/Default/Local Storage/leveldb",
        ),
        (
            "Edge",
            Path.home()
            / "AppData/Local/Microsoft/Edge/User Data/Default/Local Storage/leveldb",
        ),
        (
            "Brave",
            Path.home()
            / "AppData/Local/BraveSoftware/Brave-Browser/User Data/Default/Local Storage/leveldb",
        ),
    ]
    for name, db_path in leveldb_dirs:
        try:
            db = plyvel.DB(str(db_path))
            for key, _ in db:
                decoded_key = key.decode("utf-8", "ignore")
                if decoded_key.startswith(f"_https://{domain}"):
                    logging.info(
                        f"Deleting {name} local storage key {decoded_key} for domain {domain}"
                    )
                    db.delete(key)
            db.close()
        except Exception as e:
            # a missing or running browser (leveldb LOCK) should not stop the others
            logging.info(f"Skipping {name} local storage: {e}")

    # Firefox stores per-origin data in directories, not leveldb
    profiles_path = Path.home() / "AppData/Roaming/Mozilla/Firefox/Profiles"
    for path in profiles_path.glob(
        f"*.default-release/storage/default/https+++{domain}"
    ):
        if path.is_dir():
            logging.info(f"Deleting Firefox local storage at {path}")
            shutil.rmtree(path)


def get_browser_window_matcher(website_title: str) -> WindowMatcher:
    browser = detect_default_browser()
    if browser in (DefaultBrowser.CHROME, DefaultBrowser.EDGE, DefaultBrowser.BRAVE):
        return WindowMatcher(title=website_title, class_name="Chrome_WidgetWin_1")
    elif browser == DefaultBrowser.FIREFOX:
        return WindowMatcher(
            title=f"{website_title} — Mozilla Firefox", class_name="MozillaWindowClass"
        )
    else:
        raise ValueError(f"Unsupported browser for login: {browser}")
