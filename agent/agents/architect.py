import json
from typing import Any

from pydantic import BaseModel, Field

from agent.memory.failure import FailureMemory
from agent.memory.working import ErrorSignature
from agent.tools.fault_localizer import EditLocation
from agent.tools.repo_map import RepoMap
from providers.llm import LLMProvider


class SubTask(BaseModel):
    """Single unit of work in a DAG plan."""
    task_id: str
    description: str
    depends_on: list[str] = Field(default_factory=list)
    status: str = "pending"              # pending | in_progress | done | failed
    estimated_complexity: str = "medium" # easy | medium | hard
    files_to_create: list[str] = Field(default_factory=list)
    files_to_modify: list[str] = Field(default_factory=list)
    result: dict[str, Any] | None = None


class TaskDAG(BaseModel):
    """Directed Acyclic Graph of subtasks."""
    tasks: list[SubTask] = Field(default_factory=list)

    def validate_dag(self) -> bool:
        """Topological sort to detect cycles. Check all deps valid. Check entry points exist."""
        if not self.tasks:
            return False

        task_map = {t.task_id: t for t in self.tasks}
        # Check invalid dependencies
        for t in self.tasks:
            for dep in t.depends_on:
                if dep not in task_map:
                    return False

        # Topological sort (Kahn's algorithm)
        in_degree = {t.task_id: len(t.depends_on) for t in self.tasks}
        queue = [t_id for t_id, deg in in_degree.items() if deg == 0]

        if not queue:
            return False # Cycle or empty with dependencies

        visited_count = 0
        while queue:
            node = queue.pop(0)
            visited_count += 1
            for t in self.tasks:
                if node in t.depends_on:
                    in_degree[t.task_id] -= 1
                    if in_degree[t.task_id] == 0:
                        queue.append(t.task_id)

        if visited_count != len(self.tasks):
            return False

        return True

    def get_ready_tasks(self) -> list[SubTask]:
        """Tasks where ALL dependencies have status 'done'."""
        task_map = {t.task_id: t for t in self.tasks}
        ready = []
        for t in self.tasks:
            if t.status == "pending":
                if all(task_map[dep].status == "done" for dep in t.depends_on):
                    ready.append(t)
        return ready

    def mark_done(self, task_id: str, result: dict[str, Any]) -> None:
        """Update task status to 'done', store result."""
        for t in self.tasks:
            if t.task_id == task_id:
                t.status = "done"
                t.result = result
                break

    def mark_failed(self, task_id: str, error: str) -> None:
        """Update task status to 'failed'."""
        for t in self.tasks:
            if t.task_id == task_id:
                t.status = "failed"
                break

    def get_downstream(self, task_id: str) -> list[SubTask]:
        """All tasks that depend on this one (directly or transitively)."""
        downstream = []
        queue = [task_id]
        while queue:
            curr = queue.pop(0)
            for t in self.tasks:
                if curr in t.depends_on and t not in downstream:
                    downstream.append(t)
                    queue.append(t.task_id)
        return downstream

    def is_complete(self) -> bool:
        """All tasks done."""
        if not self.tasks:
            return False
        return all(t.status == "done" for t in self.tasks)

    def replan_branch(self, failed_task_id: str, new_subtasks: list[SubTask]) -> None:
        """Replace failed task + downstream with new subtasks. Preserve completed."""
        downstream_ids = [t.task_id for t in self.get_downstream(failed_task_id)]
        to_remove = set(downstream_ids + [failed_task_id])
        self.tasks = [t for t in self.tasks if t.task_id not in to_remove]
        self.tasks.extend(new_subtasks)


class ArchitectAgent:
    def __init__(self, llm: LLMProvider, repo_map: RepoMap, failure_memory: FailureMemory):
        self.llm = llm
        self.repo_map = repo_map
        self.failure_memory = failure_memory

    async def plan(
        self,
        goal: str,
        repo_map_str: str,
        memories: list[str],
        fault_locations: list[EditLocation] | None = None
    ) -> TaskDAG:
        prompt = (
            "You are an expert software architect. Decompose the goal into a DAG of subtasks.\n\n"
            f"Goal: {goal}\n\n"
            f"Repo Map:\n{repo_map_str}\n\n"
        )
        if memories:
            prompt += "Memories:\n" + "\n".join(memories) + "\n\n"
        if fault_locations:
            prompt += "Fault Locations:\n" + "\n".join(str(loc) for loc in fault_locations) + "\n\n"

        messages = [
            {"role": "system", "content": "You are an expert software architect."},
            {"role": "user", "content": prompt}
        ]

        for _ in range(3):
            response = await self.llm.complete(
                task_type="planning",
                messages=messages,
                response_format=TaskDAG
            )

            try:
                content = response.content
                if isinstance(content, str):
                    dag_dict = json.loads(content)
                    dag = TaskDAG(**dag_dict)
                else:
                    dag = TaskDAG(**content)

                if dag.validate_dag():
                    return dag
            except Exception:
                pass

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": "The generated DAG was invalid or cyclic. Please try again."})

        raise ValueError("Failed to generate a valid TaskDAG after 3 attempts.")

    async def replan_on_failure(self, dag: TaskDAG, failed_task: SubTask, error: ErrorSignature) -> TaskDAG:
        error_message = f"{error.error_type}: {error.core_message}"
        prompt = (
            f"Task '{failed_task.description}' failed with error:\n{error_message}\n\n"
            "Please generate new subtasks to replace this task and its dependents."
        )
        messages = [
            {"role": "system", "content": "You are an expert software architect."},
            {"role": "user", "content": prompt}
        ]

        for _ in range(3):
            response = await self.llm.complete(
                task_type="planning",
                messages=messages,
                response_format=TaskDAG
            )
            try:
                content = response.content
                if isinstance(content, str):
                    dag_dict = json.loads(content)
                    new_dag = TaskDAG(**dag_dict)
                else:
                    new_dag = TaskDAG(**content)

                # We need to work on a copy to validate before modifying original
                test_dag = TaskDAG(tasks=[t.model_copy() for t in dag.tasks])
                test_dag.replan_branch(failed_task.task_id, new_dag.tasks)
                if test_dag.validate_dag():
                    dag.replan_branch(failed_task.task_id, new_dag.tasks)
                    return dag
            except Exception:
                pass

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": "The generated replacement tasks caused an invalid or cyclic DAG. Please try again."})

        raise ValueError("Failed to replan valid TaskDAG after 3 attempts.")
