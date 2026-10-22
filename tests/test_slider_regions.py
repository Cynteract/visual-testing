import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw

from github_service import service
from github_service.slider_regions import SLIDER_BOUNDS, slider_ignore_areas


class SliderRegionTests(unittest.TestCase):
    def test_masks_leave_exactly_the_complete_slider_rectangle(self):
        for game, (left, top, right, bottom) in SLIDER_BOUNDS.items():
            for direction in ("left", "right"):
                mask = Image.new("L", (850, 600), 255)
                draw = ImageDraw.Draw(mask)
                for area in slider_ignore_areas(f"{game}_far_{direction}", mask.size):
                    draw.rectangle((area.x, area.y, area.x + area.width - 1,
                                    area.y + area.height - 1), fill=0)
                self.assertEqual(mask.getbbox(), (left, top, right, bottom))
                self.assertEqual(mask.histogram()[255], (right - left) * (bottom - top))

    def test_unrelated_checkpoints_and_unknown_layouts(self):
        self.assertIsNone(slider_ignore_areas("home", (850, 600)))
        with self.assertRaises(ValueError):
            slider_ignore_areas("new_game_far_left", (850, 600))
        with self.assertRaises(ValueError):
            slider_ignore_areas("sphere_runner_far_left", (1700, 1200))


class SliderUploadTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_keeps_full_image_and_masks_only_movement(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ("home", "sphere_runner_far_left"):
                Image.new("RGB", (850, 600)).save(Path(folder) / f"{name}.png")
            instance = object.__new__(service.Service)
            instance.config = SimpleNamespace(vrt_api_url="unused", vrt_api_key="unused",
                                              vrt_frontend_url="unused")
            vrt = Mock(projectId="project", buildId="build")
            vrt.track.return_value.testRunResponse.status = service.types.TestRunStatus.OK
            with patch.object(service, "get_screenshot_dir", return_value=Path(folder)), \
                 patch.object(service, "VisualRegressionTracker") as tracker:
                tracker.return_value.__enter__.return_value = vrt
                await instance.upload_screenshots("version", "branch", test_id="attempt")
            runs = {call.args[0].name: call.args[0] for call in vrt.track.call_args_list}
            self.assertIsNone(runs["home"].ignoreAreas)
            self.assertEqual(runs["home"].diffTollerancePercent, 0.2)
            movement = runs["sphere_runner_far_left"]
            self.assertEqual(len(movement.ignoreAreas), 4)
            self.assertEqual(movement.diffTollerancePercent, 0)
            import base64
            self.assertEqual(base64.b64decode(movement.imageBase64),
                             (Path(folder) / "sphere_runner_far_left.png").read_bytes())
