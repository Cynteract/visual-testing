import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

import cv2
import numpy
import PIL.ImageGrab
import psutil
import pywinctl
import win32gui
from cv2.typing import MatLike

from robot.timeout import Timeout


class MultipleMatchesFoundException(Exception):
    pass


@dataclass
class WindowMatcher:
    pid: int | None = None
    title: str | None = None
    class_name: str | None = None


class AppState(Enum):
    Uninitialized = "Uninitialized"
    Launched = "Launched"
    Grabbed = "Grabbed"
    Closed = "Closed"


class App:
    pid: int | None = None
    window_matcher: WindowMatcher | None = None
    window: pywinctl.Window | None = None
    enforce_size_task: asyncio.Task | None = None
    requested_client_frame_size: tuple[int, int] | None = None
    resize_offsets: tuple[int, int] = (0, 0)
    file_path: Path | None = None
    state: AppState = AppState.Uninitialized
    debug_dir: Path | None = None

    @dataclass
    class ImageCache:
        gray_image: MatLike

    cached_large_image: ImageCache | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.enforce_size_task:
            self.enforce_size_task.cancel()
            try:
                await self.enforce_size_task
            except asyncio.CancelledError:
                pass

    async def find_by_window(self, window_matcher: WindowMatcher, timeout: float = 5):
        """
        Finds a running app window by matching the window title with the given string. Sets self.pid and self.window when found.
        """
        self.window_matcher = window_matcher
        await self._find_window(timeout=timeout)
        assert self.window
        self.window.activate()

    async def find_by_path(self, path: Path, timeout: float = 5):
        """
        Tries to find a running app by matching the process executable path with the given path. Sets self.pid and self.window when found.
        """
        self.file_path = path
        await self._find_process(timeout=timeout)
        self.state = AppState.Grabbed

    async def find_or_start_by_path(self, path: Path):
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
            self.state = AppState.Launched
            window_timeout = 15.0
        else:
            self.state = AppState.Grabbed
            window_timeout = 5.0

        self.window_matcher = WindowMatcher(pid=self.pid)
        await self._find_window(timeout=window_timeout)
        assert self.window
        self.window.activate()

    async def _find_process(self, timeout: float = 5):
        """
        Waits for a running process with the app file path to appear within the given number of seconds. Sets self.pid when found.
        """
        timer = Timeout(
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

    async def _find_window(self, timeout: float):
        """
        Waits for the app window to appear within the given number of seconds. Sets self.window when found.
        """
        assert (
            self.window_matcher is not None
        ), "Either pid or window_matcher must be set to find the app window"
        timer = Timeout(
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

    def resize_client_frame(self, width, height):
        """
        Sets the size of the app window.
        """
        assert self.window, "App window is not available. Call open() first."
        self.requested_client_frame_size = (width, height)
        self._enforce_size_once()

    def close(self, timeout: float = 5):
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

        timer = Timeout(
            timeout, f"App with pid {self.pid} did not close within {timeout} seconds"
        )
        while process.is_running():
            timer.check()
            time.sleep(0.5)

        self.state = AppState.Closed
        self.pid = None

    def enforce_size(self):
        """
        Brings the app window to the foreground and enforces it to be always on top.
        """
        assert self.window, "App window is not available. Call open() first."
        if not self.enforce_size_task:
            self.enforce_size_task = asyncio.create_task(self._enforce_size_routine())

    def _enforce_size_once(self):
        assert self.window, "App window is not available. Call open() first."
        if self.window.isMinimized or self.window.isMaximized:
            # set window to floating state
            self.window.restore()
        if self.requested_client_frame_size:
            # resize window
            frame = self.window.getClientFrame()
            frame_size = (frame.right - frame.left, frame.bottom - frame.top)
            if self.requested_client_frame_size != frame_size:
                self.window.resizeTo(
                    self.requested_client_frame_size[0] + self.resize_offsets[0],
                    self.requested_client_frame_size[1] + self.resize_offsets[1],
                    wait=True,
                )
            self._update_resize_offsets()
        if self.window.position != (0, 0):
            # place window at top left corner
            self.window.moveTo(0, 0)

    def _update_resize_offsets(self) -> bool:
        assert self.window and self.requested_client_frame_size
        frame = self.window.getClientFrame()
        frame_size = (frame.right - frame.left, frame.bottom - frame.top)
        new_offsets = (
            self.requested_client_frame_size[0]
            - frame_size[0]
            + self.resize_offsets[0],
            self.requested_client_frame_size[1]
            - frame_size[1]
            + self.resize_offsets[1],
        )
        if new_offsets != self.resize_offsets:
            logging.info(f"Update offsets from {self.resize_offsets} to {new_offsets}")
            self.resize_offsets = new_offsets
            return True
        return False

    async def _enforce_size_routine(self):
        try:
            while True:
                if self.window:
                    self._enforce_size_once()
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass

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

    def _get_large_image(self) -> ImageCache:
        bbox = self._get_bounding_box()
        # load images, cv2 uses numpy arrays in BGR format
        # grabbing window only does not work on all windows, see https://github.com/python-pillow/Pillow/pull/8516#issuecomment-3794640267
        with PIL.ImageGrab.grab(bbox=bbox) as window_grab:
            if self.debug_dir is not None:
                image_grab_dir = self.debug_dir / "image_grab"
                image_grab_dir.mkdir(parents=True, exist_ok=True)
                timestamp = (
                    datetime.now().isoformat(timespec="milliseconds").replace(":", "-")
                )
                window_grab.save(image_grab_dir / f"screenshot_{timestamp}.png")
            window_image = numpy.array(window_grab)
            # convert to grayscale
            gray_image = cv2.cvtColor(window_image, cv2.COLOR_RGB2GRAY)
            return self.ImageCache(gray_image=gray_image)

    def _get_small_image(self, path: Path) -> ImageCache:
        image = cv2.imread(str(path))
        assert image is not None, f"Could not load small image at {path}"
        gray_image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        return self.ImageCache(gray_image=gray_image)

    class _CachedScreenshot:
        def __init__(self, app: "App"):
            self.app = app

        def __enter__(self):
            self.app.cached_large_image = self.app._get_large_image()
            return self.app.cached_large_image

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.app.cached_large_image = None

    def cached_screenshot(self) -> _CachedScreenshot:
        return self._CachedScreenshot(self)

    def _debug_save_images(
        self,
        target_dir: Path,
        small_image: ImageCache,
        large_image: ImageCache,
    ):
        target_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(target_dir / f"small.png"), small_image.gray_image)
        cv2.imwrite(str(target_dir / f"large.png"), large_image.gray_image)

    def locate(
        self, small_image_path: Path, confidence: float = 0.8
    ) -> tuple[int, int, int, int] | None:
        """
        Locates the given image on the app window screenshot. Returns the bounding box if found, otherwise None.

        Returns: (x1, y1, x2, y2) of the found image on the screen or None
        """
        assert self.window, "App window is not available. Call open() first."
        if self.debug_dir is not None:
            timestamp = (
                datetime.now().isoformat(timespec="milliseconds").replace(":", "-")
            )
            debug_save_dir = (
                self.debug_dir / "matches" / f"{timestamp}_{small_image_path.stem}"
            )
        else:
            debug_save_dir = None

        bbox = self._get_bounding_box()

        # enforce size before taking screenshot
        if self.enforce_size_task != None and self.window.isMaximized:
            self._enforce_size_once()

        if self.cached_large_image is not None:
            large_image = self.cached_large_image
        else:
            large_image = self._get_large_image()
        small_image = self._get_small_image(small_image_path)
        assert (
            large_image.gray_image.shape[0] >= small_image.gray_image.shape[0]
        ), "small image width exceeds the large image width"
        assert (
            large_image.gray_image.shape[1] >= small_image.gray_image.shape[1]
        ), "small image height exceeds the large image height"
        if debug_save_dir is not None:
            self._debug_save_images(debug_save_dir, small_image, large_image)

        # https://docs.opencv.org/4.13.0/d4/dc6/tutorial_py_template_matching.html
        match = cv2.matchTemplate(
            large_image.gray_image, small_image.gray_image, cv2.TM_CCOEFF_NORMED
        )
        yloc, xloc = numpy.where(match >= confidence)
        if len(xloc) == 0:
            return None
        if len(xloc) > 20:
            raise MultipleMatchesFoundException(
                f"Too many ({len(xloc)}) matches found for image {small_image_path} with confidence {confidence}"
            )
        # cluster matches with a pixel distance < 4
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
        if len(clustered_xloc) > 1:
            raise MultipleMatchesFoundException(
                f"Multiple ({len(clustered_xloc)}) matches found for image {small_image_path} with confidence {confidence}"
            )
        else:
            return (
                clustered_xloc[0] + bbox[0],
                clustered_yloc[0] + bbox[1],
                clustered_xloc[0] + bbox[0] + small_image.gray_image.shape[1],
                clustered_yloc[0] + bbox[1] + small_image.gray_image.shape[0],
            )
