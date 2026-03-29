import os
from collections.abc import Awaitable, Callable

from robot.device_types import DeviceTypes
from robot.pages import Pages
from robot.states import DefinedUIState, Games, UIState
from robot.transitions import DefinedTransition, get_next_transition


class UIStateMachine:
    def __init__(self, initial_state: DefinedUIState):
        self.state = initial_state
        self.in_transition = False
        self.transition_actions: list[
            Callable[[DefinedTransition, bool, float | None], Awaitable[bool]]
        ] = []

    def register_transition_actions(
        self,
        actions: Callable[[DefinedTransition, bool, float | None], Awaitable[bool]],
    ):
        self.transition_actions.append(actions)

    async def fire_transition(
        self,
        transition: DefinedTransition,
        wait_for_transition: bool = True,
        timeout: float | None = None,
    ) -> DefinedUIState:
        transition_handled = False
        self.in_transition = True
        for action in self.transition_actions:
            if await action(transition, wait_for_transition, timeout):
                transition_handled = True
                break
        if not transition_handled:
            raise ValueError(f"No action defined for the transition: {transition}")
        # the new state is not necessarily the same as transition.new:
        # - action might have failed
        # - state might have changed differently than expected
        self.in_transition = False
        return self.state

    async def go_towards(self, new: UIState) -> DefinedUIState:
        transition = get_next_transition(self.state, new)
        if os.environ.get("DEBUG"):
            message = f"Trigger {self.state} → {new}"
            if not new.matches(transition.new):
                message += f" via {transition.new}"
            print(message)
        return await self.fire_transition(transition)

    async def trigger_towards(self, new: UIState) -> None:
        """Trigger transition to other page without waiting for it to complete."""
        transition = get_next_transition(self.state, new)
        if os.environ.get("DEBUG"):
            message = f"Trigger {self.state} → {new}"
            if not new.matches(transition.new):
                message += f" via {transition.new}"
            print(message)
        await self.fire_transition(transition, wait_for_transition=False)

    def check_state(self):
        if not self.in_transition and not DefinedUIState.is_valid(self.state):
            raise ValueError(f"Invalid state: {self.state}")

    def update_device(self, new_device: DeviceTypes):
        self.state = self.state.with_(device=new_device)
        self.check_state()

    def update_page(self, new_page: Pages):
        self.state = self.state.with_(page=new_page)
        self.check_state()

    def udpate_game(self, new_game: Games):
        self.state = self.state.with_(game=new_game)
        self.check_state()

    def has_state_changed(self, old_state: DefinedUIState) -> bool:
        return self.state != old_state
