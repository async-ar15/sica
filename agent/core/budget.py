import logging
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

class BudgetReport(BaseModel):
    total_tokens: int
    total_cost_usd: float
    max_tokens: int
    max_cost_usd: float
    token_percent: float
    cost_percent: float
    per_model_breakdown: dict[str, dict[str, Any]]
    per_state_breakdown: dict[str, dict[str, Any]]
    warning_threshold_hit: bool

class BudgetExhaustedError(Exception):
    def __init__(self, report: BudgetReport):
        self.report = report
        super().__init__(f"Budget exhausted! Tokens: {report.total_tokens}/{report.max_tokens}, Cost: ${report.total_cost_usd:.2f}/${report.max_cost_usd:.2f}")

class Budget:
    def __init__(self, max_tokens: int = 100_000, max_cost_usd: float = 0.50):
        self.max_tokens = max_tokens
        self.max_cost = max_cost_usd
        self._total_tokens = 0
        self._total_cost = 0.0
        self._per_model: dict[str, dict[str, Any]] = {}
        self._per_state: dict[str, dict[str, Any]] = {}
        self._warning_issued = False

    def record(self, input_tokens: int, output_tokens: int, model: str, state: str = "", cost: float | None = None) -> None:
        total_toks = input_tokens + output_tokens
        self._total_tokens += total_toks

        # If cost is None, we could calculate it using a pricing table, but for now we'll assume 0.0
        # unless litellm is used in provider (which should pass the cost).
        c = cost if cost is not None else 0.0
        self._total_cost += c

        if model not in self._per_model:
            self._per_model[model] = {"tokens": 0, "cost": 0.0}
        self._per_model[model]["tokens"] += total_toks
        self._per_model[model]["cost"] += c

        if state not in self._per_state:
            self._per_state[state] = {"tokens": 0, "cost": 0.0}
        self._per_state[state]["tokens"] += total_toks
        self._per_state[state]["cost"] += c

        # 80% warning
        token_pct = self._total_tokens / self.max_tokens if self.max_tokens > 0 else 0
        cost_pct = self._total_cost / self.max_cost if self.max_cost > 0 else 0

        if (token_pct >= 0.8 or cost_pct >= 0.8) and not self._warning_issued:
            logger.warning(f"⚠️ 80% of budget used: {token_pct*100:.1f}% tokens, {cost_pct*100:.1f}% cost")
            self._warning_issued = True

    def can_continue(self) -> bool:
        return self._total_tokens < self.max_tokens and self._total_cost < self.max_cost

    def check_or_raise(self) -> None:
        if not self.can_continue():
            raise BudgetExhaustedError(self.report())

    def report(self) -> BudgetReport:
        token_pct = self._total_tokens / self.max_tokens if self.max_tokens > 0 else 0
        cost_pct = self._total_cost / self.max_cost if self.max_cost > 0 else 0

        return BudgetReport(
            total_tokens=self._total_tokens,
            total_cost_usd=self._total_cost,
            max_tokens=self.max_tokens,
            max_cost_usd=self.max_cost,
            token_percent=token_pct,
            cost_percent=cost_pct,
            per_model_breakdown=self._per_model.copy(),
            per_state_breakdown=self._per_state.copy(),
            warning_threshold_hit=self._warning_issued
        )

    def format_report(self) -> str:
        rep = self.report()
        rem_tokens = max(0, self.max_tokens - self._total_tokens)
        rem_cost = max(0.0, self.max_cost - self._total_cost)
        return (f"Tokens: {self._total_tokens}/{self.max_tokens} ({rep.token_percent*100:.0f}%) | "
                f"Cost: ${self._total_cost:.2f}/${self.max_cost:.2f} ({rep.cost_percent*100:.0f}%) | "
                f"Remaining: {rem_tokens} tokens, ${rem_cost:.2f}")

    def reset(self) -> None:
        self._total_tokens = 0
        self._total_cost = 0.0
        self._per_model = {}
        self._per_state = {}
        self._warning_issued = False

    def get_breakdown(self) -> dict[str, Any]:
        return {
            "per_model": self._per_model.copy(),
            "per_state": self._per_state.copy()
        }
