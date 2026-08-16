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
