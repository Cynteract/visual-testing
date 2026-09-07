import asyncio
import os

from robot.app import App, WindowClosedException
from robot.config import get_small_image_dir, password, therapist_username, username
from robot.device_emulator import DeviceEmulator
from robot.pages import Pages, PageTags
from robot.state_machine import UIStateMachine
from robot.states import Games, UIState
from robot.timeout import Timeout
from robot.transitions import DefinedTransition
from robot.utils import click_image, scrollbar_scroll_until_visible, type_text


class Navigation:
    img_dir = get_small_image_dir()

    # maps each game to its label image in the game_center scrollable list
    # (tests/images/game_center/assert_*.png), used to scroll to and select it
    _game_center_labels: dict[Games, str] = {
        Games.sphere_runner: "game_center/assert_sphere_runner.png",
        Games.maze_escape: "game_center/assert_maze_escape.png",
        Games.tunnel_runner: "game_center/assert_tunnel_runner.png",
        Games.asteroid_storm: "game_center/assert_asteroid_storm.png",
        Games.jump_and_roll: "game_center/assert_jump_and_roll.png",
        Games.cannon_shot: "game_center/assert_cannon_shot.png",
        Games.brick_breaker: "game_center/assert_brick_breaker.png",
        Games.whack_a_blob: "game_center/assert_whack_a_blob.png",
        Games.weekly_test: "game_center/assert_weekly_test.png",
        Games.gravity_gambit: "game_center/assert_gravity_gambit.png",
        Games.highway_hazzard: "game_center/assert_highway_hazzard.png",
        Games.fruit_frenzy: "game_center/assert_fruit_frenzy.png",
    }

    # per-game in-gameplay assert image (tests/images/each_game/assert_*.png), used to
    # confirm arrival on that game's actual gameplay screen. Not yet captured for
    # tunnel_runner, asteroid_storm, or highway_hazzard - those 3 can be *selected* via
    # game_center but detect_current_page won't recognize their gameplay screen yet.
    _gameplay_asserts: dict[Games, str] = {
        # Games.maze_escape: "each_game/assert_mazegame.png",  # too generic (thin bar) - MultipleMatchesFoundException risk
        Games.fruit_frenzy: "each_game/assert_fruitfrenzy.png",
        # Games.cannon_shot: "each_game/assert_cannon_shot.png",  # too generic (repeating zigzag) - MultipleMatchesFoundException risk
        # Games.brick_breaker: "each_game/assert_brickbreaker.png",  # too generic (plain rectangles) - MultipleMatchesFoundException risk
        # Games.whack_a_blob: "each_game/assert_whackablob.png",  # too generic (plain dot) - MultipleMatchesFoundException risk
        # Games.gravity_gambit: "each_game/assert_gravitygambit.png",  # confirmed crash: MultipleMatchesFoundException (4 matches) - too generic (plain rounded-rect edge)
        # Games.jump_and_roll: "each_game/assert_jump_and_roll.png",  # too generic (dark/blurry) - MultipleMatchesFoundException risk
        # Games.weekly_test: "each_game/assert_weeklytest.png",  # wrong image entirely - shows "Trend" (an achievements tab), not weekly test's gameplay
    }

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
        self,
        relative_image_path: str,
        confidence: float | None = None,
        region: tuple[float, float, float, float] | None = None,
        timeout: int | None = None,
    ):
        await click_image(
            self.app,
            self.img_dir / relative_image_path,
            confidence=confidence,
            region=region,
            **({"timeout": timeout} if timeout is not None else {}),
        )

    async def _dismiss_please_connect_if_present(self):
        """Dismiss the 'please connect' overlay if it is covering the home screen.

        No-op (no error) when the overlay or its back button is absent, so the
        subsequent navigation proceeds regardless.
        """
        try:
            bbox = await self.locate("connect_device/assert_connect_title.png")
        except Exception:
            return
        if bbox is None:
            return
        try:
            await self.click_image("connect_device/click_back.png", timeout=3)
        except TimeoutError:
            pass

    async def detect_current_page(self, timeout: float | None = None) -> Pages:
        if timeout is None:
            uptime = self.app.uptime()
            if uptime is not None and uptime < 30.0:
                timeout = 15.0
            else:
                timeout = 2.0
        timer = Timeout(
            timeout,
            f"Current page not detected within {timeout} seconds",
        )
        detected_page = None
        while True:
            try:
                await self.app.ensure_window()
            except TimeoutError:
                timer.check()
                await asyncio.sleep(0.2)
                continue
            try:
                with self.app.cached_screenshot():
                    if await self.locate("startup/assert_intro.png", 0.95):
                        detected_page = Pages.startup
                    elif await self.locate("startup/assert_update_now.png", 0.95):
                        detected_page = Pages.update
                    elif await self.locate("home/assert_stats_label.png"):
                        detected_page = Pages.home
                    elif await self.locate("login/assert_login_title.png"):
                        detected_page = Pages.login
                    elif await self.locate("therapist/assert_therapist_page.png"):
                        detected_page = Pages.therapist_page
                    elif await self.locate("achievements/assert_achievements.png"):
                        detected_page = Pages.achievements
                    elif await self.locate("buddy/assert_buddy.png"):
                        detected_page = Pages.buddy_page
                    elif await self.locate("help_page/assert_help.png"):
                        detected_page = Pages.help_page
                    elif await self.locate("settings/assert_title.png"):
                        detected_page = Pages.settings
                    elif await self.locate("introduction/assert_welcome_title.png"):
                        detected_page = Pages.introduction
                    elif await self.locate("connect_device/assert_connect_title.png"):
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
                    elif (
                        await self.locate("sphere_runner/assert_score.png")
                        or await self.locate("each_game/assert_fruitfrenzy.png")
                        # the rest of each_game/assert_*.png are disabled - too generic
                        # (thin bars / plain dots / repeating patterns / blurry crops),
                        # confirmed to cause MultipleMatchesFoundException on unrelated
                        # screens since this check runs on every detect_current_page()
                        # call regardless of page. assert_weeklytest.png is additionally
                        # just the wrong image (shows "Trend", an achievements tab).
                        # Re-enable per-game once better crops are captured.
                    ):
                        detected_page = Pages.gameplay
                    elif await self.locate("game/assert_feedback_title.png"):
                        detected_page = Pages.feedback
            except (WindowClosedException, TimeoutError):
                timer.check()
                await asyncio.sleep(0.2)
                continue
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

    async def go_to_page(self, target: Pages, game: Games | None = None) -> None:
        await self.detect_current_page()
        current_page = self.state_machine.state.page
        visited_states = [self.state_machine.state]
        target_state = UIState(target, game) if game is not None else UIState(target)
        while current_page != target:
            new = await self.state_machine.go_towards(target_state)
            loop_detected = new in visited_states
            visited_states.append(new)
            if loop_detected:
                state_lines = [
                    f"* {state}" if state == new else f"  {state}"
                    for state in visited_states
                ]
                raise ValueError(
                    "Transition loop detected:\n" + "\n".join(state_lines)
                )
            current_page = new.page

    async def trigger_transition(self, target: Pages) -> None:
        """Trigger transition to other page without waiting for it to complete."""
        await self.detect_current_page()
        await self.state_machine.trigger_towards(UIState(target))

    async def _login_email_password(self, user: str):
        """Log in via the internal email/password form on the login screen."""
        # the login screen shows a "login with email and password" link first; clicking
        # it reveals the email/password inputs
        await self.click_image("login/click_login_link.png")
        await self.click_image("login/click_email.png")
        await type_text(user, interval=0.05)
        await self.click_image("login/click_password.png")
        await type_text(password, interval=0.05)
        await self.click_image("login/click_login_button.png")

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
            # app checks for an existing session ("Checking authentication...") before
            # showing the Sign In form directly - no separate login-link click needed
            # anymore, but the check can take longer than the default completion timeout
            if timeout is None:
                timeout = 15.0
        elif transition.matches(Pages.login, Pages.introduction):
            await self._login_email_password(username)
            if timeout is None:
                timeout = 40.0
        elif transition.matches(Pages.login, Pages.home):
            await self._login_email_password(username)
            if timeout is None:
                timeout = 40.0
        elif transition.matches(Pages.login, Pages.therapist_page):
            await self._login_email_password(therapist_username)
            if timeout is None:
                timeout = 40.0
        elif transition.matches(Pages.settings, Pages.home):
            await self.click_image("settings/click_back.png")
        elif transition.matches(Pages.settings, Pages.login):
            await self.click_image("settings/click_logout.png")
            # logout clears the session and navigates back to the Sign In screen, which
            # can take longer than the default completion timeout
            if timeout is None:
                timeout = 15.0
        elif transition.matches(Pages.home, Pages.settings):
            await self._dismiss_please_connect_if_present()
            await self.click_image("home/click_settings.png")
        elif transition.matches(Pages.home, Pages.achievements):
            await self._dismiss_please_connect_if_present()
            await self.click_image("home/click_achievements.png")
        elif transition.matches(Pages.achievements, Pages.home):
            await self.click_image("achievements/click_back.png")
        elif transition.matches(Pages.home, Pages.buddy_page):
            await self._dismiss_please_connect_if_present()
            await self.click_image("home/click_buddy.png")
        elif transition.matches(Pages.buddy_page, Pages.home):
            await self.click_image("buddy/click_back.png")
        elif transition.matches(Pages.home, Pages.help_page):
            await self._dismiss_please_connect_if_present()
            await self.click_image("home/click_help.png")
        elif transition.matches(Pages.help_page, Pages.home):
            await self.click_image("help_page/click_back.png")
        elif transition.matches(Pages.home, [Pages.please_connect, Pages.game_center]):
            await self.click_image("home/click_game_center.png")
        elif transition.matches(Pages.please_connect, Pages.home):
            await self.click_image("connect_device/click_back.png")
        elif transition.matches(Pages.position_selection, Pages.game_center):
            await self.click_image("position_selection/click_head.png", 0.95)
        elif transition.matches(Pages.movement_selection, Pages.calibrate):
            await self.click_image("movement_selection/click_head_down.png", 0.95)
        elif transition.matches(Pages.game_center, Pages.achievements):
            await self.click_image("game_center/click_achievement.png")
        elif transition.matches(Pages.game_center, Pages.position_selection):
            await self.click_image("game_center/click_back.png")
        elif transition.matches(Pages.game_center, Pages.movement_selection):
            target_game = transition.new.game
            assert target_game is not None and target_game != Games.no_game
            label_image = self._game_center_labels[target_game]
            # left pane = scrollable thumbnail list, right pane = focused game's name.
            # The mouse wheel freezes partway down, so drag the scrollbar thumb instead.
            bbox = await scrollbar_scroll_until_visible(
                self.app,
                self.img_dir / label_image,
                self.img_dir / "game_center" / "drag_scrollbar.png",
                confidence=0.8,
                target_region=(0.5, 0.0, 1.0, 1.0),
            )
            if bbox is None:
                # game not present in this build - skip instead of failing
                logging.info(f"Skipping {target_game.value}: not found in game center")
                return True
            await self.click_image("game_center/click_start_play.png")
            self.pending_game = target_game
        elif transition.matches(Pages.calibrate, Pages.gameplay):
            await self.device_emulator.turn_left()
            await self.click_image(
                "calibrate/click_confirm.png", region=(0.0, 0.0, 0.5, 1.0)
            )
            await self.device_emulator.turn_right()
            await self.click_image(
                "calibrate/click_confirm.png", region=(0.5, 0.0, 1.0, 1.0)
            )
            # an instruction popup appears after calibration - click play to begin the game
            await self.click_image("each_game/click_play.png", timeout=10)
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
