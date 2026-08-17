import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.memory.distill import DistillEngine, Skill


@pytest.fixture
def mock_embeddings():
    emb = MagicMock()
    # Dummy embeddings. Make 3 of them very similar
    emb.embed_batch.return_value = [
        [1.0, 0.0],
        [0.99, 0.14],
        [0.98, 0.20],
        [0.0, 1.0] # different
    ]
    return emb

@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.complete.return_value = MagicMock(content="0.9")
    return llm

@pytest.fixture
def distill_engine(tmp_path, mock_embeddings, mock_llm):
    return DistillEngine(
        trajectory_dir=str(tmp_path / "trajectories"),
        embeddings=mock_embeddings,
        llm=mock_llm,
        failure_memory=MagicMock()
    )

def create_trajectory(path: Path, task_id: str, goal: str, success: bool, steps: list[dict]):
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / f"{task_id}.jsonl"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"action_type": "goal", "content": {"goal": goal}}) + "\n")
        for step in steps:
            f.write(json.dumps(step) + "\n")

        status = "success" if success else "failed"
        f.write(json.dumps({"action_type": "status", "content": {"status": status}}) + "\n")

@pytest.mark.asyncio
async def test_pattern_detection_groups_similar(distill_engine, tmp_path):
    traj_dir = tmp_path / "trajectories"

    # 3 similar successful tasks
    create_trajectory(traj_dir, "t1", "goal 1", True, [])
    create_trajectory(traj_dir, "t2", "goal 1", True, [])
    create_trajectory(traj_dir, "t3", "goal 1", True, [])

    # 1 different
    create_trajectory(traj_dir, "t4", "different", True, [])

    clusters = await distill_engine._detect_patterns()
    assert len(clusters) == 1
    assert len(clusters[0]) == 3
    assert "t1" in clusters[0]
    assert "t2" in clusters[0]
    assert "t3" in clusters[0]

@pytest.mark.asyncio
async def test_pattern_detection_requires_3_minimum(distill_engine, tmp_path):
    traj_dir = tmp_path / "trajectories"

    # Only 2 similar successful tasks
    create_trajectory(traj_dir, "t1", "goal 1", True, [])
    create_trajectory(traj_dir, "t2", "goal 1", True, [])

    clusters = await distill_engine._detect_patterns()
    assert len(clusters) == 0

@pytest.mark.asyncio
async def test_extract_common_steps_finds_lcs(distill_engine, tmp_path):
    traj_dir = tmp_path / "trajectories"

    steps = [
        {"action_type": "tool_call", "content": {"tool": "A"}},
        {"action_type": "tool_call", "content": {"tool": "B"}}
    ]
    create_trajectory(traj_dir, "t1", "goal 1", True, steps)

    cluster = ["t1"]
    common = distill_engine._extract_common_steps(cluster)
    assert len(common) == 2
    assert common[0]["content"]["tool"] == "A"

@pytest.mark.asyncio
async def test_templatize_replaces_filenames(distill_engine):
    steps = [
        {"action_type": "tool_call", "content": {"file": "main.py"}}
    ]
    skill = distill_engine._templatize(steps)
    assert skill.steps[0]["content"]["file"] == "{{target_file}}"

@pytest.mark.asyncio
async def test_templatize_replaces_function_names(distill_engine):
    steps = [
        {"action_type": "tool_call", "content": {"code": "def my_func(): pass"}}
    ]
    skill = distill_engine._templatize(steps)
    assert "{{function_name}}" in skill.steps[0]["content"]["code"]

@pytest.mark.asyncio
async def test_validate_scores_generality(distill_engine):
    skill = Skill(name="s1", description="d1", trigger_pattern="t1", steps=[], source_tasks=[])
    validated = await distill_engine._validate(skill)
    assert validated.generality_score == 0.9

@pytest.mark.asyncio
async def test_skill_files_created(distill_engine, tmp_path):
    traj_dir = tmp_path / "trajectories"

    # 3 similar successful tasks
    create_trajectory(traj_dir, "t1", "goal 1", True, [{"action_type": "tool_call"}])
    create_trajectory(traj_dir, "t2", "goal 1", True, [{"action_type": "tool_call"}])
    create_trajectory(traj_dir, "t3", "goal 1", True, [{"action_type": "tool_call"}])

    skills = await distill_engine.run()
    assert len(skills) == 1

    skill_dir = tmp_path / "skills"
    assert (skill_dir / "extracted_skill.md").exists()
    assert (skill_dir / "extracted_skill.yaml").exists()

@pytest.mark.asyncio
async def test_insufficient_data_returns_empty(distill_engine, tmp_path):
    traj_dir = tmp_path / "trajectories"
    create_trajectory(traj_dir, "t1", "goal 1", True, [])

    skills = await distill_engine.run()
    assert len(skills) == 0
