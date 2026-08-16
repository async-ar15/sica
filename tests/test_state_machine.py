import pytest
import asyncio
from agent.core.state_machine import StateMachine, AgentState, InvalidTransitionError

def test_initial_state_is_idle(fsm: StateMachine) -> None:
    assert fsm.current_state == AgentState.IDLE

@pytest.mark.asyncio
async def test_greenfield_transition_idle_to_planning(fsm: StateMachine) -> None:
    new_state = await fsm.transition("goal_received_greenfield", iteration_count=1)
    assert new_state == AgentState.PLANNING

@pytest.mark.asyncio
async def test_bugfix_transition_idle_to_localizing(fsm: StateMachine) -> None:
    new_state = await fsm.transition("goal_received_bugfix", iteration_count=1)
    assert new_state == AgentState.LOCALIZING

@pytest.mark.asyncio
async def test_full_happy_path(fsm: StateMachine) -> None:
    await fsm.transition("goal_received_greenfield", iteration_count=1)
    await fsm.transition("plan_ready", iteration_count=1)
    await fsm.transition("code_ready", iteration_count=1)
    await fsm.transition("analysis_pass", iteration_count=1)
    new_state = await fsm.transition("tests_pass", iteration_count=1)
    assert new_state == AgentState.COMPLETED

@pytest.mark.asyncio
async def test_reflection_loop(fsm: StateMachine) -> None:
    await fsm.transition("goal_received_greenfield", iteration_count=1)
    await fsm.transition("plan_ready", iteration_count=1)
    await fsm.transition("code_ready", iteration_count=1)
    await fsm.transition("analysis_pass", iteration_count=1)
    new_state = await fsm.transition("tests_fail", iteration_count=1)
    assert new_state == AgentState.REFLECTING
    new_state = await fsm.transition("hypothesis_ready", iteration_count=2)
    assert new_state == AgentState.PLANNING

@pytest.mark.asyncio
async def test_invalid_transition_raises(fsm: StateMachine) -> None:
    with pytest.raises(InvalidTransitionError):
        await fsm.transition("tests_pass", iteration_count=1)

@pytest.mark.asyncio
async def test_completed_is_terminal(fsm: StateMachine) -> None:
    await fsm.transition("goal_received_greenfield", iteration_count=1)
    await fsm.transition("plan_ready", iteration_count=1)
    await fsm.transition("code_ready", iteration_count=1)
    await fsm.transition("analysis_pass", iteration_count=1)
    await fsm.transition("tests_pass", iteration_count=1)
    with pytest.raises(InvalidTransitionError, match="terminal state"):
        await fsm.transition("tests_fail", iteration_count=1)

@pytest.mark.asyncio
async def test_failed_is_terminal(fsm: StateMachine) -> None:
    await fsm.transition("goal_received_greenfield", iteration_count=1)
    await fsm.transition("plan_ready", iteration_count=1)
    await fsm.transition("code_ready", iteration_count=1)
    await fsm.transition("analysis_pass", iteration_count=1)
    await fsm.transition("tests_fail", iteration_count=1)
    await fsm.transition("circuit_breaker_trip", iteration_count=1)
    with pytest.raises(InvalidTransitionError, match="terminal state"):
        await fsm.transition("hypothesis_ready", iteration_count=1)

@pytest.mark.asyncio
async def test_analysis_fail_goes_to_coding(fsm: StateMachine) -> None:
    await fsm.transition("goal_received_greenfield", iteration_count=1)
    await fsm.transition("plan_ready", iteration_count=1)
    await fsm.transition("code_ready", iteration_count=1)
    new_state = await fsm.transition("analysis_fail", iteration_count=1)
    assert new_state == AgentState.CODING

@pytest.mark.asyncio
async def test_circuit_breaker_trip_from_reflecting(fsm: StateMachine) -> None:
    await fsm.transition("goal_received_greenfield", iteration_count=1)
    await fsm.transition("plan_ready", iteration_count=1)
    await fsm.transition("code_ready", iteration_count=1)
    await fsm.transition("analysis_pass", iteration_count=1)
    await fsm.transition("tests_fail", iteration_count=1)
    new_state = await fsm.transition("circuit_breaker_trip", iteration_count=1)
    assert new_state == AgentState.FAILED

@pytest.mark.asyncio
async def test_history_records_all_transitions(fsm: StateMachine) -> None:
    await fsm.transition("goal_received_greenfield", iteration_count=1)
    await fsm.transition("plan_ready", iteration_count=1)
    await fsm.transition("code_ready", iteration_count=1)
    await fsm.transition("analysis_pass", iteration_count=1)
    await fsm.transition("tests_pass", iteration_count=1)
    history = fsm.get_history()
    assert len(history) == 5
    assert history[0].state_name == AgentState.IDLE
    assert history[1].state_name == AgentState.PLANNING

def test_reset_clears_state_and_history(fsm: StateMachine) -> None:
    async def run() -> None:
        await fsm.transition("goal_received_greenfield", iteration_count=1)
    asyncio.run(run())
    fsm.reset()
    assert fsm.current_state == AgentState.IDLE
    assert len(fsm.get_history()) == 0
