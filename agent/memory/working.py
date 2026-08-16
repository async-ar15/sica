import re
from collections import deque

from pydantic import BaseModel


class ErrorSignature(BaseModel):
    """Normalized error for comparison."""
    error_type: str
    core_message: str
    raw_message: str

class IterationSnapshot(BaseModel):
    """Record of one iteration through the FSM loop."""
    iteration: int
    plan_summary: str = ""
    code_changes: list[str] = []
    test_result: dict[str, int] = {}
    errors: list[ErrorSignature] = []
    hypothesis: str = ""
    tokens_used: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0

class SubTask(BaseModel):
    """Single unit of work in a DAG plan."""
    task_id: str
    description: str
    depends_on: list[str] = []
    status: str = "pending"
    files_to_create: list[str] = []
    files_to_modify: list[str] = []

class WorkingMemory:
    def __init__(self) -> None:
        self.current_goal: str = ""
        self.current_plan: list[SubTask] | None = None
        self.iteration_history: deque[IterationSnapshot] = deque(maxlen=10)
        self.active_errors: list[ErrorSignature] = []
        self.tried_hypotheses: set[str] = set()
        self.repo_map: str = ""
        self.relevant_memories: list[str] = []

    def record_iteration(self, snapshot: IterationSnapshot) -> None:
        self.iteration_history.append(snapshot)

    def normalize_hypothesis(self, h: str) -> str:
        # lowercase, strip whitespace, remove trailing punctuation
        h = h.lower().strip()
        h = re.sub(r'[.!?]+$', '', h)
        return h

    def has_tried(self, hypothesis: str) -> bool:
        return self.normalize_hypothesis(hypothesis) in self.tried_hypotheses

    def mark_tried(self, hypothesis: str) -> None:
        self.tried_hypotheses.add(self.normalize_hypothesis(hypothesis))

    def reset(self) -> None:
        self.current_goal = ""
        self.current_plan = None
        self.iteration_history.clear()
        self.active_errors.clear()
        self.tried_hypotheses.clear()
        self.repo_map = ""
        self.relevant_memories.clear()

    def remember(self, key: str, value: str) -> None:
        self.relevant_memories.append(f"{key}: {value}")

    def to_context_string(self) -> str:
        parts = []
        parts.append(f"Current Goal: {self.current_goal}")

        if self.current_plan:
            plan_strs = []
            for t in self.current_plan:
                plan_strs.append(f"- [{t.status}] {t.task_id}: {t.description}")
            parts.append("Current Plan:\\n" + "\\n".join(plan_strs))

        if self.iteration_history:
            parts.append(f"Recent Iterations ({len(self.iteration_history)}):")
            # show up to last 3
            recent = list(self.iteration_history)[-3:]
            for r in recent:
                parts.append(
                    f"  - Iteration {r.iteration}: {r.hypothesis} "
                    f"-> tokens: {r.tokens_used}"
                )

        if self.active_errors:
            parts.append("Active Errors:")
            for e in self.active_errors:
                parts.append(f"  - {e.error_type}: {e.core_message}")

        parts.append(f"Tried Hypotheses Count: {len(self.tried_hypotheses)}")
        return "\\n".join(parts)
