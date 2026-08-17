import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.agents.architect import SubTask
from agent.agents.judge import JudgeAgent
from agent.agents.worker import CodeResult


@pytest.fixture
def mock_llm():
    return AsyncMock()

@pytest.fixture
def judge(mock_llm):
    return JudgeAgent(mock_llm)

@pytest.mark.asyncio
async def test_judge_approves_good_code(judge, mock_llm):
    verdict_json = json.dumps({
        "approved": True,
        "confidence": 0.9,
        "issues": [],
        "suggestions": [],
        "reasoning": "Looks good."
    })
    mock_llm.complete.return_value = MagicMock(content=verdict_json)

    code_result = CodeResult()
    plan = SubTask(task_id="A", description="A")

    verdict = await judge.review(code_result, plan, tests_exist=True)
    assert verdict.approved is True

@pytest.mark.asyncio
async def test_judge_rejects_bad_code(judge, mock_llm):
    verdict_json = json.dumps({
        "approved": False,
        "confidence": 0.8,
        "issues": ["No error handling"],
        "suggestions": ["Add try-except"],
        "reasoning": "Code might crash."
    })
    mock_llm.complete.return_value = MagicMock(content=verdict_json)

    code_result = CodeResult()
    plan = SubTask(task_id="A", description="A")

    verdict = await judge.review(code_result, plan, tests_exist=False)
    assert verdict.approved is False
    assert "No error handling" in verdict.issues

@pytest.mark.asyncio
async def test_verdict_has_confidence(judge, mock_llm):
    verdict_json = json.dumps({
        "approved": True,
        "confidence": 0.95,
        "issues": [],
        "suggestions": [],
        "reasoning": "Looks good."
    })
    mock_llm.complete.return_value = MagicMock(content=verdict_json)

    code_result = CodeResult()
    plan = SubTask(task_id="A", description="A")

    verdict = await judge.review(code_result, plan, tests_exist=True)
    assert verdict.confidence == 0.95

@pytest.mark.asyncio
async def test_verdict_has_issues_and_suggestions(judge, mock_llm):
    verdict_json = json.dumps({
        "approved": False,
        "confidence": 0.95,
        "issues": ["Issue 1"],
        "suggestions": ["Suggestion 1"],
        "reasoning": "Need fix."
    })
    mock_llm.complete.return_value = MagicMock(content=verdict_json)

    code_result = CodeResult()
    plan = SubTask(task_id="A", description="A")

    verdict = await judge.review(code_result, plan, tests_exist=True)
    assert len(verdict.issues) == 1
    assert verdict.issues[0] == "Issue 1"
    assert len(verdict.suggestions) == 1
    assert verdict.suggestions[0] == "Suggestion 1"
