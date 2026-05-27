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

    async def run_commands(self, commands: list[str]):
        console_image = get_small_image_dir() / "home" / "assert_dev_console.png"
        await type_key("t", modifiers=[pynput.keyboard.Key.ctrl_l])
        # try to activate console if it doesn't open
        try:
            await assert_image(self.app, console_image, timeout=4)
        except TimeoutError:
            async with self.player_log_monitor.assert_line("Now using console"):
                # append space to workaround the apostrophe chars "`" behavior when it's pressed after an "e"
                await type_text("_$console ")
            await asyncio.sleep(0.05)
            await type_key("t", modifiers=[pynput.keyboard.Key.ctrl])
            await assert_image(self.app, console_image, timeout=4)

        # minimize and maximize to gain focus without using the mouse
        await type_key("`")
        await asyncio.sleep(0.05)
        await type_key("`")
        await asyncio.sleep(0.05)
        for command in commands:
            await type_text(command)
            await type_key(pynput.keyboard.Key.enter)
            await asyncio.sleep(0.05)
        await type_key("t", modifiers=[pynput.keyboard.Key.ctrl])
        await asyncio.sleep(0.05)
