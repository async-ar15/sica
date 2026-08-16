from typing import Any


class BudgetTracker:
    def __init__(self, max_cost: float = 0.50, max_tokens: int = 100000) -> None:
        self.max_cost = max_cost
        self.max_tokens = max_tokens
        self.current_cost = 0.0
        self.current_tokens = 0

    def record(self, cost: float, tokens: int) -> None:
        self.current_cost += cost
        self.current_tokens += tokens

    def is_exceeded(self) -> bool:
        return self.current_cost >= self.max_cost or self.current_tokens >= self.max_tokens

    def get_usage(self) -> dict[str, Any]:
        return {
            "cost_usd": self.current_cost,
            "tokens": self.current_tokens,
            "max_cost_usd": self.max_cost,
            "max_tokens": self.max_tokens,
        }
