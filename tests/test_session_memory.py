from pathlib import Path

import pytest

from agent.memory.session import CheckpointData, MemoryCategory, SessionMemory


@pytest.fixture
def memory_dir(tmp_path: Path) -> str:
    """Fixture to provide a temporary directory for memory."""
    return str(tmp_path / "memory")

@pytest.fixture
def session_memory(memory_dir: str) -> SessionMemory:
    """Fixture to provide a fresh SessionMemory instance."""
    return SessionMemory(memory_dir=memory_dir)

def test_read_memory_creates_template_if_missing(session_memory: SessionMemory):
    """Verify header template created"""
    content = session_memory.read_memory()
    assert "# Agent Memory" in content
    assert "## Architecture" in content
    assert "## Patterns" in content
    assert "## Errors" in content
    assert "## Conventions" in content
    assert "## Facts" in content
    assert session_memory.memory_file.exists()

def test_append_fact_under_correct_section(session_memory: SessionMemory):
    """Append architecture fact, verify it's under ## Architecture"""
    session_memory.read_memory() # ensure template exists
    session_memory.append_fact("Uses SQLite for FTS", MemoryCategory.ARCHITECTURE, "test-task")

    content = session_memory.read_memory()
    lines = content.splitlines()

    # Find the index of "## Architecture" and verify the next non-empty line is our fact
    arch_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == "## Architecture":
            arch_idx = i
            break

    assert arch_idx != -1
    assert "Uses SQLite for FTS" in lines[arch_idx + 1]

def test_append_fact_format(session_memory: SessionMemory):
    """Verify format includes category, fact, source_task, timestamp"""
    session_memory.append_fact("Python has a GIL", MemoryCategory.FACT, "task-001")
    content = session_memory.read_memory()

    # Format: - [{category}] {fact} (from task: {source_task}, {ISO timestamp})
    assert "- [fact] Python has a GIL (from task: task-001," in content

def test_search_memory_finds_matches(session_memory: SessionMemory):
    """Append 5 facts, search for keyword, verify correct matches"""
    session_memory.append_fact("Fact one about apple", MemoryCategory.FACT, "t1")
    session_memory.append_fact("Fact two about banana", MemoryCategory.FACT, "t1")
    session_memory.append_fact("Fact three about APPLE pie", MemoryCategory.FACT, "t1")
    session_memory.append_fact("Another architecture rule", MemoryCategory.ARCHITECTURE, "t2")
    session_memory.append_fact("Final fact about orange", MemoryCategory.FACT, "t3")

    results = session_memory.search_memory("apple")
    assert len(results) == 2
    assert "apple" in results[0].lower()
    assert "apple" in results[1].lower()

def test_search_memory_case_insensitive(session_memory: SessionMemory):
    """Search with different case, verify match"""
    session_memory.append_fact("Something about Docker", MemoryCategory.ARCHITECTURE, "t1")
    results = session_memory.search_memory("dOcKeR")
    assert len(results) == 1
    assert "Docker" in results[0]

def test_save_checkpoint_creates_file(session_memory: SessionMemory):
    """Save checkpoint, verify file exists"""
    data = CheckpointData(current_goal="test goal", current_state="idle", iteration_count=1)
    session_memory.save_checkpoint(data)
    assert session_memory.checkpoint_file.exists()

def test_load_checkpoint_returns_data(session_memory: SessionMemory):
    """Save then load, verify fields match"""
    data = CheckpointData(
        current_goal="test goal",
        current_state="idle",
        iteration_count=5,
        last_error="TypeError",
        files_modified=["a.py", "b.py"],
        current_hypothesis="use dict",
        tried_hypotheses=["use list"],
        task_id="t-123"
    )
    session_memory.save_checkpoint(data)
    loaded = session_memory.load_checkpoint()

    assert loaded is not None
    assert loaded.current_goal == data.current_goal
    assert loaded.current_state == data.current_state
    assert loaded.iteration_count == data.iteration_count
    assert loaded.last_error == data.last_error
    assert loaded.files_modified == data.files_modified
    assert loaded.current_hypothesis == data.current_hypothesis
    assert loaded.tried_hypotheses == data.tried_hypotheses
    assert loaded.task_id == data.task_id

def test_load_checkpoint_returns_none_if_missing(session_memory: SessionMemory):
    """Verify None when no checkpoint"""
    assert session_memory.load_checkpoint() is None

def test_load_checkpoint_handles_corrupt_file(session_memory: SessionMemory):
    """Write garbage to checkpoint, verify None returned and file renamed"""
    session_memory.checkpoint_file.write_text("garbage data without proper fields")
    loaded = session_memory.load_checkpoint()

    assert loaded is None
    assert not session_memory.checkpoint_file.exists()
    corrupt_file = Path(session_memory.memory_dir) / ".checkpoint.md.corrupt"
    assert corrupt_file.exists()

def test_clear_checkpoint_deletes_file(session_memory: SessionMemory):
    """Save, clear, verify file gone"""
    data = CheckpointData(current_goal="test goal", current_state="idle", iteration_count=1)
    session_memory.save_checkpoint(data)
    assert session_memory.checkpoint_file.exists()

    session_memory.clear_checkpoint()
    assert not session_memory.checkpoint_file.exists()

def test_checkpoint_atomic_write(session_memory: SessionMemory):
    """Verify temp file pattern (no partial writes)"""
    data = CheckpointData(current_goal="test goal", current_state="idle", iteration_count=1)
    session_memory.save_checkpoint(data)

    # We can't easily catch the rename in flight, but we can verify
    # the temp file doesn't linger and the target is written.
    tmp_path = session_memory.checkpoint_file.with_suffix(session_memory.checkpoint_file.suffix + ".tmp")
    assert not tmp_path.exists()
    assert session_memory.checkpoint_file.exists()

def test_create_task_log(session_memory: SessionMemory):
    """Create log, verify file exists with header"""
    session_memory.create_task_log("task-001", "fix bug")
    log_file = session_memory.task_logs_dir / "task-001.md"

    assert log_file.exists()
    content = log_file.read_text()
    assert "# Task: task-001" in content
    assert "## Goal: fix bug" in content

def test_append_to_task_log(session_memory: SessionMemory):
    """Create and append, verify content"""
    session_memory.create_task_log("task-001", "fix bug")
    session_memory.append_to_task_log("task-001", 1, "Testing changes")

    log_file = session_memory.task_logs_dir / "task-001.md"
    content = log_file.read_text()

    assert "### Iteration 1" in content
    assert "Testing changes" in content

def test_list_task_logs(session_memory: SessionMemory):
    """Create 3 logs, verify list returns all 3"""
    session_memory.create_task_log("task-001", "goal 1")
    session_memory.create_task_log("task-002", "goal 2")
    session_memory.create_task_log("task-003", "goal 3")

    logs = session_memory.list_task_logs()
    assert len(logs) == 3
    assert set(logs) == {"task-001", "task-002", "task-003"}

def test_write_and_read_notes(session_memory: SessionMemory):
    """Write note, read back, verify content"""
    session_memory.write_note("This is a scratchpad note.")
    notes = session_memory.read_notes()

    assert notes == "This is a scratchpad note."
