import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from robot.tests import test_smoke as smoke
from robot.pages import Pages
from robot.states import Games


class PauseMovementTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_short_round_games_pause_around_commands(self):
        for game in (Games.brick_breaker, Games.asteroid_storm, Games.maze_escape):
            events = []
            nav = SimpleNamespace(
                go_to_page=AsyncMock(side_effect=lambda page: events.append(("go", page))),
                wait_for_page=AsyncMock(side_effect=lambda page: events.append(("wait", page))),
            )
            turn = AsyncMock(side_effect=lambda: events.append("turn"))
            with patch.object(smoke, "type_key", new_callable=AsyncMock) as key:
                key.side_effect = lambda *args, **kwargs: events.append("resume")
                await smoke.send_movement(game, nav, turn)
            expected = ["turn"] if game == Games.maze_escape else [
                ("go", Pages.pause_menu), "turn", ("wait", Pages.pause_menu),
                "resume", ("wait", Pages.gameplay),
            ]
            self.assertEqual(events, expected)

    async def test_command_failure_does_not_resume_game(self):
        nav = SimpleNamespace(go_to_page=AsyncMock(), wait_for_page=AsyncMock())
        turn = AsyncMock(side_effect=RuntimeError("command failed"))
        with patch.object(smoke, "type_key", new_callable=AsyncMock) as key:
            with self.assertRaisesRegex(RuntimeError, "command failed"):
                await smoke.send_movement(Games.brick_breaker, nav, turn)
            key.assert_not_awaited()


class FailureCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_fixture_skips_navigation_but_success_disconnects(self):
        from robot.device_emulator import DeviceEmulator
        from robot.device_types import DeviceTypes
        from unittest.mock import Mock

        for failed in (True, False):
            machine = Mock()
            machine.state = Mock(device=DeviceTypes.strap)
            machine.go_towards = AsyncMock(side_effect=lambda target: setattr(
                machine, "state", Mock(device=DeviceTypes.not_connected)))
            emulator = DeviceEmulator(Mock(), machine, Mock())
            emulator.device_type = DeviceTypes.strap
            emulator.skip_cleanup = failed
            await emulator.__aexit__(None, None, None)
            self.assertEqual(machine.go_towards.await_count, 0 if failed else 1)
