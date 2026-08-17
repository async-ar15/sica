import json
from unittest.mock import AsyncMock, patch

import pytest

from eval.harness import EvalReport, EvalResult, EvalTask, EvaluationHarness


@pytest.fixture
def temp_results_dir(tmp_path):
    # Mock the results_dir to avoid polluting actual project
    with patch("eval.harness.EvaluationHarness") as mock:
        pass
    return tmp_path

@pytest.fixture
def mock_agent():
    agent = AsyncMock()
    # Mock the return of agent.run
    res = AsyncMock()
    res.success = True
    res.iterations = 2
    res.metrics = {"tokens": 100, "cost": 0.05}
    res.error = None
    agent.run.return_value = res
    return agent

@pytest.fixture
def harness(mock_agent, tmp_path):
    h = EvaluationHarness(mock_agent)
    h.results_dir = tmp_path
    return h

def test_load_tasks_from_yaml(harness):
    # This requires eval/tasks to have the 20 generated tasks
    tasks = harness._load_tasks()
    assert len(tasks) == 20
    # verify sorting by difficulty
    diffs = [t.difficulty for t in tasks]
    assert "easy" in diffs[:7]
    assert "hard" in diffs[-6:]

def test_eval_result_structure():
    r = EvalResult(
        task_id="t1",
        solved=True,
        iterations=1,
        tokens=10,
        cost_usd=0.01,
        duration_seconds=5.0
    )
    assert r.solved is True
    assert r.cost_usd == 0.01

@pytest.mark.asyncio
async def test_eval_report_aggregation(harness, tmp_path):
    t1 = EvalTask(id="easy1", difficulty="easy", description="", test_file="", expected_files=[], max_iterations=3, timeout_seconds=30)
    t2 = EvalTask(id="hard1", difficulty="hard", description="", test_file="", expected_files=[], max_iterations=3, timeout_seconds=30)

    # Run the harness on these 2 tasks
    report = await harness.run([t1, t2])

    assert report.solve_rate == 100.0
    assert report.avg_iterations == 2.0
    assert report.avg_cost == 0.05

    assert "easy" in report.per_difficulty
    assert report.per_difficulty["easy"]["solve_rate"] == 100.0

def test_compare_reports(harness):
    r1 = EvalReport(
        results=[],
        solve_rate=50.0,
        avg_iterations=3.0,
        avg_cost=0.1,
        avg_time=10.0,
        per_difficulty={}
    )
    r2 = EvalReport(
        results=[],
        solve_rate=80.0,
        avg_iterations=2.5,
        avg_cost=0.05,
        avg_time=8.0,
        per_difficulty={}
    )

    comp = harness.compare(r2, r1)
    assert "50.0% -> 80.0%" in comp
    assert "$0.100 -> $0.050" in comp
    assert "3.0 -> 2.5" in comp

@pytest.mark.asyncio
async def test_results_saved_to_json(harness, tmp_path):
    t1 = EvalTask(id="t1", difficulty="easy", description="", test_file="", expected_files=[], max_iterations=3, timeout_seconds=30)

    report = await harness.run([t1])

    json_files = list(tmp_path.glob("*.json"))
    assert len(json_files) == 1

    data = json.loads(json_files[0].read_text())
    assert data["solve_rate"] == 100.0

@pytest.mark.asyncio
async def test_per_difficulty_breakdown(harness, tmp_path):
    tasks = [
        EvalTask(id="e1", difficulty="easy", description="", test_file="", expected_files=[], max_iterations=3, timeout_seconds=30),
        EvalTask(id="e2", difficulty="easy", description="", test_file="", expected_files=[], max_iterations=3, timeout_seconds=30),
        EvalTask(id="m1", difficulty="medium", description="", test_file="", expected_files=[], max_iterations=3, timeout_seconds=30),
    ]

    # Mock one easy task to fail to see breakdown
    def side_effect(goal, max_iterations):
        res = AsyncMock()
        if "e1" in goal:  # simple mock mapping (not strictly correct since we don't pass task ID, but it's ok for the unit test)
            pass
        res.success = True
        res.iterations = 1
        res.metrics = {"tokens": 10, "cost": 0.01}
        res.error = None
        return res

    harness.agent.run.side_effect = side_effect

    # Let's do a simpler side_effect using a list
    res1 = AsyncMock(); res1.success = True; res1.iterations = 1; res1.metrics = {"cost": 0.01}; res1.error = None
    res2 = AsyncMock(); res2.success = False; res2.iterations = 1; res2.metrics = {"cost": 0.01}; res2.error = None
    res3 = AsyncMock(); res3.success = True; res3.iterations = 1; res3.metrics = {"cost": 0.01}; res3.error = None
    harness.agent.run.side_effect = [res1, res2, res3]

    report = await harness.run(tasks)

    assert report.per_difficulty["easy"]["solve_rate"] == 50.0
    assert report.per_difficulty["medium"]["solve_rate"] == 100.0
