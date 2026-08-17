import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.memory.working import ErrorSignature
from agent.tools.fault_localizer import EditLocation
from agent.tools.fix_searcher import FixSearcher


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    return llm

@pytest.fixture
def mock_sandbox():
    sandbox = AsyncMock()
    return sandbox

@pytest.fixture
def mock_analyzer():
    analyzer = AsyncMock()
    # Default: analyze returns an AnalysisResult-like object with 0 errors
    result = MagicMock()
    result.errors = 0
    analyzer.analyze.return_value = result
    return analyzer

@pytest.fixture
def fix_searcher(mock_llm, mock_sandbox, mock_analyzer):
    return FixSearcher(mock_llm, mock_sandbox, mock_analyzer)

@pytest.mark.asyncio
async def test_search_returns_best_candidate(fix_searcher, mock_llm, mock_sandbox, mock_analyzer, tmp_path):
    mock_llm.complete.side_effect = [
        MagicMock(content=json.dumps({"edits": [{"file": "test.py", "start_line": 1, "end_line": 1, "new_content": "a=1"}]})),
        MagicMock(content=json.dumps({"edits": [{"file": "test.py", "start_line": 1, "end_line": 1, "new_content": "a=2"}]})),
        MagicMock(content=json.dumps({"edits": [{"file": "test.py", "start_line": 1, "end_line": 1, "new_content": "a=3"}]}))
    ]

    # Sandbox returns success for the second candidate
    mock_sandbox.execute.side_effect = [
        MagicMock(exit_code=1),
        MagicMock(exit_code=0),
        MagicMock(exit_code=1)
    ]

    # Create test.py in tmp_path so copytree has something to copy
    (tmp_path / "test.py").write_text("a=0\n")

    error = ErrorSignature(error_type="Error", core_message="fail", raw_message="fail")
    locations = [EditLocation(file_path="test.py", start_line=1, end_line=1, content="a=0", confidence=1.0, reasoning="")]

    best = await fix_searcher.search(error, locations, str(tmp_path), n=3)
    assert best is not None
    assert best.candidate_id == 2
    assert best.tests_passed == 1

@pytest.mark.asyncio
async def test_search_returns_none_when_all_fail(fix_searcher, mock_llm, mock_sandbox, tmp_path):
    mock_llm.complete.return_value = MagicMock(content=json.dumps({"edits": []}))
    mock_sandbox.execute.return_value = MagicMock(exit_code=1)

    error = ErrorSignature(error_type="Error", core_message="fail", raw_message="fail")
    best = await fix_searcher.search(error, [], str(tmp_path), n=3)

    assert best is None

@pytest.mark.asyncio
async def test_candidate_generation_retries(fix_searcher, mock_llm, mock_sandbox, tmp_path):
    """Test that candidate generation calls llm.complete with the right task_type."""
    mock_llm.complete.return_value = MagicMock(content=json.dumps({"edits": []}))
    mock_sandbox.execute.return_value = MagicMock(exit_code=0)

    error = ErrorSignature(error_type="Error", core_message="fail", raw_message="fail")
    await fix_searcher.search(error, [], str(tmp_path), n=1)

    args, kwargs = mock_llm.complete.call_args
    assert kwargs.get("task_type") == "coding"

@pytest.mark.asyncio
async def test_sandbox_timeout_skips_candidate(fix_searcher, mock_llm, mock_sandbox, tmp_path):
    mock_llm.complete.return_value = MagicMock(content=json.dumps({"edits": []}))

    # Simulate a timeout exception
    mock_sandbox.execute.side_effect = TimeoutError("Sandbox timeout")

    error = ErrorSignature(error_type="Error", core_message="fail", raw_message="fail")
    best = await fix_searcher.search(error, [], str(tmp_path), n=1)

    # test_candidate raised TimeoutError, so it wasn't returned in tested_candidates as CodePatch
    assert best is None

@pytest.mark.asyncio
async def test_lint_filter_excludes_bad_candidates(fix_searcher, mock_llm, mock_sandbox, mock_analyzer, tmp_path):
    mock_llm.complete.side_effect = [
        MagicMock(content=json.dumps({"edits": [{"file": "test.py", "start_line": 1, "end_line": 1, "new_content": "a"}]})),
        MagicMock(content=json.dumps({"edits": [{"file": "test.py", "start_line": 1, "end_line": 1, "new_content": "b"}]}))
    ]
    mock_sandbox.execute.return_value = MagicMock(exit_code=0)

    # First candidate introduces 5 lint errors, second candidate introduces 0
    result_bad = MagicMock()
    result_bad.errors = 5
    result_good = MagicMock()
    result_good.errors = 0
    mock_analyzer.analyze.side_effect = [result_bad, result_good]

    # Create test.py in tmp_path
    (tmp_path / "test.py").write_text("x\n")

    error = ErrorSignature(error_type="Error", core_message="fail", raw_message="fail")
    locations = [EditLocation(file_path="test.py", start_line=1, end_line=1, content="x", confidence=1.0, reasoning="")]

    best = await fix_searcher.search(error, locations, str(tmp_path), n=2)
    assert best is not None
    assert best.candidate_id == 2

@pytest.mark.asyncio
async def test_ranking_tiebreaker_fewest_lint(fix_searcher, mock_llm, mock_sandbox, mock_analyzer, tmp_path):
    mock_llm.complete.side_effect = [
        MagicMock(content=json.dumps({"edits": [{"file": "test.py", "start_line": 1, "end_line": 1, "new_content": "a"}]})),
        MagicMock(content=json.dumps({"edits": [{"file": "test.py", "start_line": 1, "end_line": 1, "new_content": "b"}]}))
    ]
    mock_sandbox.execute.return_value = MagicMock(exit_code=0) # Both pass tests

    # First candidate has 10 lint errors, second has 2
    result_10 = MagicMock()
    result_10.errors = 10
    result_2 = MagicMock()
    result_2.errors = 2
    mock_analyzer.analyze.side_effect = [result_10, result_2]

    # Create test.py in tmp_path
    (tmp_path / "test.py").write_text("x\n")

    error = ErrorSignature(error_type="Error", core_message="fail", raw_message="fail")
    locations = [EditLocation(file_path="test.py", start_line=1, end_line=1, content="x", confidence=1.0, reasoning="")]

    best = await fix_searcher.search(error, locations, str(tmp_path), n=2)
    assert best is not None
    assert best.candidate_id == 2
