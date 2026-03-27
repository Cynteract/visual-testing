from dataclasses import dataclass
from enum import Enum

from robot.device_emulator import DeviceTypes
from robot.tests.shared.pages import Pages, PageTags


class Games(Enum):
    no_game = "no_game"
    sphere_runner = "sphere_runner"


# finite amount of possible states
# None means "any" for all attributes
@dataclass
class UIState:
    page: Pages | PageTags | None = None
    game: Games | None = None
    device: DeviceTypes | None = None

    def __init__(self, *args) -> None:
        state = self
        for arg in args:
            if isinstance(arg, Pages):
                state.page = arg
            elif isinstance(arg, PageTags):
                state.page = arg
            elif isinstance(arg, DeviceTypes):
                state.device = arg
            else:
                raise ValueError(f"Invalid argument type: {type(arg)}")

    def with_(self, **kwargs) -> "UIState":
        new_state = UIState()
        new_state.page = kwargs.get("page", self.page)
        new_state.game = kwargs.get("game", self.game)
        new_state.device = kwargs.get("device", self.device)
        return new_state


_valid_states: list["DefinedUIState"] = []


@dataclass(frozen=True)
class DefinedUIState:
    page: Pages
    game: Games
    device: DeviceTypes

    def with_(self, **kwargs) -> "DefinedUIState":
        new_state = DefinedUIState(
            page=kwargs.get("page", self.page),
            game=kwargs.get("game", self.game),
            device=kwargs.get("device", self.device),
        )
        return new_state

    @staticmethod
    def is_valid(state: "DefinedUIState") -> bool:
        return state in _valid_states

    @staticmethod
    def is_valid_uncached(state: "DefinedUIState") -> bool:
        # game pages can only be shown if a game is selected, except for the "please_connect" page
        if state.page.has(PageTags.game) and state.game == Games.no_game:
            if state.page != Pages.please_connect:
                return False

        # the opposite is true as well, except for the "please_connect" page
        if not state.page.has(PageTags.game) and state.game != Games.no_game:
            if state.page != Pages.please_connect:
                return False

        # pages that require a device connection cannot be shown without
        if (
            state.page.has(PageTags.device_connected)
            and state.device == DeviceTypes.not_connected
        ):
            return False

        return True

    @staticmethod
    def valid_states():
        return _valid_states


# cache valid_states
for page in Pages:
    for game in Games:
        for device in DeviceTypes:
            state = DefinedUIState(page=page, game=game, device=device)
            if DefinedUIState.is_valid_uncached(state):
                _valid_states.append(state)


class UIStateTracker:
    def __init__(self, initial_state: DefinedUIState):
        self.state = initial_state
        self.pending_game_start: Games | None = None

    def update_device(self, new_device: DeviceTypes):
        self.state = self.state.with_(device=new_device)
        if not DefinedUIState.is_valid(self.state):
            raise ValueError(f"Invalid state after device update: {self.state}")

    def update_page(self, new_page: Pages):
        if self.state.page == new_page:
            return

        # update game based on page change
        if self.pending_game_start is not None:
            if new_page.has(PageTags.game):
                self.state = self.state.with_(game=self.pending_game_start)
            self.pending_game_start = None
        if self.state.game != Games.no_game and not new_page.has(PageTags.game):
            self.state = self.state.with_(game=Games.no_game)

        self.state = self.state.with_(page=new_page)
        if not DefinedUIState.is_valid(self.state):
            raise ValueError(f"Invalid state after page update: {self.state}")

    def start_game(self, new_game: Games):
        self.pending_game_start = new_game

    def has_state_changed(self, old_state: DefinedUIState) -> bool:
        return self.state != old_state
