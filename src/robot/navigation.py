import asyncio
import os

from robot.app import App
from robot.config import get_small_image_dir, password, username
from robot.device_emulator import DeviceEmulator
from robot.pages import Pages, PageTags
from robot.state_machine import UIStateMachine
from robot.states import Games, UIState
from robot.timeout import Timeout
from robot.transitions import DefinedTransition
from robot.utils import click_image, left_click, type_text


class Navigation:
    img_dir = get_small_image_dir()

    def __init__(
        self,
        app: App,
        device_emulator: DeviceEmulator,
        state_machine: UIStateMachine,
    ):
        self.app = app
        self.device_emulator = device_emulator
        self.state_machine = state_machine
        self.pending_game: Games | None = None
        state_machine.register_transition_actions(self.page_actions)

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
                self.state_machine.update_page(detected_page)
                if detected_page.has(PageTags.game) and self.pending_game is not None:
                    self.state_machine.udpate_game(self.pending_game)
                    self.pending_game = None
                if not detected_page.has(PageTags.game):
                    self.state_machine.udpate_game(Games.no_game)
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
        await self.detect_current_page()
        current_page = self.state_machine.state.page
        while current_page != target:
            new = await self.state_machine.go_towards(UIState(target))
            current_page = new.page

    async def trigger_transition(self, target: Pages) -> None:
        """Trigger transition to other page without waiting for it to complete."""
        await self.detect_current_page()
        await self.state_machine.trigger_towards(UIState(target))

    async def page_actions(
        self,
        transition: DefinedTransition,
        wait_for_completion: bool = True,
        timeout: float | None = None,
    ) -> bool:
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
        elif transition.matches(Pages.position_selection, Pages.game_center):
            await self.click_image("position_selection/click_head.png", 0.95)
        elif transition.matches(Pages.movement_selection, Pages.calibrate):
            await self.click_image("movement_selection/click_head_down.png", 0.95)
        elif transition.matches(Pages.game_center, Pages.movement_selection):
            await self.click_image("sphere_runner/click_preview.png", 0.95)
            self.pending_game = Games.sphere_runner
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
        else:
            return False

        if timeout is None:
            timeout = 4.0

        if not wait_for_completion:
            return True

        timer = Timeout(
            timeout,
            f"Failed to fire {transition} within {timeout} seconds",
        )
        while self.state_machine.state.page == transition.old.page:
            timer.check()
            await self.detect_current_page()
        return True
