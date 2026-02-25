import asyncio
from pathlib import Path

import pynput

from robot.app import App, WindowMatcher
from robot.utils import assert_image, click_image, screenshot, type_key, type_text


async def browser_login_test(username: str, password: str, test_id: str):
    IMGDIR = Path("robot/tests/images/chrome")

    browser_binary = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
    browser = App()
    window_matcher = WindowMatcher(title="Cynteract", class_name="Chrome_WidgetWin_1")
    await browser.find_by_window(window_matcher)
    browser.resize(800, 600)
    browser.enforce_size()

    await screenshot(browser, "browser_sign_in_page", test_id)
    await click_image(browser, IMGDIR / "enter_email.png", timeout=5)
    await type_text(username, interval=0.05)
    # cancel any password manager popups
    await type_key(pynput.keyboard.Key.esc)
    await click_image(browser, IMGDIR / "enter_password.png", timeout=1)
    await type_text(password, interval=0.05)
    await click_image(browser, IMGDIR / "click_sign_in.png", timeout=1)
    await asyncio.sleep(0.1)
    await screenshot(browser, "browser_signing_in", test_id)
    await assert_image(browser, IMGDIR / "assert_sign_in_success.png", timeout=10)
