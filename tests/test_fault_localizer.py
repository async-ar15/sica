import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.reflection.engine import ErrorCategory, Hypothesis
from agent.tools.fault_localizer import FaultLocalizer
from agent.tools.repo_map import RepoMap
from providers.llm import LLMProvider, LLMResponse


@pytest.fixture
def mock_llm() -> AsyncMock:
    llm = AsyncMock(spec=LLMProvider)
    return llm

@pytest.fixture
def mock_repo_map() -> MagicMock:
    rm = MagicMock(spec=RepoMap)
    rm.to_markdown.return_value = "📄 `main.py`\n  - ⚡ `func` *(Line 10)*"
    return rm

@pytest.fixture
def fault_localizer(mock_llm: AsyncMock, mock_repo_map: MagicMock) -> FaultLocalizer:
    return FaultLocalizer(llm=mock_llm, repo_map=mock_repo_map)

@pytest.mark.asyncio
async def test_localize_success(
    fault_localizer: FaultLocalizer, mock_llm: AsyncMock, mock_repo_map: MagicMock
) -> None:
    """Verify localization parses LLM JSON successfully"""
    mock_llm.complete.return_value = LLMResponse(
        content=json.dumps({
            "summary": "Fix in main.py",
            "locations": [
                {
                    "file_path": "main.py",
                    "start_line": 10,
                    "end_line": 12,
                    "content": "def func():\n    pass",
                    "confidence": 0.95,
                    "reasoning": "This is where it failed."
                }
            ]
        }),
        model="test", input_tokens=10, output_tokens=10, cost_usd=0.01, latency_ms=100
    )

    hyp = Hypothesis(
        description="Fix it", confidence=0.9, action_plan="Do X", category=ErrorCategory.LOGIC
    )

    result = await fault_localizer.localize(hyp, "Traceback info", "Current state")

    assert result.summary == "Fix in main.py"
    assert len(result.locations) == 1

    loc = result.locations[0]
    assert loc.file_path == "main.py"
    assert loc.start_line == 10
    assert loc.end_line == 12
    assert loc.confidence == 0.95
    assert loc.reasoning == "This is where it failed."

    # Verify repo map was used
    mock_repo_map.to_markdown.assert_called_once()

    # Verify LLM was called with right task_type
    mock_llm.complete.assert_called_once()
    args, kwargs = mock_llm.complete.call_args
    assert kwargs.get("task_type") == "localization"

@pytest.mark.asyncio
async def test_localize_llm_failure(fault_localizer: FaultLocalizer, mock_llm: AsyncMock) -> None:
    """Verify fallback gracefully handles LLM exceptions"""
    mock_llm.complete.side_effect = Exception("API Error")

    hyp = Hypothesis(
        description="Fix", confidence=0.9, action_plan="X", category=ErrorCategory.UNKNOWN
    )
    result = await fault_localizer.localize(hyp, "TB", "State")

    assert "Failed to localize: API Error" in result.summary
    assert len(result.locations) == 0

@pytest.mark.asyncio
async def test_localize_bad_json(fault_localizer: FaultLocalizer, mock_llm: AsyncMock) -> None:
    """Verify fallback gracefully handles malformed JSON"""
    mock_llm.complete.return_value = LLMResponse(
        content="This is not JSON",
        model="test", input_tokens=10, output_tokens=10, cost_usd=0.01, latency_ms=100
    )

    hyp = Hypothesis(
        description="Fix", confidence=0.9, action_plan="X", category=ErrorCategory.UNKNOWN
    )
    result = await fault_localizer.localize(hyp, "TB", "State")

    assert "Failed to localize: Expecting value" in result.summary
    assert len(result.locations) == 0
