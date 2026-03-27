import asyncio
import os
from collections.abc import Callable

from robot.app import App
from robot.config import get_small_image_dir, password, username
from robot.device_emulator import DeviceEmulator, DeviceTypes
from robot.tests.shared.pages import Pages, PageTags
from robot.tests.shared.transitions import DefinedTransition
from robot.tests.shared.ui_state import DefinedUIState, Games, UIState
from robot.timeout import Timeout
from robot.utils import click_image, left_click, type_text


class Navigation:
    img_dir = get_small_image_dir()

    def __init__(
        self,
        app: App,
        device_emulator: DeviceEmulator,
        on_page_change: Callable[[Pages], None],
        on_game_start: Callable[[Games], None],
        get_next_transition: Callable[[UIState], DefinedTransition],
        has_state_changed: Callable[[DefinedUIState], bool],
    ):
        self.app = app
        self.device_emulator = device_emulator
        self.on_page_change = on_page_change
        self.on_game_start = on_game_start
        self.get_next_transition = get_next_transition
        self.has_state_changed = has_state_changed

    async def locate(
        self, relative_image_path: str, confidence: float | None = None
    ) -> tuple[int, int, int, int] | None:
        return await self.app.locate(self.img_dir / relative_image_path, confidence)

    async def click_image(
        self, relative_image_path: str, confidence: float | None = None
    ):
        await click_image(
            self.app, self.img_dir / relative_image_path, confidence=confidence
        )

    async def detect_current_page(self, timeout: float = 2) -> Pages:
        timer = Timeout(
            timeout,
            f"Current page not detected within {timeout} seconds",
        )
        detected_page = None
        while True:
            with self.app.cached_screenshot():
                if await self.locate("startup/assert_intro.png", 0.95):
                    detected_page = Pages.startup
                elif await self.locate("startup/assert_update_now.png", 0.95):
                    detected_page = Pages.update
                elif await self.locate("home/assert_stats_label.png"):
                    detected_page = Pages.home
                elif await self.locate("login/assert_login_title.png"):
                    detected_page = Pages.login
                elif await self.locate("settings/assert_title.png"):
                    detected_page = Pages.settings
                elif await self.locate("introduction/assert_welcome_title.png"):
                    detected_page = Pages.introduction
                elif await self.locate("home/assert_please_connect_label.png"):
                    detected_page = Pages.please_connect
                elif await self.locate("position_selection/assert_title.png"):
                    detected_page = Pages.position_selection
                elif await self.locate("game_center/assert_title.png"):
                    detected_page = Pages.game_center
                elif await self.locate("movement_selection/assert_title.png"):
                    detected_page = Pages.movement_selection
                elif await self.locate("calibrate/assert_title.png"):
                    detected_page = Pages.calibrate
                elif await self.locate("game/assert_pause_title.png"):
                    detected_page = Pages.pause_menu
                elif await self.locate("sphere_runner/assert_score.png"):
                    detected_page = Pages.gameplay
                elif await self.locate("game/assert_feedback_title.png"):
                    detected_page = Pages.feedback
            if detected_page is not None:
                if os.environ.get("DEBUG"):
                    print(f"Detected page: {detected_page}")
                self.on_page_change(detected_page)
                return detected_page
            timer.check()
            await asyncio.sleep(0.2)

    async def wait_for_page(self, page: Pages, timeout: float = 5):
        timer = Timeout(
            timeout,
            f"Page {page} not detected within {timeout} seconds",
        )
        while True:
            try:
                current_page = await self.detect_current_page()
                if current_page == page:
                    return
            except TimeoutError:
                pass
            timer.check()
            await asyncio.sleep(0.5)

    async def go_to_page(self, target: Pages) -> None:
        current = await self.detect_current_page()
        while current != target:
            transition = self.get_next_transition(UIState(target))
            current = await self.fire_transition(transition)

    async def trigger_transition(self, target: Pages) -> None:
        """Trigger transition to other page without waiting for it to complete."""
        current = await self.detect_current_page()
        transition = self.get_next_transition(UIState(target))
        await self.fire_transition(transition, wait_for_transition=False)

    async def fire_transition(
        self,
        transition: DefinedTransition,
        wait_for_transition: bool = True,
        timeout: float | None = None,
    ) -> Pages:
        if transition.matches(Pages.startup, Pages.update):
            await self.wait_for_page(Pages.update, timeout=5)
        elif transition.matches(Pages.update, Pages.login):
            await self.click_image("startup/click_no.png")
            await left_click()
            # next thing could be auto login
            if timeout is None:
                timeout = 10.0
        elif transition.matches(Pages.login, Pages.introduction):
            await self.click_image("login/click_login_link.png")
            await self.click_image("login/click_email.png")
            await type_text(username, interval=0.05)
            await self.click_image("login/click_password.png")
            await type_text(password, interval=0.05)
            await self.click_image("login/click_login_button.png")
            if timeout is None:
                timeout = 10.0
        elif transition.matches(Pages.settings, Pages.home):
            await self.click_image("settings/click_back.png")
        elif transition.matches(Pages.settings, Pages.login):
            await self.click_image("settings/click_logout.png")
        elif transition.matches(Pages.home, Pages.settings):
            await self.click_image("home/click_settings.png")
        elif transition.matches(Pages.home, [Pages.please_connect, Pages.game_center]):
            await self.click_image("home/click_game_center.png")
        elif transition.matches(Pages.please_connect, Pages.home):
            await self.click_image("home/click_back.png")
        elif transition.matches(Pages.please_connect, DeviceTypes.strap):
            await self.device_emulator.connect("strap")
        elif transition.matches(Pages.position_selection, Pages.game_center):
            await self.click_image("position_selection/click_head.png", 0.95)
        elif transition.matches(Pages.movement_selection, Pages.calibrate):
            await self.click_image("movement_selection/click_head_down.png", 0.95)
        elif transition.matches(Pages.game_center, Pages.movement_selection):
            await self.click_image("sphere_runner/click_preview.png", 0.95)
            self.on_game_start(Games.sphere_runner)
        elif transition.matches(Pages.calibrate, Pages.gameplay):
            await self.device_emulator.turn_left()
            await self.click_image("calibrate/click_confirm.png", 0.7)
            await self.device_emulator.turn_right()
            await self.click_image("calibrate/click_confirm.png", 0.7)
        elif transition.matches(PageTags.game, Pages.pause_menu):
            await self.click_image("game/click_menu.png")
        elif transition.matches(Pages.pause_menu, Pages.home):
            await self.click_image("game/click_home.png")
        elif transition.matches(Pages.feedback, Pages.game_center):
            await self.click_image("game/click_feedback_confirm.png")
        elif transition.matches(PageTags.device_connected, Pages.please_connect):
            await self.device_emulator.disconnect()
        elif transition.matches(DeviceTypes.not_connected, DeviceTypes.strap):
            await self.device_emulator.connect("strap")
        elif transition.matches(DeviceTypes.strap, DeviceTypes.not_connected):
            await self.device_emulator.disconnect()
        else:
            raise Exception(f"No action defined for {transition}")

        if timeout is None:
            timeout = 4.0

        new_page = transition.old.page
        if not wait_for_transition:
            return new_page

        timer = Timeout(
            timeout,
            f"Failed to fire {transition} within {timeout} seconds",
        )
        while not self.has_state_changed(transition.old):
            timer.check()
            new_page = await self.detect_current_page()
        return new_page
