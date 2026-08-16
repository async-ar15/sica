import asyncio
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AgentState(StrEnum):
    """All possible states of the agent FSM."""
    IDLE = "idle"
    LOCALIZING = "localizing"
    PLANNING = "planning"
    CODING = "coding"
    ANALYZING = "analyzing"
    TESTING = "testing"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"

class StateSnapshot(BaseModel):
    """Immutable record of a single state transition."""
    state_name: AgentState
    iteration_count: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    error: str | None = None
    tokens_used: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0

class InvalidTransitionError(Exception):
    """Custom exception for illegal transitions."""
    pass

class StateMachine:
    TRANSITIONS: dict[AgentState, dict[str, AgentState]] = {
        AgentState.IDLE: {
            "goal_received_bugfix": AgentState.LOCALIZING,
            "goal_received_greenfield": AgentState.PLANNING,
        },
        AgentState.LOCALIZING: {
            "locations_found": AgentState.PLANNING,
            "localization_failed": AgentState.REFLECTING,
        },
        AgentState.PLANNING: {
            "plan_ready": AgentState.CODING,
            "plan_failed": AgentState.REFLECTING,
        },
        AgentState.CODING: {
            "code_ready": AgentState.ANALYZING,
            "code_failed": AgentState.REFLECTING,
        },
        AgentState.ANALYZING: {
            "analysis_pass": AgentState.TESTING,
            "analysis_fail": AgentState.CODING,
        },
        AgentState.TESTING: {
            "tests_pass": AgentState.COMPLETED,
            "tests_fail": AgentState.REFLECTING,
        },
        AgentState.REFLECTING: {
            "hypothesis_ready": AgentState.PLANNING,
            "circuit_breaker_trip": AgentState.FAILED,
        },
    }

    def __init__(self) -> None:
        self.state = AgentState.IDLE
        self._history: list[StateSnapshot] = []
        self._lock = asyncio.Lock()

    async def transition(self, event: str, **snapshot_kwargs: Any) -> AgentState:
        async with self._lock:
            if self.state in (AgentState.COMPLETED, AgentState.FAILED):
                raise InvalidTransitionError(f"Cannot transition from terminal state {self.state}")

            allowed_transitions = self.TRANSITIONS.get(self.state, {})
            if event not in allowed_transitions:
                raise InvalidTransitionError(f"Invalid event '{event}' for state {self.state}")

            next_state = allowed_transitions[event]

            # Record snapshot of PREVIOUS state
            snapshot = StateSnapshot(
                state_name=self.state,
                **snapshot_kwargs
            )
            self._history.append(snapshot)
            self.state = next_state

            return self.state

    def can_transition(self, event: str) -> bool:
        if self.state in (AgentState.COMPLETED, AgentState.FAILED):
            return False
        return event in self.TRANSITIONS.get(self.state, {})

    def get_history(self) -> list[StateSnapshot]:
        return self._history.copy()

    def reset(self) -> None:
        self.state = AgentState.IDLE
        self._history.clear()

    @property
    def current_state(self) -> AgentState:
        return self.state
