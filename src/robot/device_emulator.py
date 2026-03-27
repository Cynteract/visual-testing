import asyncio
from enum import Enum
from typing import Callable

from pynput.keyboard import Controller


class DeviceTypes(Enum):
    not_connected = "not_connected"
    strap = "strap"


class DeviceEmulator:
    def __init__(
        self,
        keyboard: Controller,
        on_device_change: Callable[[DeviceTypes], None],
    ):
        self.keyboard: Controller = keyboard
        self.device_type: DeviceTypes | None = None
        self.rotation: int = 0
        self.on_device_change = on_device_change

    async def connect(self, device_name: str):
        await self._type_text("_$" + device_name)
        self.device_type = DeviceTypes.strap
        self.rotation = 0
        self.on_device_change(self.device_type)

    async def disconnect(self):
        await self._type_text("_$disconnect")
        self.device_type = DeviceTypes.not_connected
        self.rotation = 0
        self.on_device_change(self.device_type)

    async def turn_left(self):
        while self.rotation >= 0:
            await self._type_text("_$rxn")
            self.rotation -= 1

    async def turn_far_left(self):
        while self.rotation >= -1:
            await self._type_text("_$rxn")
            self.rotation -= 1

    async def turn_right(self):
        while self.rotation <= 0:
            await self._type_text("_$rxn")
            self.rotation += 1

    async def turn_far_right(self):
        while self.rotation <= 1:
            await self._type_text("_$rxn")
            self.rotation += 1

    async def _type_text(self, text: str):
        interval = 0.05
        for char in text:
            self.keyboard.press(char)
            self.keyboard.release(char)
            await asyncio.sleep(interval)
