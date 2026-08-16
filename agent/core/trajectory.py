import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class TrajectoryStep(BaseModel):
    """A single step in the agent's trajectory."""
    step_index: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    state: str
    action_type: str  # e.g., 'llm_call', 'tool_execution'
    content: dict[str, Any]

class TrajectoryLogger:
    def __init__(self, task_id: str, log_dir: str = "memory/trajectory_logs") -> None:
        self.task_id = task_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"{task_id}.jsonl"

    def log_step(self, step: TrajectoryStep) -> None:
        """Append a step to the JSONL log."""
        record = step.model_dump(mode="json")
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\\n")
