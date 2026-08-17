from agent.core.circuit_breaker import (
    BreakerState,
    CircuitBreaker,
    CircuitBreakerConfig,
    TripReason,
)


def test_no_trip_under_max() -> None:
    cb = CircuitBreaker(CircuitBreakerConfig(max_iterations=10))
    assert cb.check(BreakerState(iteration_count=5)) is None

def test_trip_at_max() -> None:
    cb = CircuitBreaker(CircuitBreakerConfig(max_iterations=10))
    assert cb.check(BreakerState(iteration_count=10)) == TripReason.MAX_ITERATIONS

def test_trip_over_max() -> None:
    cb = CircuitBreaker(CircuitBreakerConfig(max_iterations=10))
    assert cb.check(BreakerState(iteration_count=15)) == TripReason.MAX_ITERATIONS

def test_custom_max_iterations() -> None:
    cb = CircuitBreaker(CircuitBreakerConfig(max_iterations=3))
    assert cb.check(BreakerState(iteration_count=3)) == TripReason.MAX_ITERATIONS

def test_default_config_max_is_10() -> None:
    cb = CircuitBreaker()
    assert cb.config.max_iterations == 10
    assert cb.check(BreakerState(iteration_count=10)) == TripReason.MAX_ITERATIONS

def test_add_condition_extends_checks() -> None:
    cb = CircuitBreaker()
    def my_cond(state: BreakerState) -> TripReason | None:
        return TripReason.NO_PROGRESS

    cb.add_condition(my_cond)
    assert cb.check(BreakerState(iteration_count=1)) == TripReason.NO_PROGRESS

def test_first_trip_wins() -> None:
    cb = CircuitBreaker(CircuitBreakerConfig(max_iterations=10))
    def cond1(state: BreakerState) -> TripReason | None:
        return TripReason.CONSECUTIVE_FAILURES
    def cond2(state: BreakerState) -> TripReason | None:
        return TripReason.NO_PROGRESS

    # We add cond1 then cond2. The iterations check is first.
    cb.add_condition(cond1)
    cb.add_condition(cond2)

    # Under max iterations, cond1 should hit first
    assert cb.check(BreakerState(iteration_count=1)) == TripReason.CONSECUTIVE_FAILURES

    # At max iterations, the built-in max iter check should hit first
    assert cb.check(BreakerState(iteration_count=10)) == TripReason.MAX_ITERATIONS

def test_trip_on_budget_exceeded() -> None:
    cb = CircuitBreaker(CircuitBreakerConfig(max_cost_usd=1.0))
    # Below budget
    assert cb.check(BreakerState(iteration_count=1, total_cost_usd=0.99)) is None
    # At budget
    assert cb.check(BreakerState(iteration_count=1, total_cost_usd=1.0)) == TripReason.BUDGET_EXCEEDED
    # Over budget
    assert cb.check(BreakerState(iteration_count=1, total_cost_usd=1.5)) == TripReason.BUDGET_EXCEEDED

def test_trip_on_token_limit_exceeded() -> None:
    cb = CircuitBreaker(CircuitBreakerConfig(max_tokens=1000))
    # Below limit
    assert cb.check(BreakerState(iteration_count=1, total_tokens=999)) is None
    # At limit
    assert cb.check(BreakerState(iteration_count=1, total_tokens=1000)) == TripReason.TOKEN_LIMIT_EXCEEDED
    # Over limit
    assert cb.check(BreakerState(iteration_count=1, total_tokens=1001)) == TripReason.TOKEN_LIMIT_EXCEEDED

def test_trip_on_file_error_limit() -> None:
    cb = CircuitBreaker(CircuitBreakerConfig(max_file_errors=3))
    # Below limit
    assert cb.check(BreakerState(iteration_count=1, file_error_counts={"app.py": 2})) is None
    # At limit
    assert cb.check(BreakerState(iteration_count=1, file_error_counts={"app.py": 3})) == TripReason.FILE_ERROR_LIMIT
    # Multiple files, one over limit
    assert cb.check(BreakerState(
        iteration_count=1,
        file_error_counts={"main.py": 1, "app.py": 4}
    )) == TripReason.FILE_ERROR_LIMIT
