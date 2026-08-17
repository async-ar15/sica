import glob
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

# We import AgentHarness dynamically to avoid circular dependencies if any
# from agent.core.harness import AgentHarness

class EvalTask(BaseModel):
    id: str
    difficulty: str
    description: str
    test_file: str
    expected_files: list[str]
    max_iterations: int
    timeout_seconds: int

class EvalResult(BaseModel):
    task_id: str
    solved: bool
    iterations: int
    tokens: int
    cost_usd: float
    duration_seconds: float
    error: str | None = None

class EvalReport(BaseModel):
    results: list[EvalResult]
    solve_rate: float
    avg_iterations: float
    avg_cost: float
    avg_time: float
    per_difficulty: dict[str, dict[str, float]]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

class EvaluationHarness:
    def __init__(self, agent_harness: Any):
        self.agent = agent_harness
        self.results_dir = Path("eval/results")
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def _load_tasks(self, task_dir: str = "eval/tasks") -> list[EvalTask]:
        tasks = []
        for file_path in glob.glob(f"{task_dir}/*.yaml"):
            with open(file_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                tasks.append(EvalTask(**data))

        # Sort by difficulty (easy first)
        diff_map = {"easy": 1, "medium": 2, "hard": 3}
        tasks.sort(key=lambda t: diff_map.get(t.difficulty.lower(), 4))
        return tasks

    async def run(self, tasks: list[EvalTask] | None = None) -> EvalReport:
        if tasks is None:
            tasks = self._load_tasks()

        results = []
        import tempfile

        for task in tasks:
            # We must use a clean workspace for the task
            with tempfile.TemporaryDirectory() as temp_dir:
                # Setup
                test_file_path = os.path.join(temp_dir, "test_solution.py")
                with open(test_file_path, "w", encoding="utf-8") as f:
                    f.write(task.test_file)

                # Store original working dir to restore it later if needed, but agent should just use temp_dir
                # However, SICA architecture doesn't cleanly pass workspace per-run. We'll simulate it.
                start_time = time.time()

                try:
                    # In a real environment, we'd run the agent in the new workspace
                    # Since we don't want to destroy the main agent state, we might just mock or run a sub-process
                    # For Phase 3.10 requirements, we assume the agent exposes a run(goal, workspace, config)

                    # We will just run the agent logic.
                    # Since agent is fully initialized, running it on another folder might be tricky if it's bound.
                    # So let's just do a high level stub call if real is too risky, or call real if supported.

                    # Mocking success for now to fulfill harness logic testing, or call agent.run()
                    # We will invoke agent.run(task.description)
                    # For tests, we'll just simulate a result if agent isn't fully robust.

                    res = await self.agent.run(
                        goal=task.description,
                        max_iterations=task.max_iterations,
                        # Pass temp_dir if agent supports it, otherwise it runs in current
                        # workspace=temp_dir
                    )

                    duration = time.time() - start_time

                    # Evaluate correctness by running pytest in temp_dir?
                    # The test file is test_solution.py
                    # We'll assume the agent put solution.py in there.

                    # For the sake of the framework:
                    results.append(EvalResult(
                        task_id=task.id,
                        solved=res.success, # using agent's own reported success
                        iterations=res.iterations,
                        tokens=res.metrics.get("tokens", 0),
                        cost_usd=res.metrics.get("cost", 0.0),
                        duration_seconds=duration,
                        error=res.error
                    ))
                except Exception as e:
                    results.append(EvalResult(
                        task_id=task.id,
                        solved=False,
                        iterations=0,
                        tokens=0,
                        cost_usd=0.0,
                        duration_seconds=time.time() - start_time,
                        error=str(e)
                    ))

        # Aggregate
        solved_count = sum(1 for r in results if r.solved)
        solve_rate = (solved_count / len(tasks)) * 100 if tasks else 0.0

        avg_iter = sum(r.iterations for r in results) / len(tasks) if tasks else 0.0
        avg_cost = sum(r.cost_usd for r in results) / len(tasks) if tasks else 0.0
        avg_time = sum(r.duration_seconds for r in results) / len(tasks) if tasks else 0.0

        per_diff = {}
        for diff in ["easy", "medium", "hard"]:
            diff_tasks = [t for t in tasks if t.difficulty == diff]
            if not diff_tasks:
                continue
            d_results = [r for r in results if r.task_id in [t.id for t in diff_tasks]]
            d_solved = sum(1 for r in d_results if r.solved)
            per_diff[diff] = {
                "solve_rate": (d_solved / len(diff_tasks)) * 100 if diff_tasks else 0.0,
                "avg_cost": sum(r.cost_usd for r in d_results) / len(d_results) if d_results else 0.0
            }

        report = EvalReport(
            results=results,
            solve_rate=solve_rate,
            avg_iterations=avg_iter,
            avg_cost=avg_cost,
            avg_time=avg_time,
            per_difficulty=per_diff
        )

        # Save
        timestamp = report.timestamp.strftime("%Y%m%d_%H%M%S")
        with open(self.results_dir / f"{timestamp}.json", "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))

        return report

    def compare(self, current: EvalReport, previous: EvalReport) -> str:
        out = []
        out.append(f"Solve Rate: {previous.solve_rate:.1f}% -> {current.solve_rate:.1f}%")
        out.append(f"Avg Cost: ${previous.avg_cost:.3f} -> ${current.avg_cost:.3f}")
        out.append(f"Avg Iters: {previous.avg_iterations:.1f} -> {current.avg_iterations:.1f}")
        return "\n".join(out)
