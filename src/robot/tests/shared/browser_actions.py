import asyncio
import os

import pynput

from robot.app import App
from robot.browser import get_browser_window_matcher
from robot.config import get_data_dir, get_frame_size, get_small_image_dir
from robot.utils import assert_image, click_image, screenshot, type_key, type_text


async def login_with_browser_cookie_absent(username: str, password: str, test_id: str):
    window_matcher = get_browser_window_matcher("Cynteract")

    async with App() as browser:
        if os.environ.get("DEBUG") is not None:
            browser.debug_dir = get_data_dir(test_id="debug")
        # browsers and websites are screen-scale aware; the pixel-patches need to match the scale
        await browser.find_by_window(window_matcher)
        scale = browser.get_screen_scale()
        if scale == 100:
            frame_size = get_frame_size()
            img_dir = get_small_image_dir() / "browser" / "100"
        elif scale == 150:
            frame_size = tuple(int(dim * 1.5) for dim in get_frame_size())
            img_dir = get_small_image_dir() / "browser" / "150"
        else:
            raise ValueError(f"Unsupported screen scale: {scale}%")
        await browser.resize_client_frame(*frame_size)
        browser.enforce_size()

        # lower confidence than default for cross-browser compatibility
        confidence = 0.8

        await assert_image(
            browser, img_dir / "enter_email.png", timeout=5, confidence=confidence
        )
        await screenshot(browser, "browser_sign_in", test_id)
        await click_image(
            browser, img_dir / "enter_email.png", timeout=1, confidence=confidence
        )
        await type_text(username, interval=0.05)
        # cancel any password manager popups
        await type_key(pynput.keyboard.Key.esc)
        await click_image(
            browser, img_dir / "enter_password.png", timeout=1, confidence=confidence
        )
        await type_text(password, interval=0.05)
        await click_image(
            browser, img_dir / "click_sign_in.png", timeout=1, confidence=confidence
        )
        await asyncio.sleep(0.1)
        await screenshot(browser, "browser_signing_in", test_id)
        # await assert_image(browser, img_dir / "assert_sign_in_success.png", timeout=10, confidence=confidence)
