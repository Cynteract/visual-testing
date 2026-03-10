import asyncio
from enum import Enum

from robot.app import App
from robot.config import get_small_image_dir, password, username
from robot.timeout import Timeout
from robot.utils import click_image, left_click, type_text


class Pages(Enum):
    help = "help"
    home = "home"
    introduction = "introduction"
    login = "login"
    settings = "settings"
    startup = "startup"
    update = "update"
    please_connect = "please_connect"
    game_center = "game_center"
    # set of possible pages, depending on app state
    _next = "_next"


img_dir = get_small_image_dir()


async def detect_current_page(app: App, timeout: float = 2) -> Pages:
    timer = Timeout(
        timeout,
        f"Current page not detected within {timeout} seconds",
    )
    while True:
        with app.cached_screenshot():
            if app.locate(img_dir / "startup/assert_intro.png", confidence=0.95):
                return Pages.startup
            elif app.locate(img_dir / "startup/assert_update_now.png"):
                return Pages.update
            elif app.locate(img_dir / "home/assert_stats_label.png"):
                return Pages.home
            elif app.locate(img_dir / "login/assert_login_title.png"):
                return Pages.login
            elif app.locate(img_dir / "settings/assert_title.png"):
                return Pages.settings
            elif app.locate(img_dir / "introduction/assert_welcome_title.png"):
                return Pages.introduction
            elif app.locate(img_dir / "home/assert_please_connect_label.png"):
                return Pages.please_connect
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


async def go_to_page(app: App, target: Pages):
    current = await detect_current_page(app)
    while current != target:
        if target == Pages.login:
            if current == Pages.home:
                current = await transition(app, current, Pages.settings)
            elif current == Pages.settings:
                current = await transition(app, current, Pages.login)
            else:
                current = await transition(app, current, Pages._next)
        elif target == Pages.home:
            current = await transition(app, current, Pages._next)
        else:
            current = await transition(app, current, target)


async def transition(
    app, current: Pages, target: Pages, timeout: float | None = None
) -> Pages:
    tr = (current, target)
    if tr == (Pages.startup, Pages._next):
        await wait_for_page(app, Pages.update, timeout=5)
    elif tr == (Pages.update, Pages._next):
        await click_image(app, img_dir / "startup/click_no.png")
        await left_click()
    elif tr == (Pages.login, Pages._next):
        await click_image(app, img_dir / "login/click_login_link.png")
        await click_image(app, img_dir / "login/click_email.png")
        await type_text(username, interval=0.05)
        await click_image(app, img_dir / "login/click_password.png")
        await type_text(password, interval=0.05)
        await click_image(app, img_dir / "login/click_login_button.png")
        if timeout is None:
            timeout = 10.0
    elif tr == (Pages.settings, Pages.login):
        await click_image(app, img_dir / "settings/click_logout.png")
    elif tr == (Pages.home, Pages.settings):
        await click_image(app, img_dir / "home/click_settings.png")
    elif tr == (Pages.home, Pages.game_center):
        await click_image(app, img_dir / "home/click_game_center.png")
    elif tr == (Pages.please_connect, Pages._next):
        await click_image(app, img_dir / "click_back.png")
        # need to click twice because of a bug
        await left_click()
    else:
        raise Exception(f"No transition defined from {current} to {target}")

    if timeout is None:
        timeout = 4.0

    timer = Timeout(
        timeout,
        f"Failed to transition from {current} to {target} within {timeout} seconds",
    )
    next = current
    while next == current:
        timer.check()
        next = await detect_current_page(app)
    return next
