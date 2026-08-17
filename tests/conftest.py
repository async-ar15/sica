import pytest

from agent.core.state_machine import StateMachine


@pytest.fixture
def fsm() -> StateMachine:
    return StateMachine()
