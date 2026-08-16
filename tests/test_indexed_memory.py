import os
import pytest
import sqlite3
from pathlib import Path
from datetime import datetime
from agent.memory.indexed import IndexedMemory, MemoryEntry
from agent.memory.session import SessionMemory, MemoryCategory

@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test_index.db")

@pytest.fixture
def indexed_memory(db_path: str) -> IndexedMemory:
    return IndexedMemory(db_path=db_path)

@pytest.fixture
def session_memory(tmp_path: Path) -> SessionMemory:
    return SessionMemory(memory_dir=str(tmp_path / "session"))

def test_initialize_creates_database(indexed_memory: IndexedMemory, db_path: str):
    """Verify db file exists after init"""
    assert Path(db_path).exists()
    
    # Verify table schema
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memory_index'")
        assert cursor.fetchone() is not None

def test_index_and_search_basic(indexed_memory: IndexedMemory):
    """Index 3 entries, search for keyword, verify match"""
    indexed_memory.index(MemoryEntry(content="apple is red", source="test", category="fact"))
    indexed_memory.index(MemoryEntry(content="banana is yellow", source="test", category="fact"))
    indexed_memory.index(MemoryEntry(content="cherry is also red", source="test", category="fact"))
    
    results = indexed_memory.search("red")
    assert len(results) == 2
    contents = {r.content for r in results}
    assert "apple is red" in contents
    assert "cherry is also red" in contents

def test_search_with_category_filter(indexed_memory: IndexedMemory):
    """Index entries in different categories, search with filter"""
    indexed_memory.index(MemoryEntry(content="Docker is used", source="test", category="architecture"))
    indexed_memory.index(MemoryEntry(content="Docker is hard", source="test", category="opinion"))
    
    results = indexed_memory.search("Docker", category="architecture")
    assert len(results) == 1
    assert results[0].content == "Docker is used"

def test_search_relevance_ranking(indexed_memory: IndexedMemory):
    """Index entries with varying relevance, verify rank order"""
    # SQLite FTS5 ranks lower values as MORE relevant (more negative).
    # "red" appears multiple times in the first string.
    indexed_memory.index(MemoryEntry(content="red apple is very red and sometimes red", source="test", category="fact"))
    indexed_memory.index(MemoryEntry(content="apple is just red once", source="test", category="fact"))
    
    results = indexed_memory.search("red")
    assert len(results) == 2
    assert results[0].content == "red apple is very red and sometimes red"

def test_search_dotted_identifiers(indexed_memory: IndexedMemory):
    """Index auth.middleware.validate_token, search for auth.middleware, verify match"""
    indexed_memory.index(MemoryEntry(content="Use auth.middleware.validate_token", source="test", category="fact"))
    
    results = indexed_memory.search("auth.middleware")
    assert len(results) == 1
    assert results[0].content == "Use auth.middleware.validate_token"

def test_search_empty_query_returns_empty(indexed_memory: IndexedMemory):
    """Verify empty list"""
    indexed_memory.index(MemoryEntry(content="test data", source="test", category="fact"))
    assert len(indexed_memory.search("")) == 0
    assert len(indexed_memory.search("   ")) == 0

def test_search_no_results(indexed_memory: IndexedMemory):
    """Search for nonexistent term, verify empty list"""
    indexed_memory.index(MemoryEntry(content="apple is red", source="test", category="fact"))
    assert len(indexed_memory.search("grape")) == 0

def test_index_batch(indexed_memory: IndexedMemory):
    """Batch insert 10 entries, verify all searchable"""
    entries = [
        MemoryEntry(content=f"Item number {i}", source="test", category="fact") 
        for i in range(10)
    ]
    indexed_memory.index_batch(entries)
    results = indexed_memory.search("number")
    assert len(results) == 10

def test_reindex_from_markdown(indexed_memory: IndexedMemory, session_memory: SessionMemory):
    """Create MEMORY.md with entries, reindex, verify searchable"""
    session_memory.append_fact("FastAPI is fast", MemoryCategory.ARCHITECTURE, "task_1")
    session_memory.append_fact("Always use dicts", MemoryCategory.CONVENTION, "task_2")
    
    session_memory.create_task_log("task_3", "fix bug")
    session_memory.append_to_task_log("task_3", 1, "tried caching")
    
    indexed_memory.reindex_from_markdown(session_memory)
    
    # Should find architecture fact
    res1 = indexed_memory.search("FastAPI")
    assert len(res1) == 1
    assert "FastAPI is fast" in res1[0].content
    assert res1[0].category == "architecture"
    
    # Should find task log entry
    res2 = indexed_memory.search("caching")
    assert len(res2) == 1
    assert "tried caching" in res2[0].content

def test_get_stats(indexed_memory: IndexedMemory):
    """Index entries, verify stats are correct"""
    indexed_memory.index(MemoryEntry(content="A", source="s", category="cat1"))
    indexed_memory.index(MemoryEntry(content="B", source="s", category="cat1"))
    indexed_memory.index(MemoryEntry(content="C", source="s", category="cat2"))
    
    stats = indexed_memory.get_stats()
    assert stats["total_entries"] == 3
    
    cat_stats = stats["entries_per_category"]
    assert isinstance(cat_stats, dict)
    assert cat_stats["cat1"] == 2
    assert cat_stats["cat2"] == 1

def test_delete_by_task(indexed_memory: IndexedMemory):
    """Index entries with task_id, delete, verify gone"""
    indexed_memory.index(MemoryEntry(content="Data 1", source="s", category="c", task_id="t1"))
    indexed_memory.index(MemoryEntry(content="Data 2", source="s", category="c", task_id="t2"))
    
    indexed_memory.delete_by_task("t1")
    
    # Data 1 should be gone
    res = indexed_memory.search("Data")
    assert len(res) == 1
    assert res[0].task_id == "t2"

def test_fts5_special_chars_escaped(indexed_memory: IndexedMemory):
    """Search with query containing " or *, verify no crash"""
    indexed_memory.index(MemoryEntry(content='User said "hello"', source="test", category="fact"))
    indexed_memory.index(MemoryEntry(content="import *", source="test", category="fact"))
    
    # Should not throw sqlite3.OperationalError
    res1 = indexed_memory.search('said "hello"')
    assert len(res1) == 1
    
    res2 = indexed_memory.search("import *")
    assert len(res2) == 1
