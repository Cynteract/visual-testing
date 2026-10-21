"""Startup regressions without launching apps or resetting user data."""

import os
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from robot import __main__ as runner
from robot.pages import Pages
from robot.tests import test_00_first_start as startup


class FirstStartTests(unittest.IsolatedAsyncioTestCase):
    async def test_restore_failure_stops_startup_before_launch(self):
        app = Mock()
        app.find_or_start_by_path = AsyncMock()
        events = []
        app.close.side_effect = lambda: events.append("close")

        def fail_restore():
            events.append("restore")
            raise RuntimeError("Fixture restore failed")

        with (
            patch.object(startup, "reset_app_state", side_effect=lambda: events.append("reset")),
            patch.object(startup, "reset_training_and_mood", side_effect=fail_restore),
        ):
            with self.assertRaisesRegex(RuntimeError, "Fixture restore failed"):
                await startup.test_first_start_login(app, Path("app.exe"), Mock(), "unit")
        self.assertEqual(events, ["close", "reset", "restore"])
        app.find_or_start_by_path.assert_not_awaited()

    async def run_startup(self, browser_error=None, app_error=None):
        app = Mock()
        app.find_or_start_by_path = AsyncMock()
        app.resize_client_frame = AsyncMock()
        navigation = Mock()
        navigation.wait_for_page = AsyncMock()
        navigation.trigger_transition = AsyncMock()
        with (
            patch.object(startup, "reset_app_state"),
            patch.object(startup, "reset_training_and_mood") as restore,
            patch.object(startup, "login_with_browser_cookie_absent", new_callable=AsyncMock) as login,
            patch.object(startup, "_assert_logged_in", new_callable=AsyncMock) as logged_in,
        ):
            login.side_effect = browser_error
            logged_in.side_effect = app_error
            await startup.test_first_start_login(app, Path("app.exe"), navigation, "unit")
            restore.assert_called_once()
            login.assert_awaited_once()
            logged_in.assert_awaited_once()
            navigation.wait_for_page.assert_awaited_once_with(Pages.update, timeout=15)

    async def test_browser_login_does_not_wait_for_legacy_app_login_page(self):
        await self.run_startup()

    async def test_cached_session_requires_confirmed_app_login(self):
        await self.run_startup(browser_error=TimeoutError("No browser form"))

    async def test_browser_failure_is_not_replaced_by_app_timeout(self):
        original = TimeoutError("Email field not found")
        with self.assertRaises(TimeoutError) as caught:
            await self.run_startup(original, TimeoutError("App not logged in"))
        self.assertIs(caught.exception, original)


class CaptureTests(unittest.TestCase):
    def test_windows_capture_and_debug_override(self):
        for debug, expected in ((False, "sys"), (True, "no")):
            with self.subTest(debug=debug), patch.dict(os.environ), patch.object(runner.AttemptEvidence, "save"), patch.object(runner.pytest, "main", return_value=0) as pytest_main:
                os.environ.pop("DEBUG", None)
                if debug:
                    os.environ["DEBUG"] = "1"
                runner.main(runner.RobotArguments("app.exe", close_app_after_tests=False))
                args = pytest_main.call_args.args[0]
                if os.name == "nt" or debug:
                    self.assertEqual(args[args.index("--capture") + 1], expected)
                else:
                    self.assertNotIn("--capture", args)
