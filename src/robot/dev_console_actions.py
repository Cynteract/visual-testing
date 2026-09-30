import asyncio

import pynput

from robot.app import App
from robot.config import get_small_image_dir
from robot.player_log_monitor import PlayerLogMonitor
from robot.utils import assert_image, type_key, type_text


class DevConsole:
    def __init__(self, app: App, player_log_monitor: PlayerLogMonitor):
        self.app = app
        self.player_log_monitor = player_log_monitor

    async def run_command(self, command: str):
        await self.run_commands([command])

    async def _open_console(self):
        console_image = get_small_image_dir() / "home" / "assert_dev_console.png"
        for attempt in range(3):
            await self.app.ensure_window()
            assert self.app.window is not None
            self.app.window.activate()
            await asyncio.sleep(0.2)
            # Do not toggle an already-open console closed.
            try:
                await assert_image(self.app, console_image, timeout=0.3)
                return
            except TimeoutError:
                pass
            await type_key("t", modifiers=[pynput.keyboard.Key.ctrl_l], hold=0.15)
            try:
                await assert_image(self.app, console_image, timeout=4)
                return
            except TimeoutError:
                if attempt == 2:
                    raise
            # Ctrl+T can restore a console that was previously minimized.
            await type_key("`", hold=0.15)
            try:
                await assert_image(self.app, console_image, timeout=1)
                return
            except TimeoutError:
                pass
            if attempt == 0:
                # Enable once; subsequent attempts only retry opening it.
                # The visible console is the readiness check, since activation
                # need not emit a new log entry when already enabled.
                await type_text("_$console ")
                await asyncio.sleep(0.2)

    async def run_commands(self, commands: list[str]):
        await self._open_console()

        # minimize and maximize to gain focus without using the mouse
        await type_key("`")
        await asyncio.sleep(0.05)
        await type_key("`")
        await asyncio.sleep(0.05)
        for command in commands:
            await type_text(command)
            await type_key(pynput.keyboard.Key.enter)
            await asyncio.sleep(0.05)
        await type_key("t", modifiers=[pynput.keyboard.Key.ctrl_l], hold=0.15)
        await asyncio.sleep(0.05)
