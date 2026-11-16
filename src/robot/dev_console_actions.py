import asyncio
import logging
import re

import cv2
import pynput

from robot.app import App
from robot.config import get_small_image_dir
from robot.player_log_monitor import PlayerLogMonitor
from robot.utils import assert_image, best_template_match, GAME_UI_SCALES, keyboard, mouse, type_key, type_text


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

    def _console_visible(self):
        template = cv2.imread(str(get_small_image_dir() / "home/assert_dev_console.png"), 0)
        frame = self.app._get_large_image().gray_image
        score, _ = best_template_match(frame[:int(frame.shape[0] * 0.2)], template, GAME_UI_SCALES)
        return score >= 0.9

    async def _focus_input(self):
        template = cv2.imread(str(get_small_image_dir() / "home/console_input_handle.png"), 0)
        for _ in range(10):
            frame = self.app._get_large_image().gray_image
            h, w = frame.shape
            offset = int(w * 0.9)
            score, box = best_template_match(frame[:, offset:], template, GAME_UI_SCALES)
            if box is not None and score >= 0.9:
                # The resize handle anchors the command bar's vertical position.
                # Click its empty middle, independent of placeholder text/font.
                left, top, _, _ = self.app._get_bounding_box()
                mouse.position = (left + w // 2, top + box[1] + box[3] // 2)
                mouse.click(pynput.mouse.Button.left)
                await asyncio.sleep(0.2)
                keyboard.press(pynput.keyboard.Key.ctrl_l)
                try:
                    await asyncio.sleep(0.1)
                    await type_key("a", hold=0.15)
                finally:
                    keyboard.release(pynput.keyboard.Key.ctrl_l)
                await asyncio.sleep(0.1)
                await type_key(pynput.keyboard.Key.backspace, hold=0.15)
                await asyncio.sleep(0.1)
                return
            await asyncio.sleep(0.2)
        raise TimeoutError("Could not locate the console command-bar handle")

    async def _close_console(self):
        for _ in range(3):
            if not self._console_visible():
                return
            await type_key("t", modifiers=[pynput.keyboard.Key.ctrl_l], hold=0.15)
            for _ in range(10):
                await asyncio.sleep(0.1)
                if not self._console_visible():
                    return
        raise TimeoutError("Developer console remained open after three close attempts")

    @staticmethod
    def _acknowledgement(command):
        if command == "strap":
            return "Emulator: connect strap"
        if command == "disconnect":
            return "Emulator: disconnect device"
        match = re.fullmatch(r"([+-]10)([xyz])", command)
        if match:
            return f"Emulator: rotate palm {match[1]} degrees around {match[2].upper()} axis"
        raise ValueError(f"No acknowledgement defined for console command {command!r}")

    async def run_commands(self, commands: list[str]):
        acknowledgements = [self._acknowledgement(command) for command in commands]
        await self._open_console()
        try:
            await self._focus_input()
            for command, acknowledgement in zip(commands, acknowledgements):
                # Never resend an incremental command after a missing acknowledgement.
                async with self.player_log_monitor.assert_line(acknowledgement, timeout=3):
                    await type_text(command)
                    await type_key(pynput.keyboard.Key.enter, hold=0.15)
        except BaseException:
            try:
                await self._close_console()
            except Exception:
                logging.exception("Console cleanup also failed")
            raise
        else:
            await self._close_console()
