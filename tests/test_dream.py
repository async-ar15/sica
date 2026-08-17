import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.memory.dream import DreamEngine, DreamReport
from agent.memory.failure import FailureMemory
from agent.memory.indexed import IndexedMemory
from agent.memory.session import MemoryCategory, SessionMemory


@pytest.fixture
def mock_embeddings():
    emb = MagicMock()
    # Return dummy vectors
    emb.embed_batch.return_value = [[1.0, 0.0], [0.99, 0.14]]
    return emb

@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.complete.return_value = MagicMock(content="Summary of logs")
    return llm

@pytest.fixture
def dream_engine(tmp_path, mock_embeddings, mock_llm):
    session = SessionMemory(memory_dir=str(tmp_path / "memory"))
    indexed = IndexedMemory(db_path=str(tmp_path / "memory.db"))
    failure = MagicMock(spec=FailureMemory)
    failure.prune.return_value = 1

    return DreamEngine(session, indexed, failure, mock_embeddings, mock_llm)

@pytest.mark.asyncio
async def test_scan_returns_inventory(dream_engine):
    dream_engine.session.append_fact("fact1", MemoryCategory.FACT, "task1")
    dream_engine.session.append_fact("fact2", MemoryCategory.FACT, "task2")

    with dream_engine.indexed._get_connection() as conn:
        conn.execute("INSERT INTO memory_index (content) VALUES (?)", ("fact1",))

    inv = dream_engine._scan()
    assert inv["total_entries"] == 3 # 2 lines + 1 DB

@pytest.mark.asyncio
async def test_deduplicate_merges_similar(dream_engine, mock_embeddings):
    with dream_engine.indexed._get_connection() as conn:
        conn.execute("INSERT INTO memory_index (content) VALUES (?)", ("short",))
        conn.execute("INSERT INTO memory_index (content) VALUES (?)", ("longer content",))

    merges = await dream_engine._deduplicate()
    assert merges == 1

    assert dream_engine.indexed.get_stats().get("total_entries", 0) == 1
    with dream_engine.indexed._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT content FROM memory_index")
        contents = [row[0] for row in cursor.fetchall()]

    assert contents[0] == "longer content"

@pytest.mark.asyncio
async def test_validate_finds_stale_paths(dream_engine, tmp_path):
    dream_engine.session.append_fact("check `missing.py`", MemoryCategory.FACT, "task1")

    val, stale = dream_engine._validate_paths(str(tmp_path))
    assert val == 1
    assert stale == 1

    content = dream_engine.session.read_memory()
    assert "[PATH NOT FOUND]" in content

@pytest.mark.asyncio
async def test_validate_valid_paths_untouched(dream_engine, tmp_path):
    p = tmp_path / "exists.py"
    p.write_text("code")

    dream_engine.session.append_fact("check `exists.py`", MemoryCategory.FACT, "task1")

    val, stale = dream_engine._validate_paths(str(tmp_path))
    assert val == 1
    assert stale == 0

    content = dream_engine.session.read_memory()
    assert "[PATH NOT FOUND]" not in content

@pytest.mark.asyncio
async def test_compress_moves_old_logs(dream_engine):
    task_id = "old_task"
    dream_engine.session.create_task_log(task_id, "goal")
    log_file = dream_engine.session.task_logs_dir / f"{task_id}.md"

    # Make it 8 days old
    old_time = (datetime.now(UTC) - timedelta(days=8)).timestamp()
    os.utime(log_file, (old_time, old_time))

    compressed = await dream_engine._compress_old_logs(max_age_days=7)
    assert compressed == 1

    # Check archive
    archive_file = dream_engine.session.task_logs_dir / "archive" / f"{task_id}.md"
    assert archive_file.exists()

    # Check original is now a summary
    content = dream_engine.session.get_task_log(task_id)
    assert "Summary of logs" in content

@pytest.mark.asyncio
async def test_compress_preserves_recent_logs(dream_engine):
    task_id = "new_task"
    dream_engine.session.create_task_log(task_id, "goal")

    compressed = await dream_engine._compress_old_logs(max_age_days=7)
    assert compressed == 0

def test_prune_removes_old_failures(dream_engine):
    pruned = dream_engine._prune_failures()
    assert pruned == 1
    dream_engine.failure.prune.assert_called_once()

@pytest.mark.asyncio
async def test_empty_memory_no_crash(dream_engine, tmp_path):
    report = await dream_engine.run(str(tmp_path))
    assert report.summary == "No memory to maintain"

@pytest.mark.asyncio
async def test_full_dream_returns_report(dream_engine, tmp_path):
    dream_engine.session.append_fact("fact", MemoryCategory.FACT, "task1")
    report = await dream_engine.run(str(tmp_path))

    assert isinstance(report, DreamReport)
    assert "Dream cycle complete" in report.summary
