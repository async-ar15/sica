import pytest

from agent.core.context_manager import ContextManager
from agent.memory.failure import FailureRecord
from agent.memory.working import WorkingMemory
from agent.tools.fault_localizer import EditLocation


@pytest.fixture
def context_manager():
    # Small token limit to easily trigger compaction in tests
    return ContextManager(max_tokens=100)

@pytest.fixture
def memory():
    mem = WorkingMemory()
    mem.current_goal = "Test goal"
    mem.last_error = "Traceback (most recent call last):\n  File 'test.py', line 1\n    Error"
    mem.tried_hypotheses.add("Hypo 1")
    return mem

def test_build_prompt_all_layers():
    cm = ContextManager(max_tokens=100000)
    mem = WorkingMemory()
    mem.current_goal = "Goal"
    failures = [FailureRecord(error_signature="Err", goal="G", hypothesis="H", result="R")]
    faults = [EditLocation(file_path="a.py", start_line=1, end_line=2, content="def test(): pass", confidence=1.0, reasoning="test")]
    repo_map = "a.py\nb.py"
    logs = "System starting..."

    prompt = cm.build_prompt("coding", mem, failures=failures, repo_map=repo_map, fault_locations=faults, raw_logs=logs)
    content = prompt[1]["content"]

    assert "Goal: Goal" in content
    assert "Repo Map:" in content
    assert "a.py" in content
    assert "Fault Locations:" in content
    assert "Related Past Failures:" in content
    assert "Working Memory:" in content
    assert "Terminal Output / Logs:" in content
    assert "System starting..." in content

def test_compaction_triggers(context_manager, memory):
    # Logs alone > 25 tokens (100 chars)
    logs = "A" * 1500
    prompt = context_manager.build_prompt("coding", memory, raw_logs=logs)
    content = prompt[1]["content"]

    # Should say Truncated
    assert "Terminal Output (Truncated):" in content
    assert len(content) < 1500 + 300 # Should be compacted to ~1000 chars + memory

def test_compaction_preserves_errors(context_manager, memory):
    # Trigger layer 5 compaction by adding large logs and large memory
    logs = "A" * 400
    memory.last_error = "CRITICAL_ERROR_SIGNATURE " + "B" * 500

    prompt = context_manager.build_prompt("coding", memory, raw_logs=logs)
    content = prompt[1]["content"]

    assert "Working Memory (Compacted):" in content
    assert "CRITICAL_ERROR_SIGNATURE" in content
    assert "Hypo 1" in content

def test_compaction_preserves_paths(context_manager, memory):
    # Trigger layer 2 compaction
    logs = "A" * 400
    repo_map = "dir/\n  file1.py\n  file2.py\ndir2/\n  file3.py"

    prompt = context_manager.build_prompt("coding", memory, repo_map=repo_map, raw_logs=logs)
    content = prompt[1]["content"]

    assert "Repo Map (Compacted):" in content
    # Shallow items should remain
    assert "dir/" in content
    assert "dir2/" in content
    # Indented items removed
    assert "file1.py" not in content
