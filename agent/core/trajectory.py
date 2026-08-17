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
            f.write(json.dumps(record) + "\n")

    def replay(self) -> None:
        if not self.log_file.exists():
            print(f"No trajectory found for {self.task_id}")
            return

        try:
            from rich.console import Console
            from rich.panel import Panel
            console = Console()

            with open(self.log_file, encoding="utf-8") as f:
                for line in f:
                    record = json.loads(line)
                    state = record.get("state", "UNKNOWN")
                    action = record.get("action_type", "")
                    content = record.get("content", {})

                    color = "white"
                    if "success" in str(content).lower(): color = "green"
                    elif "error" in str(content).lower() or "fail" in str(content).lower(): color = "red"

                    panel = Panel(
                        f"[bold]{action}[/bold]\n{json.dumps(content, indent=2)}",
                        title=f"[{color}]Step {record.get('step_index')} - {state}[/{color}]"
                    )
                    console.print(panel)

                    cmd = input("Press Enter to continue, 'q' to quit: ")
                    if cmd.lower() == 'q':
                        break
        except ImportError:
            print("Rich library not installed, cannot replay interactively.")

    def export(self, format: str = "markdown") -> str:
        if not self.log_file.exists():
            return f"No trajectory found for {self.task_id}"

        lines = [f"# Trajectory: {self.task_id}", ""]
        total_steps = 0

        with open(self.log_file, encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                total_steps += 1
                state = record.get("state", "UNKNOWN")
                action = record.get("action_type", "")
                content = record.get("content", {})

                lines.append(f"## Step {record.get('step_index')} - {state}")
                lines.append(f"**Action:** {action}")
                lines.append("```json")
                lines.append(json.dumps(content, indent=2))
                lines.append("```")
                lines.append("")

        lines.append("## Summary")
        lines.append(f"Total steps: {total_steps}")

        out = "\n".join(lines)
        export_file = self.log_dir / f"{self.task_id}.md"
        with open(export_file, "w", encoding="utf-8") as f:
            f.write(out)

        return out
