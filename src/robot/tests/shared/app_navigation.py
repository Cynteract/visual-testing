import asyncio
from enum import Enum

from robot.app import App
from robot.config import get_small_image_dir
from robot.timeout import Timeout
from robot.utils import click_image


class Pages(Enum):
    home = "home"
    login = "login"
    help = "help"
    settings = "settings"
    startup = "startup"


img_dir = get_small_image_dir()


async def detect_current_page(app: App, timeout: float = 2) -> Pages:
    timer = Timeout(
        timeout,
        f"Current page not detected within {timeout} seconds",
    )
    while True:
        if app.locate(img_dir / "startup/assert_intro.png", confidence=0.95):
            return Pages.startup
        elif app.locate(img_dir / "home/click_game_center.png"):
            return Pages.home
        elif app.locate(img_dir / "login/assert_login_title.png"):
            return Pages.login
        elif app.locate(img_dir / "settings/assert_title.png"):
            return Pages.settings
        timer.check()
        await asyncio.sleep(0.3)
    return Pages.unknown


async def wait_for_page(app: App, page: Pages, timeout: float = 5):
    timer = Timeout(
        timeout,
        f"Page {page} not detected within {timeout} seconds",
    )
    while True:
        try:
            current_page = await detect_current_page(app)
            if current_page == page:
                return
        except TimeoutError:
            pass
        timer.check()
        await asyncio.sleep(0.5)


async def go_to_page(app: App, page: Pages):
    current_page = await detect_current_page(app)
    if page == Pages.login:
        if current_page == Pages.home:
            await click_image(app, img_dir / "home/click_settings.png")
            await wait_for_page(app, Pages.settings)
            await go_to_page(app, Pages.login)
        elif current_page == Pages.settings:
            await click_image(app, img_dir / "settings/click_logout.png")
            await wait_for_page(app, Pages.login)
        elif page == Pages.startup:
            # reject app update
            await assert_image(
                app, img_dir / "startup/assert_update_now.png", timeout=5
            )
            await click_image(app, img_dir / "startup/click_no.png")

            # skip browser login if it is first start
            try:
                await click_image(app, img_dir / "login/click_cancel.png", timeout=5)
            except TimeoutError:
                pass
            await wait_for_page(app, Pages.login)
