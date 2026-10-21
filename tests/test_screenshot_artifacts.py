"""Artifact isolation checks without launching the robot or contacting VRT."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from github_service import service
from robot import config, utils


class ArtifactTests(unittest.IsolatedAsyncioTestCase):
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
