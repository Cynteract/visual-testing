from dataclasses import dataclass
from typing import Callable

from robot.device_emulator import DeviceTypes
from robot.tests.shared.pages import Pages, PageTags
from robot.tests.shared.ui_state import DefinedUIState as DS
from robot.tests.shared.ui_state import Games
from robot.tests.shared.ui_state import UIState as S
from shared.utils import PrintDuration


# list of conditions for transitions, used to generate all possible transitions
def _keep_device(transition: "DefinedTransition") -> bool:
    return transition.old.device == transition.new.device


def _keep_game(transition: "DefinedTransition") -> bool:
    return transition.old.game == transition.new.game


def _keep_page(transition: "DefinedTransition") -> bool:
    return transition.old.page == transition.new.page


def _keep_device_and_game(transition: "DefinedTransition") -> bool:
    return _keep_device(transition) and _keep_game(transition)


def _is_connected(transition: "DefinedTransition") -> bool:
    return (
        _keep_device_and_game(transition) and transition.new.device == DeviceTypes.strap
    )


def _is_not_connected(transition: "DefinedTransition") -> bool:
    return (
        _keep_device_and_game(transition)
        and transition.new.device == DeviceTypes.not_connected
    )


def _keep_page_and_game(transition: "DefinedTransition") -> bool:
    return _keep_page(transition) and _keep_game(transition)


def _start_game(transition: "DefinedTransition") -> bool:
    return _keep_device(transition) and transition.new.game != Games.no_game


def _leave_game(transition: "DefinedTransition") -> bool:
    return _keep_device(transition) and transition.new.game == Games.no_game


@dataclass
class _Transition:
    """Partially defined transition, will be expanded before use"""

    old: S
    new: S
    cost: float
    condition: Callable[["DefinedTransition"], bool] = _keep_device_and_game


P = Pages
T = _Transition


# trying to keep the lines short for auto-sorting
_base_transitions = [
    T(S(P._restart), S(P.startup), 1),
    T(S(P.calibrate), S(P.gameplay), 1),
    T(S(P.feedback), S(P.home), 1, _leave_game),
    T(S(P.game_center), S(P.movement_selection), 1, _start_game),
    T(S(P.home), S(P.please_connect), 1, _is_not_connected),
    T(S(P.home), S(P.game_center), 1, _is_connected),
    T(S(P.home), S(P.settings), 1),
    T(S(P.introduction), S(P.home), 1),
    T(S(P.login_help), S(P.login), 1),
    T(S(P.login), S(P.introduction), 1),
    T(S(P.login), S(P.login_help), 1),
    T(S(P.movement_selection), S(P.calibrate), 1),
    T(S(P.pause_menu), S(P.home), 1, _leave_game),
    T(S(P.pause_menu), S(P.feedback), 2),
    T(S(P.please_connect), S(P.position_selection), 1, _is_connected),
    T(S(P.please_connect), S(P.home), 1),
    T(S(P.please_connect), S(P.home), 1, _leave_game),
    T(S(P.position_selection), S(P.game_center), 1),
    T(S(P.settings), S(P.home), 1),
    T(S(P.settings), S(P.login), 1),
    T(S(P.gameplay), S(P.pause_menu), 1),
    T(S(P.startup), S(P.update), 1),
    T(S(P.update), S(P.login), 1),
    T(S(PageTags.any), S(P._restart), 10),
    T(S(PageTags.device_connected), S(P.please_connect), 1),
    T(S(DeviceTypes.not_connected), S(DeviceTypes.strap), 6, _keep_page_and_game),
    T(S(DeviceTypes.strap), S(DeviceTypes.not_connected), 3, _keep_page_and_game),
]


@dataclass
class DefinedTransition:
    """Fully defined transition"""

    old: DS
    new: DS
    cost: float

    def matches(
        self,
        old: Pages | PageTags | DeviceTypes,
        new: Pages | DeviceTypes | list[Pages],
    ) -> bool:
        if isinstance(old, Pages) and isinstance(new, Pages):
            return self.old.page == old and self.new.page == new
        elif isinstance(old, PageTags) and isinstance(new, Pages):
            return self.old.page.has(old) and self.new.page == new
        elif isinstance(old, Pages) and isinstance(new, DeviceTypes):
            return self.old.page == old and self.new.device == new
        elif isinstance(old, DeviceTypes) and isinstance(new, DeviceTypes):
            return self.old.device == old and self.new.device == new
        elif isinstance(old, Pages) and isinstance(new, list):
            return self.old.page == old and self.new.page in new
        else:
            raise ValueError(f"Invalid types for matching: {type(old)}, {type(new)}")


