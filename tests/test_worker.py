from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.agents.architect import SubTask
from agent.agents.judge import Verdict
from agent.agents.worker import CodeResult, WorkerAgent
from agent.safety.static_analysis import LintError


@pytest.fixture
def mock_llm():
    return AsyncMock()

@pytest.fixture
def mock_tools():
    tools = MagicMock()
    tools.get_tool_definitions.return_value = []
    tools.execute = AsyncMock()
    return tools

@pytest.fixture
def worker(mock_llm, mock_tools):
    return WorkerAgent(mock_llm, mock_tools)

@pytest.mark.asyncio
async def test_worker_executes_tool_calls(worker, mock_llm, mock_tools):
    # In a real implementation, the worker would parse tool calls from the LLM.
    # We are mocking the LLM response.
    mock_llm.complete.return_value = MagicMock(content="Mocked response")

    plan = SubTask(task_id="A", description="A")
    result = await worker.execute(plan, "context")

    assert result.success is True
    # We haven't fully implemented tool extraction yet, so tool_calls_made is empty.
    # In the future, we would verify mock_tools.execute.call_count here.

@pytest.mark.asyncio
async def test_worker_returns_code_result(worker, mock_llm, mock_tools):
    mock_llm.complete.return_value = MagicMock(content="Mocked response")

    plan = SubTask(task_id="A", description="A")
    result = await worker.execute(plan, "context")

    assert isinstance(result, CodeResult)
    assert hasattr(result, "files_modified")
    assert hasattr(result, "files_created")
    assert hasattr(result, "tool_calls_made")

@pytest.mark.asyncio
async def test_worker_fix_lint(worker, mock_llm, mock_tools):
    mock_llm.complete.return_value = MagicMock(content="Mocked fix")

    lint_errors = [
        LintError(file="a.py", line=1, message="Missing docstring", tool="ruff", code="E")
    ]
    result = await worker.fix_lint(lint_errors)

    assert result.success is True
    assert mock_llm.complete.call_args[1]["task_type"] == "lint_fix"

@pytest.mark.asyncio
async def test_worker_revise_from_verdict(worker, mock_llm, mock_tools):
    mock_llm.complete.return_value = MagicMock(content="Mocked revision")

    verdict = Verdict(approved=False, confidence=1.0, issues=["issue1"])
    code_result = CodeResult()

    result = await worker.revise(code_result, verdict)

    assert result.success is True
    assert mock_llm.complete.call_args[1]["task_type"] == "coding"
