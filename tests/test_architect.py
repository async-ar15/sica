import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.agents.architect import ArchitectAgent, SubTask, TaskDAG


@pytest.fixture
def mock_llm():
    return AsyncMock()

@pytest.fixture
def mock_repo_map():
    rm = MagicMock()
    rm.__str__ = MagicMock(return_value="repo map")
    return rm

@pytest.fixture
def mock_failure_memory():
    return MagicMock()

@pytest.fixture
def architect(mock_llm, mock_repo_map, mock_failure_memory):
    return ArchitectAgent(mock_llm, mock_repo_map, mock_failure_memory)

def test_validate_detects_cycle():
    dag = TaskDAG(tasks=[
        SubTask(task_id="A", description="A", depends_on=["B"]),
        SubTask(task_id="B", description="B", depends_on=["A"]),
    ])
    assert not dag.validate_dag()

def test_validate_detects_missing_dependency():
    dag = TaskDAG(tasks=[
        SubTask(task_id="A", description="A", depends_on=["C"]),
    ])
    assert not dag.validate_dag()

def test_validate_requires_entry_point():
    dag = TaskDAG(tasks=[
        SubTask(task_id="A", description="A", depends_on=["B"]),
        SubTask(task_id="B", description="B", depends_on=["A"]),
    ])
    assert not dag.validate_dag()

def test_get_ready_tasks_returns_entry_points():
    dag = TaskDAG(tasks=[
        SubTask(task_id="A", description="A", depends_on=[]),
        SubTask(task_id="B", description="B", depends_on=["A"]),
    ])
    ready = dag.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].task_id == "A"

def test_get_ready_tasks_after_completion():
    dag = TaskDAG(tasks=[
        SubTask(task_id="A", description="A", depends_on=[], status="done"),
        SubTask(task_id="B", description="B", depends_on=["A"]),
    ])
    ready = dag.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].task_id == "B"

def test_mark_done_stores_result():
    dag = TaskDAG(tasks=[SubTask(task_id="A", description="A")])
    dag.mark_done("A", {"success": True})
    assert dag.tasks[0].status == "done"
    assert dag.tasks[0].result == {"success": True}

def test_get_downstream_finds_all():
    dag = TaskDAG(tasks=[
        SubTask(task_id="A", description="A"),
        SubTask(task_id="B", description="B", depends_on=["A"]),
        SubTask(task_id="C", description="C", depends_on=["B"]),
    ])
    downstream = dag.get_downstream("A")
    ids = {t.task_id for t in downstream}
    assert "B" in ids
    assert "C" in ids
    assert len(downstream) == 2

def test_is_complete_all_done():
    dag = TaskDAG(tasks=[
        SubTask(task_id="A", description="A", status="done"),
        SubTask(task_id="B", description="B", status="done"),
    ])
    assert dag.is_complete()

def test_is_complete_partial():
    dag = TaskDAG(tasks=[
        SubTask(task_id="A", description="A", status="done"),
        SubTask(task_id="B", description="B", status="pending"),
    ])
    assert not dag.is_complete()

def test_replan_branch_preserves_completed():
    dag = TaskDAG(tasks=[
        SubTask(task_id="A", description="A", status="done"),
        SubTask(task_id="B", description="B", status="failed", depends_on=["A"]),
    ])
    dag.replan_branch("B", [SubTask(task_id="B_new", description="B_new", depends_on=["A"])])
    assert len(dag.tasks) == 2
    assert dag.tasks[0].task_id == "A"
    assert dag.tasks[1].task_id == "B_new"

def test_empty_dag_raises_error():
    dag = TaskDAG(tasks=[])
    assert not dag.validate_dag()

@pytest.mark.asyncio
async def test_plan_generates_valid_dag(architect, mock_llm):
    valid_dag_json = json.dumps({
        "tasks": [{"task_id": "A", "description": "A", "depends_on": []}]
    })
    mock_llm.complete.return_value = MagicMock(content=valid_dag_json)

    dag = await architect.plan("do something", "repo_map", [])
    assert len(dag.tasks) == 1
    assert dag.tasks[0].task_id == "A"

@pytest.mark.asyncio
async def test_plan_includes_subtask_dependencies(architect, mock_llm):
    valid_dag_json = json.dumps({
        "tasks": [
            {"task_id": "A", "description": "A", "depends_on": []},
            {"task_id": "B", "description": "B", "depends_on": ["A"]}
        ]
    })
    mock_llm.complete.return_value = MagicMock(content=valid_dag_json)

    dag = await architect.plan("goal", "repo_map", [])
    assert dag.tasks[1].depends_on == ["A"]

@pytest.mark.asyncio
async def test_plan_retries_on_cyclic_dag(architect, mock_llm):
    cyclic_dag_json = json.dumps({
        "tasks": [
            {"task_id": "A", "description": "A", "depends_on": ["B"]},
            {"task_id": "B", "description": "B", "depends_on": ["A"]}
        ]
    })
    valid_dag_json = json.dumps({
        "tasks": [{"task_id": "A", "description": "A", "depends_on": []}]
    })

    mock_llm.complete.side_effect = [
        MagicMock(content=cyclic_dag_json),
        MagicMock(content=valid_dag_json)
    ]

    dag = await architect.plan("goal", "repo_map", [])
    assert len(dag.tasks) == 1
    assert mock_llm.complete.call_count == 2

@pytest.mark.asyncio
async def test_single_task_goal(architect, mock_llm):
    valid_dag_json = json.dumps({
        "tasks": [
            {"task_id": "A", "description": "A", "depends_on": []},
            {"task_id": "verify", "description": "verify", "depends_on": ["A"]}
        ]
    })
    mock_llm.complete.return_value = MagicMock(content=valid_dag_json)

    dag = await architect.plan("simple", "repo_map", [])
    assert len(dag.tasks) == 2
