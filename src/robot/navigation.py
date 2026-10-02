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
from robot.utils import (
    GAME_UI_SCALES,
    best_template_match,
    click_image,
    match_best_image,
    scrollbar_drag_step,
    scrollbar_scroll_until_visible,
    type_text,
)


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

    # per-game movement-select click image. Default (head down) covers most games.
    _movement_select_clicks: dict[Games, str] = {
        Games.brick_breaker: "movement_selection/click_head_leftright.png",
    }
    _movement_select_default = "movement_selection/click_head_down.png"

    # games that need TWO movement-select + calibration cycles before play:
    # (first movement, second movement). The second is always up/down.
    _two_cycle_movements: dict[Games, tuple[str, str]] = {
        Games.maze_escape: (
            "movement_selection/click_head_tilt.png",
            "movement_selection/click_up_down.png",
        ),
        Games.asteroid_storm: (
            "movement_selection/click_head_leftright.png",
            "movement_selection/click_up_down.png",
        ),
        Games.jump_and_roll: (
            "movement_selection/click_head_leftright.png",
            "movement_selection/click_up_down.png",
        ),
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
        # learned click positions (client-relative), captured from the first game
        # (sphere_runner) and reused for all subsequent games
        self._menu_center: tuple[int, int] | None = None
        self._home_center: tuple[int, int] | None = None
        self._game_center_center: tuple[int, int] | None = None
        state_machine.register_transition_actions(self.page_actions)

    async def locate(
        self, relative_image_path: str, confidence: float | None = None
    ) -> tuple[int, int, int, int] | None:
        return await self.app.locate(self.img_dir / relative_image_path, confidence)

    async def locate_max(
        self,
        relative_image_path: str,
        confidence: float = 0.8,
        region: tuple[float, float, float, float] | None = None,
    ) -> tuple[int, int, int, int] | None:
        """Return the bbox of the best (max) match, bypassing app.locate's clustering
        guards that reject good matches with >20 above-threshold pixels."""
        import cv2

        target = cv2.imread(str(self.img_dir / relative_image_path), cv2.IMREAD_GRAYSCALE)
        if target is None:
            return None
        cached = getattr(self.app, "cached_large_image", None)
        large = (
            cached.gray_image
            if cached is not None
            else self.app._get_large_image().gray_image
        )
        h, w = large.shape
        if region is not None:
            rx0 = int(w * region[0])
            ry0 = int(h * region[1])
            rx1 = int(w * region[2])
            ry1 = int(h * region[3])
        else:
            rx0, ry0, rx1, ry1 = 0, 0, w, h
        region_img = large[ry0:ry1, rx0:rx1]
        from robot.utils import foreground_template
        target, foreground_range = foreground_template(
            self.img_dir / relative_image_path, target,
            relative_image_path in ("game/click_home.png", "game/click_menu.png"),
        )
        if foreground_range is not None:
            region_img = cv2.inRange(region_img, *foreground_range)
        scales = GAME_UI_SCALES if relative_image_path.startswith(("game/", "each_game/")) else (1.0,)
        maxval, box = best_template_match(region_img, target, scales)
        if box is None or maxval < confidence:
            return None
        win = self.app._get_bounding_box()
        return (
            win[0] + rx0 + box[0],
            win[1] + ry0 + box[1],
            win[0] + rx0 + box[0] + box[2],
            win[1] + ry0 + box[1] + box[3],
        )

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

    async def click_image_max(
        self,
        relative_image_path: str,
        confidence: float = 0.8,
        region: tuple[float, float, float, float] | None = None,
        timeout: float = 5.0,
    ):
        from robot.utils import click_image_max as _click_image_max

        await _click_image_max(
            self.app,
            self.img_dir / relative_image_path,
            confidence=confidence,
            region=region,
            timeout=timeout,
            scales=GAME_UI_SCALES if relative_image_path.startswith(("game/", "each_game/")) else (1.0,),
            foreground_only=relative_image_path in ("game/click_home.png", "game/click_menu.png"),
        )

    async def click_at(self, x: int, y: int):
        """Click at a client-relative coordinate within the app window."""
        import pynput

        win = self.app._get_bounding_box()
        ctrl = pynput.mouse.Controller()
        ctrl.position = (win[0] + x, win[1] + y)
        ctrl.click(pynput.mouse.Button.left, 1)
        await asyncio.sleep(0.2)

    async def _click_or_learn(
        self,
        image: str,
        confidence: float,
        region: tuple[float, float, float, float] | None,
        attr: str,
    ):
        """Click `image`; on first success capture its client-relative center into
        `attr` and reuse that fixed position for every subsequent call."""
        center = getattr(self, attr)
        if center is None:
            bbox = await self.locate_max(image, confidence, region=region)
            if bbox is None:
                raise TimeoutError(f"Image {image} not found on screen")
            win = self.app._get_bounding_box()
            center = (
                (bbox[0] + bbox[2]) // 2 - win[0],
                (bbox[1] + bbox[3]) // 2 - win[1],
            )
            setattr(self, attr, center)
        await self.click_at(*center)

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

    async def _calibrate_once(self):
        """Run one calibration cycle: rotate left, confirm, rotate right, confirm."""
        await self.device_emulator.turn_left()
        await self.click_image(
            "calibrate/click_confirm.png", region=(0.0, 0.0, 0.5, 1.0)
        )
        await self.device_emulator.turn_right()
        await self.click_image(
            "calibrate/click_confirm.png", region=(0.5, 0.0, 1.0, 1.0)
        )

    async def _detect_focused_game(self) -> Games | None:
        """Return the game whose name label currently matches the game_center right pane."""
        games = list(self._game_center_labels.keys())
        paths = [self.img_dir / label for label in self._game_center_labels.values()]
        result = await match_best_image(self.app, paths, region=(0.5, 0.0, 1.0, 1.0))
        if result is None:
            return None
        return games[result[0]]

    async def discover_game_center_order(self) -> list[Games]:
        """Scroll the game_center list top-to-bottom and return the games in visual order.

        Assumes the game_center page is showing with the list reset to the top. Games not
        present for the current device (e.g. cannon_shot on strap) are simply absent from
        the returned order.
        """
        order: list[Games] = []
        timer = Timeout(
            60.0,
            "Could not discover the game_center order within 60 seconds",
        )
        while True:
            focused = await self._detect_focused_game()
            if focused is not None and (not order or order[-1] != focused):
                order.append(focused)
            if order:
                moved = await scrollbar_drag_step(
                    self.app,
                    self.img_dir / "game_center" / "drag_scrollbar.png",
                    step=15,
                )
                if not moved:
                    break
            else:
                # right pane has not settled on a game yet - wait before scrolling
                await asyncio.sleep(0.5)
            timer.check()
        return order

    async def reset_game_center_scroll(self, top_game: Games | None = None):
        """Scroll upward in place and verify the first discovered game is selected."""
        if top_game is None:
            raise ValueError("The first discovered game is required to verify reset")
        await self.go_to_page(Pages.game_center)
        timer = Timeout(30.0, f"Could not reset game list to {top_game.value}")
        while True:
            timer.check()
            moved = await scrollbar_drag_step(
                self.app,
                self.img_dir / "game_center" / "drag_scrollbar.png",
                step=30,
                direction=-1,
            )
            if not moved and await self._detect_focused_game() == top_game:
                return

    async def detect_current_page(self, timeout: float | None = None) -> Pages:
        if timeout is None:
            uptime = self.app.uptime()
            if uptime is not None and uptime < 30.0:
                timeout = 15.0
            else:
                timeout = 10.0
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
                    if await self.locate_max("home/assert_reward_title.png", 0.9):
                        await self.click_image_max("home/click_collect.png", confidence=0.9)
                        timer.check()
                        await asyncio.sleep(0.3)
                        continue
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
                    elif await self.locate_max(
                        "each_game/assert_weeklytest_results.png", 0.9,
                        region=(0.4, 0.05, 0.9, 0.25),
                    ):
                        detected_page = Pages.weekly_results
                    elif self.state_machine.state.game == Games.weekly_test:
                        # Weekly Test's inactive shared HUD remains faintly visible
                        # behind its panels. Only its own Cancel button proves it ran.
                        if await self.locate_max(
                            "each_game/click_weeklytest_cancel.png", 0.9,
                            region=(0, 0.8, 1, 1),
                        ):
                            detected_page = Pages.gameplay
                    elif await self.locate_max("game/assert_pause_title.png", 0.85):
                        detected_page = Pages.pause_menu
                    elif (
                        await self.locate_max(
                            "game/assert_fruit_frenzy_pause_title.png", 0.9,
                            region=(0.1, 0.15, 0.9, 0.85),
                        )
                        and await self.locate_max(
                            "game/click_fruit_frenzy_home.png", 0.9,
                            region=(0.1, 0.15, 0.9, 0.85),
                        )
                    ):
                        detected_page = Pages.pause_menu
                    elif await self.locate_max(
                        "game/click_menu.png", 0.85,
                        region=(0.5, 0.0, 1.0, 0.2),
                    ):
                        detected_page = Pages.gameplay
                    elif await self.locate_max(
                        "game/assert_score.png",
                        0.85,
                        region=(0.0, 0.0, 1.0, 0.5),
                    ):
                        detected_page = Pages.gameplay
                    elif await self.locate_max(
                        "game/assert_fruit_frenzy_score.png", 0.9,
                        region=(0.0, 0.0, 1.0, 0.2),
                    ):
                        detected_page = Pages.gameplay
                    elif await self.locate_max("game/assert_feedback_title.png", 0.9):
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
        elif transition.matches(Pages.introduction, Pages.home):
            # first-time onboarding: enter -> skip blob -> name -> confirm
            await self.click_image("introduction/click_enter.png")
            await self.click_image("introduction/click_skip.png", timeout=10)
            await self.click_image("introduction/click_name_field.png")
            await type_text("visualTesting", interval=0.05)
            await self.click_image("introduction/click_confirm.png")
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
            # let the home screen settle after quitting a game
            await asyncio.sleep(2)
            await self._click_or_learn(
                "home/click_game_center.png", 0.5, None, "_game_center_center"
            )
            # loading the game_center thumbnail list can exceed the default 4s
            if timeout is None:
                timeout = 10.0
        elif transition.matches(Pages.please_connect, Pages.home):
            await self.click_image("connect_device/click_back.png")
        elif transition.matches(Pages.position_selection, Pages.game_center):
            await self.click_image("position_selection/click_head.png", 0.95)
        elif transition.matches(Pages.movement_selection, Pages.weekly_results):
            await self.click_image(self._movement_select_default, 0.95)
        elif transition.matches(Pages.weekly_results, Pages.calibrate):
            restart = "each_game/click_weeklytest_restart_test.png"
            start = restart if await self.locate_max(restart, 0.9, region=(0.3, 0.85, 0.7, 1)) else "each_game/click_weeklytest_start_test.png"
            await self.click_image_max(
                start, confidence=0.9,
                region=(0.3, 0.85, 0.7, 1),
            )
        elif transition.matches(Pages.gameplay, Pages.weekly_results):
            await self.click_image_max(
                "each_game/click_weeklytest_cancel.png", confidence=0.9,
                region=(0, 0.8, 1, 1),
            )
        elif transition.matches(Pages.weekly_results, Pages.movement_selection):
            await self.click_image_max(
                "each_game/click_weeklytest_back.png", confidence=0.9,
                region=(0, 0, 0.3, 0.2),
            )
        elif transition.matches(Pages.movement_selection, Pages.game_center):
            await self.click_image_max("movement_selection/click_back.png", confidence=0.9, region=(0, 0, 0.3, 0.2))
        elif transition.matches(Pages.movement_selection, Pages.calibrate):
            game = transition.old.game
            two_cycle = self._two_cycle_movements.get(game)
            if two_cycle is not None:
                first, second = two_cycle
                await self.click_image(first, 0.95)
                await self._calibrate_once()
                await self.click_image(second, 0.95)
                await self._calibrate_once()
                await self.click_image_max(
                    "each_game/click_play.png", confidence=0.75, timeout=10
                )
                await self.device_emulator.reset_rotation()
            else:
                click = self._movement_select_clicks.get(
                    game, self._movement_select_default
                )
                await self.click_image(click, 0.95)
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
                # game not present for the strap device - skip it
                return True
            await self.click_image("game_center/click_start_play.png")
            self.pending_game = target_game
        elif transition.matches(Pages.calibrate, Pages.gameplay):
            await self._calibrate_once()
            # an instruction popup appears after calibration - click play to begin the game
            if transition.old.game != Games.weekly_test:
                await self.click_image_max(
                    "each_game/click_play.png", confidence=0.75, timeout=10
                )
            elif timeout is None:
                timeout = 10.0  # Weekly Test starts automatically after its countdown.
            # calibration left the device rotated "right" - return it to center so the
            # game starts neutral instead of carrying that leftover rotation
            await self.device_emulator.reset_rotation()
        elif transition.matches(PageTags.game, Pages.pause_menu):
            menu_image = "game/click_menu.png"
            await self.click_image_max(menu_image, confidence=0.85, region=(0.5, 0, 1, 0.2))
        elif transition.matches(Pages.pause_menu, Pages.home):
            home_image = "game/click_home.png"
            await self.click_image_max(
                home_image, confidence=0.85, region=(0.1, 0.15, 0.9, 0.85), timeout=10
            )
        elif transition.matches(Pages.feedback, Pages.home):
            await self.click_image_max("game/click_feedback_confirm.png", confidence=0.9)
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
