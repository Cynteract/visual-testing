from dataclasses import dataclass
from typing import Callable

from robot.device_types import DeviceTypes
from robot.pages import Pages, PageTags
from robot.states import DefinedUIState as DS
from robot.states import Games
from robot.states import UIState as S
from robot.states import expand_states
from shared.utils import PrintDuration


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


# list of conditions for transitions, used to generate all possible transitions
def _keep_device(transition: DefinedTransition) -> bool:
    return transition.old.device == transition.new.device


def _keep_game(transition: DefinedTransition) -> bool:
    return transition.old.game == transition.new.game


def _keep_page(transition: DefinedTransition) -> bool:
    return transition.old.page == transition.new.page


def _keep_device_and_game(transition: DefinedTransition) -> bool:
    return _keep_device(transition) and _keep_game(transition)


def _is_connected(transition: DefinedTransition) -> bool:
    return (
        _keep_device_and_game(transition) and transition.new.device == DeviceTypes.strap
    )


def _is_not_connected(transition: DefinedTransition) -> bool:
    return (
        _keep_device_and_game(transition)
        and transition.new.device == DeviceTypes.not_connected
    )


def _keep_page_and_game(transition: DefinedTransition) -> bool:
    return _keep_page(transition) and _keep_game(transition)


def _start_game(transition: DefinedTransition) -> bool:
    return _keep_device(transition) and transition.new.game != Games.no_game


def _leave_game(transition: DefinedTransition) -> bool:
    return _keep_device(transition) and transition.new.game == Games.no_game


class Transitions:

    @dataclass
    class _Transition:
        """Partially defined transition, will be expanded before use. Partial definitions are easier to write and read."""

        old: S
        new: S
        cost: float
        condition: Callable[[DefinedTransition], bool] = _keep_device_and_game

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

    def __init__(self):
        with PrintDuration("expanding transitions"):
            self._expanded_transitions = self._expand_transitions(
                self._base_transitions
            )
        with PrintDuration("generating all paths (Floyd-Warshall)"):
            dist, prev = self._floyd_warshall(self._expanded_transitions)
        self._all_paths = {
            u: {v: self._path(u, v, prev) for v in DS.valid_states()}
            for u in DS.valid_states()
        }

    @staticmethod
    def _expand_transitions(transitions: list[_Transition]) -> list[DefinedTransition]:
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

    # generate all transitions using Floyd-Warshall algorithm
    # source: https://en.wikipedia.org/wiki/Floyd%E2%80%93Warshall_algorithm
    @staticmethod
    def _floyd_warshall(
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

    @staticmethod
    def _path(u: DS, v: DS, prev: dict[DS, dict[DS, DS | None]]) -> list[DS]:
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

    def get_next_transition(self, old: DS, new: DS | S) -> DefinedTransition:
        # find suiting transition
        if isinstance(new, DS):
            next_target = self._all_paths[old][new][1]
            transition = next(
                t
                for t in self._expanded_transitions
                if t.old == old and t.new == next_target
            )
            return transition
        else:
            # pick any suiting transition
            expanded_new = expand_states([new])
            for candidate in expanded_new:
                try:
                    next_target = self._all_paths[old][candidate][1]
                    transition = next(
                        t
                        for t in self._expanded_transitions
                        if t.old == old and t.new == next_target
                    )
                    return transition
                except (KeyError, IndexError):
                    continue
            raise ValueError(f"No transition found from {old} to {new}")
