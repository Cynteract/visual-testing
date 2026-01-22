import asyncio
import subprocess
import time
from enum import Enum
from pathlib import Path

import psutil
import pywinctl


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
            await asyncio.sleep(1)
