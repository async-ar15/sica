from collections.abc import Callable
from enum import StrEnum

from pydantic import BaseModel


class TripReason(StrEnum):
    """Why the circuit breaker stopped the agent."""
    MAX_ITERATIONS = "max_iterations"
    CONSECUTIVE_FAILURES = "consecutive_failures"
    NO_PROGRESS = "no_progress"
    BUDGET_EXCEEDED = "budget_exceeded"
    TOKEN_LIMIT_EXCEEDED = "token_limit_exceeded"
    FILE_ERROR_LIMIT = "file_error_limit"

class CircuitBreakerConfig(BaseModel):
    """Configuration for the circuit breaker."""
    max_iterations: int = 10
    max_cost_usd: float = 0.50
    max_tokens: int = 100000
    max_file_errors: int = 5

class BreakerState(BaseModel):
    """Current state fed to circuit breaker for evaluation."""
    iteration_count: int
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    file_error_counts: dict[str, int] = {}

class CircuitBreaker:
    def __init__(self, config: CircuitBreakerConfig | None = None) -> None:
        self.config = config or CircuitBreakerConfig()
        self._conditions: list[Callable[[BreakerState], TripReason | None]] = [
            self._check_max_iterations,
            self._check_budget,
            self._check_tokens,
            self._check_file_errors,
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

    def _check_budget(self, state: BreakerState) -> TripReason | None:
        if state.total_cost_usd >= self.config.max_cost_usd:
            return TripReason.BUDGET_EXCEEDED
        return None

    def _check_tokens(self, state: BreakerState) -> TripReason | None:
        if state.total_tokens >= self.config.max_tokens:
            return TripReason.TOKEN_LIMIT_EXCEEDED
        return None

    def _check_file_errors(self, state: BreakerState) -> TripReason | None:
        for file_path, count in state.file_error_counts.items():
            if count >= self.config.max_file_errors:
                return TripReason.FILE_ERROR_LIMIT
        return None

    def add_condition(self, condition: Callable[[BreakerState], TripReason | None]) -> None:
        self._conditions.append(condition)
