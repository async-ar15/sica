from collections.abc import Callable
from enum import StrEnum

from pydantic import BaseModel


class TripReason(StrEnum):
    """Why the circuit breaker stopped the agent."""
    MAX_ITERATIONS = "max_iterations"
    CONSECUTIVE_FAILURES = "consecutive_failures"
    NO_PROGRESS = "no_progress"
    BUDGET_EXCEEDED = "budget_exceeded"

class CircuitBreakerConfig(BaseModel):
    """Configuration for the circuit breaker."""
    max_iterations: int = 10
    # max_consecutive_failures: int = 3
    # progress_window: int = 3
    # min_progress_score: float = 0.1
    # max_cost_per_task_usd: float = 0.50

class BreakerState(BaseModel):
    """Current state fed to circuit breaker for evaluation."""
    iteration_count: int
    # consecutive_same_errors: int = 0
    # progress_scores: list[float] = []
    # total_cost_usd: float = 0.0

class CircuitBreaker:
    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        self.config = config or CircuitBreakerConfig()
        self._conditions: list[Callable[[BreakerState], TripReason | None]] = [
            self._check_max_iterations
        ]

    def check(self, state: BreakerState) -> TripReason | None:
        for condition in self._conditions:
            result = condition(state)
            if result is not None:
                return result
        return None

    def _check_max_iterations(self, state: BreakerState) -> TripReason | None:
        if state.iteration_count >= self.config.max_iterations:
            return TripReason.MAX_ITERATIONS
        return None

    def add_condition(self, condition: Callable[[BreakerState], TripReason | None]) -> None:
        self._conditions.append(condition)
