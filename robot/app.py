import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import cv2
import numpy
import PIL.ImageGrab
import psutil
import pywinctl
import win32gui


class MultipleMatchesFoundException(Exception):
    pass


@dataclass
class WindowMatcher:
    pid: int | None = None
    title: str | None = None
    class_name: str | None = None


class App:
    pid: int | None = None
    window_matcher: WindowMatcher | None = None
    window: pywinctl.Window | None = None
    enforce_size_task: asyncio.Task | None = None
    requested_size: tuple[int, int] | None = None
    file_path: Path | None = None

    class State(Enum):
        Launching = "Launching"
        Running = "Running"

    class _Timeout:
        def __init__(self, timeout: float, error_message: str):
            self.timeout = timeout
            self.error_message = error_message
            self.start_time = time.time()

        def check(self):
            if time.time() - self.start_time > self.timeout:
                raise TimeoutError(self.error_message)

    async def find_by_window(self, window_matcher: WindowMatcher, timeout: float = 5):
        """
        Finds a running app window by matching the window title with the given string. Sets self.pid and self.window when found.
        """
        self.window_matcher = window_matcher
        await self._find_window(timeout=timeout)
        assert self.window
        self.window.activate()

    async def find_or_start_by_path(self, path: Path) -> State:
        """
        Tries to open an app using the given file path and waits 5 seconds for it to be ready.
        If the app is already open, it is brought to the foreground.
        """
        self.file_path = path

        # check if app is already running
        try:
            await self._find_process(timeout=0)
        except TimeoutError:
            pass

        if self.pid is None:
            # start the app
            logging.info(f"Start app {self.file_path} .")
            process = subprocess.Popen([str(self.file_path)])
            self.pid = process.pid
            app_state = self.State.Launching
        else:
            app_state = self.State.Running

        self.window_matcher = WindowMatcher(pid=self.pid)
        await self._find_window()
        assert self.window
        self.window.activate()
        return app_state

    async def _find_process(self, timeout: float = 5):
        """
        Waits for a running process with the app file path to appear within the given number of seconds. Sets self.pid when found.
        """
        timer = self._Timeout(
            timeout,
            f"No running process found for app {self.file_path} within {timeout} seconds",
        )
        while self.pid is None:
            for proc in psutil.process_iter(["pid", "exe"]):
                if proc.info["exe"] and Path(proc.info["exe"]) == self.file_path:
                    self.pid = proc.info["pid"]
            if self.pid is None:
                timer.check()
                await asyncio.sleep(0.5)

    async def _find_window(self, timeout: float = 5):
        """
        Waits for the app window to appear within the given number of seconds. Sets self.window when found.
        """
        assert (
            self.window_matcher is not None
        ), "Either pid or window_matcher must be set to find the app window"
        timer = self._Timeout(
            timeout,
            f"No app window found for {self.file_path} within {timeout} seconds",
        )
        while self.window is None:
            for window in pywinctl.getAllWindows():
                is_ok = True
                _pid = self.window_matcher.pid
                _title = self.window_matcher.title
                _class_name = self.window_matcher.class_name
                if _pid is not None and window.getPID() != _pid:
                    is_ok = False
                elif _title is not None and _title != window.title:
                    is_ok = False
                elif _class_name is not None:
                    hwnd = window.getHandle()
                    class_name = win32gui.GetClassName(hwnd)
                    if class_name != _class_name:
                        is_ok = False
                if is_ok:
                    self.window = window
            if self.window is None:
                timer.check()
                await asyncio.sleep(0.5)

    def resize(self, width, height):
        """
        Sets the size of the app window.
        """
        assert self.window, "App window is not available. Call open() first."
        self.requested_size = (width, height)
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
        bbox = self._get_bounding_box()
        with PIL.ImageGrab.grab(bbox=bbox) as img:
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
            # if any existing clustered point is within 4 pixels, skip this point
            if any(
                abs(x - cx) < 4 and abs(y - cy) < 4
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
