from robot.dev_console_actions import DevConsole
from robot.device_types import DeviceTypes
from robot.player_log_monitor import PlayerLogMonitor
from robot.state_machine import UIStateMachine
from robot.states import UIState
from robot.transitions import DefinedTransition


class DeviceEmulator:
    def __init__(
        self,
        dev_console: DevConsole,
        state_machine: UIStateMachine,
        player_log: PlayerLogMonitor,
    ):
        self.dev_console = dev_console
        self.device_type: DeviceTypes | None = None
        self.rotation: int = 0
        self.state_machine = state_machine
        self.player_log = player_log

        state_machine.register_transition_actions(self.device_actions)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.device_type is not None:
            # the page might change after the disconnect
            visited = set()
            while self.state_machine.state.device != DeviceTypes.not_connected:
                if self.state_machine.state in visited:
                    raise RuntimeError("Transition loop while disconnecting the emulator")
                visited.add(self.state_machine.state)
                await self.state_machine.go_towards(UIState(DeviceTypes.not_connected))

    async def connect(self, device_name: str):
        async with self.player_log.assert_line(f"Emulator: connect {device_name}"):
            await self.dev_console.run_command(device_name)
            self.device_type = DeviceTypes.strap
            self.rotation = 0
            self.state_machine.update_device(self.device_type)

    async def disconnect(self):
        async with self.player_log.assert_line("Emulator: disconnect"):
            await self.dev_console.run_command("disconnect")
            self.device_type = DeviceTypes.not_connected
            self.rotation = 0
            self.state_machine.update_device(self.device_type)

    async def turn_left(self):
        if self.rotation >= 0:
            await self.dev_console.run_commands([f"+10x"] * (self.rotation + 1))
            self.rotation = -1

    async def turn_far_left(self):
        if self.rotation >= -1:
            await self.dev_console.run_commands([f"+10x"] * (self.rotation + 2))
            self.rotation = -2

    async def turn_right(self):
        if self.rotation <= 0:
            await self.dev_console.run_commands([f"-10x"] * (abs(self.rotation) + 1))
            self.rotation = 1

    async def turn_far_right(self):
        if self.rotation <= 1:
            await self.dev_console.run_commands([f"-10x"] * (2 - self.rotation))
            self.rotation = 2

    async def reset_rotation(self):
        """Return the device to neutral (center) rotation."""
        if self.rotation > 0:
            await self.dev_console.run_commands([f"+10x"] * self.rotation)
        elif self.rotation < 0:
            await self.dev_console.run_commands([f"-10x"] * abs(self.rotation))
        self.rotation = 0

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
