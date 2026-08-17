import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.memory.failure import FailureMemory, FailureRecord
from agent.reflection.engine import (
    ErrorCategory,
    ErrorSignature,
    Hypothesis,
    ReflectionEngine,
)
from providers.llm import LLMProvider, LLMResponse


@pytest.fixture
def mock_llm() -> AsyncMock:
    llm = AsyncMock(spec=LLMProvider)
    return llm

@pytest.fixture
def mock_failure_memory() -> MagicMock:
    fm = MagicMock(spec=FailureMemory)
    return fm

@pytest.fixture
def reflection_engine(mock_llm: MagicMock, mock_failure_memory: MagicMock) -> ReflectionEngine:
    return ReflectionEngine(llm=mock_llm, failure_memory=mock_failure_memory)

def test_extract_signature_basic(reflection_engine: ReflectionEngine):
    """Verify parsing of standard python traceback"""
    tb = """Traceback (most recent call last):
  File "/app/main.py", line 42, in <module>
    divide(1, 0)
  File "/app/math.py", line 10, in divide
    return a / b
ZeroDivisionError: division by zero"""

    sig = reflection_engine.extract_signature(tb)
    assert sig.error_type == "ZeroDivisionError"
    assert sig.message == "division by zero"
    assert sig.file_path == "/app/math.py"
    assert sig.line_number == 10

def test_extract_signature_no_file_line(reflection_engine: ReflectionEngine):
    """Verify fallback when file/line is missing"""
    tb = "ConnectionError: failed to connect to database"
    sig = reflection_engine.extract_signature(tb)
    assert sig.error_type == "ConnectionError"
    assert sig.message == "failed to connect to database"
    assert sig.file_path == ""
    assert sig.line_number is None

def test_search_failures_returns_fixes(reflection_engine: ReflectionEngine, mock_failure_memory: MagicMock):
    """Verify search returns only successful hypotheses"""
    r1 = FailureRecord(error_signature="E", goal="G", hypothesis="H1", result="Success")
    r2 = FailureRecord(error_signature="E", goal="G", hypothesis="H2", result="Failed")
    mock_failure_memory.search_similar_errors.return_value = [r1, r2]

    sig = ErrorSignature(error_type="E", message="M")
    fixes = reflection_engine.search_failures(sig)

    assert len(fixes) == 1
    assert fixes[0]["hypothesis"] == "H1"
    assert fixes[0]["result"] == "Success"

@pytest.mark.asyncio
async def test_classify_error(reflection_engine: ReflectionEngine, mock_llm: AsyncMock):
    """Verify LLM classification maps to Enum"""
    mock_llm.complete.return_value = LLMResponse(
        content="Syntax", model="test", input_tokens=10, output_tokens=10, cost_usd=0.01, latency_ms=100
    )
    sig = ErrorSignature(error_type="SyntaxError", message="invalid syntax")

    cat = await reflection_engine.classify_error(sig)
    assert cat == ErrorCategory.SYNTAX

@pytest.mark.asyncio
async def test_generate_hypotheses_excludes_tried(reflection_engine: ReflectionEngine, mock_llm: AsyncMock):
    """Verify prompt explicitly lists tried hypotheses"""
    mock_llm.complete.return_value = LLMResponse(
        content=json.dumps([
            {"description": "New fix", "confidence": 0.8, "action_plan": "Do this"}
        ]),
        model="test", input_tokens=10, output_tokens=10, cost_usd=0.01, latency_ms=100
    )

    sig = ErrorSignature(error_type="E", message="M")
    tried = ["Tried fix 1", "Tried fix 2"]

    hypotheses = await reflection_engine.generate_hypotheses(
        sig, "state", ErrorCategory.LOGIC, [], tried
    )

    # Check if tried hypotheses were in the prompt
    args, kwargs = mock_llm.complete.call_args
    prompt = kwargs["messages"][1]["content"]
    assert "Tried fix 1" in prompt
    assert "Tried fix 2" in prompt

    assert len(hypotheses) == 1
    assert hypotheses[0].description == "New fix"

def test_select_best_hypothesis(reflection_engine: ReflectionEngine):
    """Verify hypothesis with highest confidence is returned"""
    h1 = Hypothesis(description="A", confidence=0.2, action_plan="A")
    h2 = Hypothesis(description="B", confidence=0.9, action_plan="B")
    h3 = Hypothesis(description="C", confidence=0.5, action_plan="C")

    best = reflection_engine.select_best_hypothesis([h1, h2, h3])
    assert best.description == "B"

@pytest.mark.asyncio
async def test_full_reflect_pipeline(reflection_engine: ReflectionEngine, mock_llm: AsyncMock, mock_failure_memory: MagicMock):
    """Verify all 6 steps execute in order"""
    tb = "TypeError: 'int' object is not iterable"

    # Mock search
    mock_failure_memory.search_similar_errors.return_value = []

    # Mock LLM (it gets called twice: classify and hypothesize)
    mock_llm.complete.side_effect = [
        LLMResponse(content="type", model="test", input_tokens=10, output_tokens=10, cost_usd=0.01, latency_ms=100), # classification
        LLMResponse(
            content=json.dumps([
                {"description": "Wrap in list", "confidence": 0.9, "action_plan": "Use [x]"},
                {"description": "Cast to str", "confidence": 0.4, "action_plan": "Use str(x)"}
            ]),
            model="test", input_tokens=10, output_tokens=10, cost_usd=0.01, latency_ms=100
        ) # generate
    ]

    chosen = await reflection_engine.reflect(tb, "current state", ["Use tuple"])

    assert chosen.category == ErrorCategory.TYPE
    assert chosen.description == "Wrap in list"
    assert chosen.confidence == 0.9
