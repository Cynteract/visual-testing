import asyncio
import subprocess
import time
from enum import Enum
from pathlib import Path

import cv2
import numpy
import PIL.ImageGrab
import psutil
import pywinctl


class MultipleMatchesFoundException(Exception):
    pass


class App:
    pid: int
    window: pywinctl.Window | None = None
    enforce_size_task: asyncio.Task | None = None
    requested_size: tuple[int, int] | None = None

    class State(Enum):
        Launching = "Launching"
        Running = "Running"

    def __init__(self, file_path: Path):
        self.file_path = file_path

    async def open(self) -> State:
        """
        Tries to open an app using the given file path and waits 1 second for it to be ready.
        If the app is already open, it is brought to the foreground.
        """
        # check if app is already running
        app_pid = None
        app_state = None
        for proc in psutil.process_iter(["pid", "exe"]):
            if proc.info["exe"] and Path(proc.info["exe"]) == self.file_path:
                app_pid = proc.info["pid"]
                break
        if app_pid is None:
            # start the app
            process = subprocess.Popen([str(self.file_path)])
            self.pid = process.pid
            app_state = self.State.Launching
        else:
            self.pid = app_pid
            app_state = self.State.Running
        self.window = await self.find_window()
        self.window.activate()
        return app_state

    async def find_window(self, timeout: float = 5) -> pywinctl.Window:
        """
        Waits for the app window to appear within the given number of seconds. Returns the window box when found.
        """
        if self.window:
            return self.window

        start_time = time.time()
        while True:
            for window in pywinctl.getAllWindows():
                if window.getPID() == self.pid:
                    self.window = window
                    return window
            if time.time() - start_time > timeout:
                raise TimeoutError(
                    f"App window for {self.file_path} did not appear within {timeout} seconds"
                )
            await asyncio.sleep(0.5)

    def resize(self, width, height):
        """
        Sets the size of the app window.
        """
        assert self.window, "App window is not available. Call open() first."
        self.window.resizeTo(width, height)

    def close(self):
        """
        Tries to close the app defined by this App instance, waits max 5 seconds for the app to no longer be running.
        """
        process = psutil.Process(self.pid)

        # cleanup
        if self.enforce_size_task:
            self.enforce_size_task.cancel()
            self.enforce_size_task = None

        # try to close the app gracefully first
        wait = False
        if self.window:
            self.window.close()
            wait = True
        if wait:
            for _ in range(5):
                if not process.is_running():
                    return
                time.sleep(1)

        # force terminate if still running
        if process.is_running():
            process.terminate()

    def enforce_size(self):
        """
        Brings the app window to the foreground and enforces it to be always on top.
        """
        assert self.window, "App window is not available. Call open() first."
        if not self.enforce_size_task:
            self.enforce_size_task = asyncio.create_task(self._enforce_size_routine())

    async def _enforce_size_routine(self):
        while True:
            if self.window:
                if self.window.isMinimized or self.window.isMaximized:
                    self.window.restore()
                if self.requested_size:
                    self.window.resizeTo(*self.requested_size)
                if self.window.position != (0, 0):
                    self.window.moveTo(0, 0)
            await asyncio.sleep(0.5)

    def screenshot(self, save_path: Path) -> None:
        """
        Takes a screenshot of the app window and saves it to the given path.
        """
        assert self.window, "App window is not available. Call open() first."
        with PIL.ImageGrab.grab() as img:
            img.save(save_path)

    def _get_bounding_box(self) -> tuple[int, int, int, int]:
        """
        Returns the bounding box of the app window.
        """
        assert self.window, "App window is not available. Call open() first."
        client_frame = self.window.getClientFrame()
        return (
            client_frame.left,
            client_frame.top,
            client_frame.right,
            client_frame.bottom,
        )

    def locate(
        self, small_image_path: Path, confidence: float = 0.8
    ) -> tuple[int, int, int, int] | None:
        """
        Locates the given image on the app window screenshot. Returns the bounding box if found, otherwise None.

        Returns: (x1, y1, x2, y2) of the found image on the screen or None
        """
        assert self.window, "App window is not available. Call open() first."
        bbox = self._get_bounding_box()

        # load images, cv2 uses numpy arrays in BGR format
        # grabbing window only does not work on all windows, see https://github.com/python-pillow/Pillow/pull/8516#issuecomment-3794640267
        with PIL.ImageGrab.grab(bbox=bbox) as window_grab:
            window_image = numpy.array(window_grab)
            large_image = cv2.cvtColor(window_image, cv2.COLOR_RGB2BGR)
        small_image = cv2.imread(small_image_path)
        assert (
            small_image is not None
        ), f"Could not load small image at {small_image_path}"
        assert (
            large_image.shape[0] >= small_image.shape[0]
        ), "small image width exceeds the large image width"
        assert (
            large_image.shape[1] >= small_image.shape[1]
        ), "small image height exceeds the large image height"

        # https://docs.opencv.org/4.13.0/d4/dc6/tutorial_py_template_matching.html
        match = cv2.matchTemplate(large_image, small_image, cv2.TM_CCOEFF_NORMED)
        yloc, xloc = numpy.where(match >= confidence)
        # cluster matches with a pixel distance < 3
        clustered_xloc: list[int] = []
        clustered_yloc: list[int] = []
        for x, y in zip(xloc, yloc):
            # if any existing clustered point is within 3 pixels, skip this point
            if any(
                abs(x - cx) < 3 and abs(y - cy) < 3
                for (cx, cy) in zip(clustered_xloc, clustered_yloc)
            ):
                continue
            clustered_xloc.append(x)
            clustered_yloc.append(y)
        if len(clustered_xloc) == 0:
            return None
        elif len(clustered_xloc) > 1:
            raise MultipleMatchesFoundException(
                f"Multiple ({len(clustered_xloc)}) matches found for image {small_image_path} with confidence {confidence}"
            )
        else:
            return (
                clustered_xloc[0] + bbox[0],
                clustered_yloc[0] + bbox[1],
                clustered_xloc[0] + bbox[0] + small_image.shape[1],
                clustered_yloc[0] + bbox[1] + small_image.shape[0],
            )
