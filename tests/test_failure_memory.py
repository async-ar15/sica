from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.memory.failure import FailureMemory, FailureRecord
from providers.embeddings import EmbeddingProvider


@pytest.fixture
def mock_provider() -> MagicMock:
    provider = MagicMock(spec=EmbeddingProvider)
    # Return a dummy 384-dimensional vector
    provider.embed.return_value = [0.1] * 384
    return provider

@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "failures_test")

@pytest.fixture
def failure_memory(db_path: str, mock_provider: MagicMock) -> FailureMemory:
    # ChromaDB persistent client can take some time to init, but it works in tmp_path
    return FailureMemory(db_path=db_path, provider=mock_provider)

def test_init_creates_collection(failure_memory: FailureMemory) -> None:
    """Verify collection is created with correct metadata"""
    if not failure_memory.enabled:
        pytest.skip("ChromaDB not installed")

    assert failure_memory.collection is not None
    assert failure_memory.collection.name == "agent_failures"
    # Need to check metadata
    assert failure_memory.collection.metadata.get("hnsw:space") == "cosine"

def test_init_no_chromadb(db_path: str, mock_provider: MagicMock) -> None:
    """Mock ImportError, verify graceful fallback"""
    with patch.dict('sys.modules', {'chromadb': None}):
        fm = FailureMemory(db_path=db_path, provider=mock_provider)
        assert not fm.enabled
        assert fm.collection is None

def test_record_and_search_failure(failure_memory: FailureMemory, mock_provider: MagicMock) -> None:
    """Record a failure, search for it, verify retrieval"""
    if not failure_memory.enabled:
        pytest.skip("ChromaDB not installed")

    record = FailureRecord(
        error_signature="KeyError: 'user'",
        goal="Fetch user data",
        hypothesis="Try dict.get() instead",
        result="Success"
    )

    failure_memory.record_failure(record)

    # Provider should have been called
    mock_provider.embed.assert_called_with("KeyError: 'user'")

    # Now search
    mock_provider.embed.return_value = [0.1] * 384 # same embedding to get distance ~0
    results = failure_memory.search_similar_errors("KeyError", limit=1)

    assert len(results) == 1
    assert results[0].error_signature == "KeyError: 'user'"
    assert results[0].goal == "Fetch user data"
    assert results[0].hypothesis == "Try dict.get() instead"

def test_search_respects_threshold(failure_memory: FailureMemory, mock_provider: MagicMock) -> None:
    """Search with tight threshold, mock distance above threshold, verify empty"""
    if not failure_memory.enabled:
        pytest.skip("ChromaDB not installed")

    record = FailureRecord(
        error_signature="ValueError: bad format",
        goal="Parse data",
        hypothesis="Use try/except",
        result="Success"
    )

    # We need to bypass the actual collection.query to inject a high distance
    # for the test, or rely on chromadb. Since we mocked embed, all vectors are identical (distance=0).
    # We will mock collection.query directly.
    assert failure_memory.collection is not None
    failure_memory.collection.query = MagicMock(return_value={
        "ids": [["1"]],
        "embeddings": None,
        "documents": [["ValueError: bad format"]],
        "metadatas": [[{
            "error_signature": "ValueError: bad format",
            "goal": "Parse data",
            "hypothesis": "Use try/except",
            "result": "Success",
            "timestamp": datetime.now(UTC).isoformat()
        }]],
        "distances": [[0.5]] # High distance (above default 0.3 threshold)
    })

    results = failure_memory.search_similar_errors("ValueError", distance_threshold=0.3)
    assert len(results) == 0

def test_provider_disabled_fallback(failure_memory: FailureMemory, mock_provider: MagicMock) -> None:
    """Provider fails to embed, verify safe exit"""
    if not failure_memory.enabled:
        pytest.skip("ChromaDB not installed")

    mock_provider.embed.return_value = []

    record = FailureRecord(
        error_signature="Test", goal="T", hypothesis="T", result="T"
    )

    # Should not crash
    failure_memory.record_failure(record)
    results = failure_memory.search_similar_errors("Test")
    assert len(results) == 0
