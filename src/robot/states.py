from dataclasses import dataclass
from enum import Enum

from robot.device_emulator import DeviceTypes
from robot.pages import Pages, PageTags


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
            elif isinstance(arg, Games):
                state.game = arg
            else:
                raise ValueError(f"Invalid argument type: {type(arg)}")

    def with_(self, **kwargs) -> "UIState":
        new_state = UIState()
        new_state.page = kwargs.get("page", self.page)
        new_state.game = kwargs.get("game", self.game)
        new_state.device = kwargs.get("device", self.device)
        return new_state

    def matches(self, other: "DefinedUIState") -> bool:
        if isinstance(self.page, Pages) and self.page != other.page:
            return False
        if isinstance(self.page, PageTags) and not other.page.has(self.page):
            return False
        if isinstance(self.game, Games) and self.game != other.game:
            return False
        if isinstance(self.device, DeviceTypes) and self.device != other.device:
            return False
        return True

    def __str__(self) -> str:
        result = "S"
        if self.page is not None:
            result += f"_P_{self.page.name}"
        if self.device is not None:
            result += f"_D_{self.device.name}"
        if self.game is not None:
            result += f"_G_{self.game.name}"
        return result


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

    def __str__(self) -> str:
        return str(UIState(self.page, self.device, self.game))

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


def expand_states(states: list[UIState]) -> list[DefinedUIState]:
    # expand page
    new_states: list[UIState] = []
    for state in states:
        if isinstance(state.page, Pages):
            new_states.append(state)
        elif isinstance(state.page, PageTags):
            for page in Pages:
                if page.has(state.page):
                    new_states.append(state.with_(page=page))
        else:
            for page in Pages:
                new_states.append(state.with_(page=page))
    states = new_states

    # expand game
    new_states = []
    for state in states:
        if state.game is not None:
            new_states.append(state)
        else:
            for game in Games:
                new_states.append(state.with_(game=game))
    states = new_states

    # expand device
    new_states = []
    for state in states:
        if state.device is not None:
            new_states.append(state)
        else:
            for device_type in DeviceTypes:
                new_states.append(state.with_(device=device_type))
    states = new_states

    # convert type
    new_defined_states: list[DefinedUIState] = []
    for state in states:
        assert (
            isinstance(state.page, Pages)
            and isinstance(state.game, Games)
            and isinstance(state.device, DeviceTypes)
        )
        new_defined_states.append(
            DefinedUIState(
                page=state.page,
                game=state.game,
                device=state.device,
            )
        )

    # filter invalid states
    new_defined_states = [
        state for state in new_defined_states if DefinedUIState.is_valid(state)
    ]

    return new_defined_states
