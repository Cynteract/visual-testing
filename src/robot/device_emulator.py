import asyncio

from pynput.keyboard import Controller

from robot.device_types import DeviceTypes
from robot.state_machine import UIStateMachine
from robot.states import UIState
from robot.transitions import DefinedTransition


class DeviceEmulator:
    def __init__(
        self,
        keyboard: Controller,
        state_machine: UIStateMachine,
    ):
        self.keyboard: Controller = keyboard
        self.device_type: DeviceTypes | None = None
        self.rotation: int = 0
        self.state_machine = state_machine
        state_machine.register_transition_actions(self.device_actions)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.device_type is not None:
            # the page might change after the disconnect
            await self.state_machine.go_towards(UIState(DeviceTypes.not_connected))

    async def connect(self, device_name: str):
        await self._type_text("_$" + device_name)
        self.device_type = DeviceTypes.strap
        self.rotation = 0
        self.state_machine.update_device(self.device_type)

    async def disconnect(self):
        await self._type_text("_$disconnect")
        self.device_type = DeviceTypes.not_connected
        self.rotation = 0
        self.state_machine.update_device(self.device_type)

    async def turn_left(self):
        while self.rotation >= 0:
            await self._type_text("+10x")
            self.rotation -= 1

    async def turn_far_left(self):
        while self.rotation >= -1:
            await self._type_text("+10x")
            self.rotation -= 1

    async def turn_right(self):
        while self.rotation <= 0:
            await self._type_text("-10x")
            self.rotation += 1

    async def turn_far_right(self):
        while self.rotation <= 1:
            await self._type_text("-10x")
            self.rotation += 1

    async def _type_text(self, text: str):
        interval = 0.05
        for char in text:
            self.keyboard.press(char)
            self.keyboard.release(char)
            await asyncio.sleep(interval)

    async def device_actions(
        self,
        transition: DefinedTransition,
        wait_for_completion: bool = True,
        timeout: float | None = None,
    ) -> bool:
        if transition.matches(DeviceTypes.not_connected, DeviceTypes.strap):
            await self.connect("strap")
        elif transition.matches(DeviceTypes.strap, DeviceTypes.not_connected):
            await self.disconnect()
        else:
            return False
        return True