def expand_states(states: list[S]) -> list[DS]:
    # expand page
    new_states: list[S] = []
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
    new_defined_states: list[DS] = []
    for state in states:
        assert (
            isinstance(state.page, Pages)
            and isinstance(state.game, Games)
            and isinstance(state.device, DeviceTypes)
        )
        new_defined_states.append(
            DS(
                page=state.page,
                game=state.game,
                device=state.device,
            )
        )

    # filter invalid states
    new_defined_states = [state for state in new_defined_states if DS.is_valid(state)]

    return new_defined_states


def expand_transitions(
    transitions: list[_Transition],
) -> list[DefinedTransition]:
    # expand states
    new_defined_transitions: list[DefinedTransition] = []
    for transition in transitions:
        expanded_old_states = expand_states([transition.old])
        expanded_new_states = expand_states([transition.new])
        for old in expanded_old_states:
            for new in expanded_new_states:
                new_transition = DefinedTransition(
                    old=old, new=new, cost=transition.cost
                )
                if transition.condition(new_transition):
                    new_defined_transitions.append(new_transition)

    # remove duplicates
    seen: set[tuple[DS, DS]] = set()
    result: list[DefinedTransition] = []
    for transition in new_defined_transitions:
        key = (transition.old, transition.new)
        if key not in seen:
            seen.add(key)
            result.append(transition)

    return result


with PrintDuration("expanding transitions"):
    _expanded_transitions = expand_transitions(_base_transitions)


# generate all transitions using Floyd-Warshall algorithm
# source: https://en.wikipedia.org/wiki/Floyd%E2%80%93Warshall_algorithm
def floyd_warshall(
    transitions: list[DefinedTransition],
) -> tuple[
    dict[DS, dict[DS, float]],
    dict[DS, dict[DS, DS | None]],
]:
    dist: dict[DS, dict[DS, float]] = {
        u: {v: float("inf") for v in DS.valid_states()} for u in DS.valid_states()
    }
    prev: dict[DS, dict[DS, DS | None]] = {
        u: {v: None for v in DS.valid_states()} for u in DS.valid_states()
    }

    for edge in transitions:
        dist[edge.old][edge.new] = edge.cost
        prev[edge.old][edge.new] = edge.old
    for vertex in DS.valid_states():
        dist[vertex][vertex] = 0
        prev[vertex][vertex] = vertex
    for k in DS.valid_states():
        for i in DS.valid_states():
            for j in DS.valid_states():
                if dist[i][j] > dist[i][k] + dist[k][j]:
                    dist[i][j] = dist[i][k] + dist[k][j]
                    prev[i][j] = prev[k][j]

    return dist, prev


with PrintDuration("generating all paths (Floyd-Warshall)"):
    dist, prev = floyd_warshall(_expanded_transitions)


def path(u: DS, v: DS, prev: dict[DS, dict[DS, DS | None]] = prev) -> list[DS]:
    if prev[u][v] is None:
        raise ValueError(f"No path from {u} to {v}")
    _u = u
    _v: DS | None = v
    path = [_v]
    while _u != _v:
        assert prev[_u] is not None and _v is not None
        _v = prev[_u][_v]
        assert _v is not None
        path.insert(0, _v)
    return path


_all_paths = {
    u: {v: path(u, v, prev) for v in DS.valid_states()} for u in DS.valid_states()
}


def get_next_transition(old: DS, new: DS | S) -> DefinedTransition:
    # find suiting transition
    if isinstance(new, DS):
        next_target = _all_paths[old][new][1]
        transition = next(
            t for t in _expanded_transitions if t.old == old and t.new == next_target
        )
        return transition
    else:
        # pick any suiting transition
        expanded_new = expand_states([new])
        for candidate in expanded_new:
            try:
                next_target = _all_paths[old][candidate][1]
                transition = next(
                    t
                    for t in _expanded_transitions
                    if t.old == old and t.new == next_target
                )
                return transition
            except (KeyError, IndexError):
                continue
        raise ValueError(f"No transition found from {old} to {new}")
