from unittest.mock import Mock, patch

from robot import state_machine as sm


def test_routes_are_shared_but_test_state_is_independent():
    sm._get_transitions.cache_clear()
    try:
        with patch.object(sm, "Transitions") as build:
            initial = Mock()
            first = sm.UIStateMachine(initial)
            second = sm.UIStateMachine(initial)
            build.assert_called_once_with()
            assert first.transitions is second.transitions

            first.state = Mock()
            first.in_transition = True
            first.register_transition_actions(Mock())
            assert second.state is initial
            assert not second.in_transition
            assert second.transition_actions == []
    finally:
        sm._get_transitions.cache_clear()
