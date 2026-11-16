"""Artifact isolation checks without launching the robot or contacting VRT."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from github_service import service
from robot import config, utils


class ArtifactTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patcher = patch.object(service, "get_data_dir", side_effect=lambda name: Path(self.temp.name) / name)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_diagnostics_are_not_visual_checkpoints(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(config, "get_data_dir", return_value=root):
                app = Mock()
                app.screenshot.side_effect = lambda path: path.write_bytes(b"image")
                await utils.screenshot(app, "home", "attempt")
                await utils.diagnostic_screenshot(app, "movement_failure", "attempt")
                await utils.diagnostic_screenshot(app, "before_restart", "attempt")
                self.assertEqual(
                    [p.name for p in config.get_screenshot_dir("attempt").glob("*.png")],
                    ["home.png"],
                )
                self.assertEqual(len(list((root / "diagnostics").glob("*.png"))), 2)

    async def test_successful_retry_uploads_only_its_own_attempt(self):
        instance = object.__new__(service.Service)
        instance.config = SimpleNamespace(robot_args=SimpleNamespace())
        instance.get_app_folder = AsyncMock(return_value=Path("build"))
        instance.upload_screenshots = AsyncMock(
            return_value=service.VRTTestResult(1, 0, 0, None)
        )
        with patch.object(service, "async_main", new_callable=AsyncMock) as run:
            run.side_effect = [RuntimeError("movement failed"), None]
            failed = await instance.run_commit_test("version", "branch")
            first_id = instance.config.robot_args.test_id
            instance.upload_screenshots.assert_not_awaited()
            passed = await instance.run_commit_test("version", "branch")
            second_id = instance.config.robot_args.test_id

        self.assertEqual(failed.test_status, service.CommitTestStatus.ROBOT_FAILURE)
        self.assertEqual(passed.test_status, service.CommitTestStatus.SUCCESS)
        self.assertNotEqual(first_id, second_id)
        instance.upload_screenshots.assert_awaited_once_with(
            "version", "branch", test_id=second_id
        )

    async def test_retry_policy_and_attempt_limit(self):
        from robot.results import RobotFailure

        for outcomes, expected, count, uploads in (
            ([None], service.CommitTestStatus.SUCCESS, 1, 1),
            ([RobotFailure("movement failed", retryable=True)] * 2 + [None], service.CommitTestStatus.ROBOT_FLAKY, 3, 1),
            ([RobotFailure("login timeout", retryable=True), None], service.CommitTestStatus.ROBOT_FLAKY, 2, 1),
            ([RobotFailure("login timeout", retryable=True)] * 3, service.CommitTestStatus.ROBOT_FAILURE, 3, 0),
            ([RobotFailure("assertion failed", retryable=True), None], service.CommitTestStatus.ROBOT_FLAKY, 2, 1),
            ([RobotFailure("movement failed", retryable=True)] * 3, service.CommitTestStatus.ROBOT_FAILURE, 3, 0),
            ([RobotFailure("fixture setup failed", retryable=True), None], service.CommitTestStatus.ROBOT_FLAKY, 2, 1),
            ([RuntimeError("cleanup failed")], service.CommitTestStatus.ROBOT_FAILURE, 1, 0),
        ):
            with self.subTest(expected=expected, count=count):
                instance = object.__new__(service.Service)
                instance.config = SimpleNamespace(robot_args=SimpleNamespace())
                instance.get_app_folder = AsyncMock(return_value=Path("build"))
                instance.upload_screenshots = AsyncMock(return_value=service.VRTTestResult(1, 0, 0, None))
                ids = []

                async def run(args):
                    ids.append(args.test_id)
                    self.assertTrue(args.close_app_after_tests)
                    error = outcomes[len(ids) - 1]
                    if error:
                        raise error

                with patch.object(service, "async_main", side_effect=run):
                    result = await instance.run_commit_test("version", "branch")
                self.assertEqual(result.test_status, expected)
                if expected == service.CommitTestStatus.ROBOT_FLAKY:
                    self.assertIn(f"({count} attempts)", result.details)
                self.assertEqual(len(ids), count)
                self.assertEqual(len(set(ids)), count)
                self.assertEqual(instance.upload_screenshots.await_count, uploads)
                summary = service.get_data_dir(ids[-1]).parent / "summary.html"
                self.assertTrue(summary.exists())
                if uploads:
                    self.assertEqual(instance.upload_screenshots.call_args.kwargs["test_id"], ids[-1])

    def test_all_test_failure_phases_are_retryable(self):
        from robot.results import AttemptEvidence, LoginTransitionTimeout

        for phase, error, expected in (
            ("call", LoginTransitionTimeout("login"), True),
            ("setup", LoginTransitionTimeout("login"), True),
            ("call", TimeoutError("other wait"), True),
            ("call", AssertionError("mismatch"), True),
            ("teardown", RuntimeError("fixture failed"), True),
        ):
            evidence = AttemptEvidence(Path(self.temp.name))
            evidence.pytest_runtest_makereport(
                SimpleNamespace(nodeid="test_login"),
                SimpleNamespace(when=phase, excinfo=SimpleNamespace(value=error), duration=40),
            )
            self.assertEqual(evidence.retryable, expected)
