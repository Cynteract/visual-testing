import asyncio

import pynput

from robot.app import App
from robot.browser import get_browser_window_matcher
from robot.config import get_small_image_dir
from robot.utils import assert_image, click_image, screenshot, type_key, type_text


async def browser_login_cookie_absent(username: str, password: str, test_id: str):
    img_dir = get_small_image_dir() / "browser"
    window_matcher = get_browser_window_matcher("Cynteract")

    async with App() as browser:
        await browser.find_by_window(window_matcher)
        browser.resize(800, 600)
        browser.enforce_size()

        await screenshot(browser, "browser_sign_in_page", test_id)
        await click_image(browser, img_dir / "enter_email.png", timeout=5)
        await type_text(username, interval=0.05)
        # cancel any password manager popups
        await type_key(pynput.keyboard.Key.esc)
        await click_image(browser, img_dir / "enter_password.png", timeout=1)
        await type_text(password, interval=0.05)
        await click_image(browser, img_dir / "click_sign_in.png", timeout=1)
        await asyncio.sleep(0.1)
        await screenshot(browser, "browser_signing_in", test_id)
        await assert_image(browser, img_dir / "assert_sign_in_success.png", timeout=10)
