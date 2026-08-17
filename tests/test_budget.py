import logging

import pytest

from agent.core.budget import Budget, BudgetExhaustedError


def test_record_accumulates_tokens():
    budget = Budget()
    budget.record(10, 20, "modelA")
    budget.record(5, 5, "modelB")
    assert budget._total_tokens == 40

def test_record_accumulates_cost():
    budget = Budget()
    budget.record(10, 20, "modelA", cost=0.10)
    budget.record(5, 5, "modelB", cost=0.05)
    assert budget._total_cost == pytest.approx(0.15)

def test_can_continue_under_budget():
    budget = Budget(max_tokens=100, max_cost_usd=1.0)
    budget.record(50, 0, "modelA", cost=0.5)
    assert budget.can_continue()

def test_can_continue_over_tokens():
    budget = Budget(max_tokens=100, max_cost_usd=1.0)
    budget.record(60, 50, "modelA", cost=0.1)
    assert not budget.can_continue()

def test_can_continue_over_cost():
    budget = Budget(max_tokens=100, max_cost_usd=1.0)
    budget.record(10, 10, "modelA", cost=1.1)
    assert not budget.can_continue()

def test_check_or_raise_raises():
    budget = Budget(max_tokens=100)
    budget.record(150, 0, "modelA")
    with pytest.raises(BudgetExhaustedError):
        budget.check_or_raise()

def test_warning_at_80_percent(caplog):
    budget = Budget(max_tokens=100)
    with caplog.at_level(logging.WARNING):
        budget.record(81, 0, "modelA")
    assert "80% of budget used" in caplog.text
    assert budget._warning_issued

def test_per_model_breakdown():
    budget = Budget()
    budget.record(10, 0, "modelA", cost=0.1)
    budget.record(20, 0, "modelB", cost=0.2)
    budget.record(5, 0, "modelA", cost=0.05)

    bd = budget.get_breakdown()["per_model"]
    assert bd["modelA"]["tokens"] == 15
    assert bd["modelA"]["cost"] == pytest.approx(0.15)
    assert bd["modelB"]["tokens"] == 20

def test_per_state_breakdown():
    budget = Budget()
    budget.record(10, 0, "modelA", state="planning", cost=0.1)
    budget.record(20, 0, "modelA", state="coding", cost=0.2)

    bd = budget.get_breakdown()["per_state"]
    assert bd["planning"]["tokens"] == 10
    assert bd["coding"]["tokens"] == 20

def test_format_report_includes_all():
    budget = Budget(max_tokens=100, max_cost_usd=1.0)
    budget.record(25, 0, "modelA", cost=0.25)
    rep = budget.format_report()
    assert "25/100 (25%)" in rep
    assert "$0.25/$1.00 (25%)" in rep

def test_reset_zeros_all():
    budget = Budget()
    budget.record(100, 0, "modelA", cost=0.5)
    budget.reset()
    assert budget._total_tokens == 0
    assert budget._total_cost == 0.0
    assert budget._per_model == {}
    assert budget._per_state == {}
