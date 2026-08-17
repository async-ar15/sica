from unittest.mock import MagicMock, patch

import litellm
import pytest
from httpx import Request, Response

from providers.llm import LLMProvider, LLMResponse


@pytest.fixture
def provider() -> LLMProvider:
    return LLMProvider()

def test_model_routing_returns_correct_model(provider: LLMProvider) -> None:
    model = provider.get_model_for_task("coding")
    assert model == "gemini/gemini-3.5-flash-lite"

@pytest.mark.asyncio
@patch("providers.llm.litellm.acompletion")
@patch("providers.llm.litellm.completion_cost")
async def test_complete_returns_llm_response(mock_cost: MagicMock, mock_acompletion: MagicMock, provider: LLMProvider) -> None:
    mock_resp = MagicMock()
    mock_resp.usage.prompt_tokens = 10
    mock_resp.usage.completion_tokens = 20
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = "hello"
    mock_acompletion.return_value = mock_resp
    mock_cost.return_value = 0.05

    response = await provider.complete("coding", [{"role": "user", "content": "hi"}])

    assert isinstance(response, LLMResponse)
    assert response.content == "hello"
    assert response.input_tokens == 10
    assert response.output_tokens == 20
    assert response.cost_usd == 0.05
    assert response.model == "gemini/gemini-3.5-flash-lite"
    assert response.latency_ms >= 0

@pytest.mark.asyncio
@patch("providers.llm.litellm.acompletion")
@patch("providers.llm.litellm.completion_cost")
async def test_cost_tracking_accumulates(mock_cost: MagicMock, mock_acompletion: MagicMock, provider: LLMProvider) -> None:
    mock_resp = MagicMock()
    mock_resp.usage.prompt_tokens = 10
    mock_resp.usage.completion_tokens = 20
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = "hello"
    mock_acompletion.return_value = mock_resp
    mock_cost.return_value = 0.05

    await provider.complete("coding", [{"role": "user", "content": "hi"}])
    await provider.complete("coding", [{"role": "user", "content": "hi"}])

    assert provider.get_total_cost() == 0.10

@pytest.mark.asyncio
@patch("providers.llm.litellm.acompletion")
@patch("providers.llm.litellm.completion_cost")
async def test_token_tracking_accumulates(mock_cost: MagicMock, mock_acompletion: MagicMock, provider: LLMProvider) -> None:
    mock_resp = MagicMock()
    mock_resp.usage.prompt_tokens = 10
    mock_resp.usage.completion_tokens = 20
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = "hello"
    mock_acompletion.return_value = mock_resp
    mock_cost.return_value = 0.05

    await provider.complete("coding", [{"role": "user", "content": "hi"}])
    await provider.complete("coding", [{"role": "user", "content": "hi"}])

    assert provider.get_total_tokens() == 60

def test_reset_counters_zeros_out(provider: LLMProvider) -> None:
    provider.total_cost = 5.0
    provider.total_tokens = 100
    provider.reset_counters()
    assert provider.get_total_cost() == 0.0
    assert provider.get_total_tokens() == 0

@pytest.mark.asyncio
@patch("providers.llm.litellm.acompletion")
async def test_auth_error_gives_clear_message(mock_acompletion: MagicMock, provider: LLMProvider) -> None:
    req = Request("POST", "https://api.openai.com/v1/chat/completions")
    resp = Response(401, request=req)
    mock_acompletion.side_effect = litellm.AuthenticationError("auth error", llm_provider="openai", model="gpt-4", response=resp)

    with pytest.raises(ValueError, match="API key for"):
        await provider.complete("coding", [{"role": "user", "content": "hi"}])

@pytest.mark.asyncio
@patch("providers.llm.litellm.acompletion")
async def test_model_not_found_gives_clear_message(mock_acompletion: MagicMock, provider: LLMProvider) -> None:
    req = Request("POST", "https://api.openai.com/v1/chat/completions")
    resp = Response(404, request=req)
    mock_acompletion.side_effect = litellm.NotFoundError("model not found", llm_provider="openai", model="gpt-4", response=resp)

    with pytest.raises(ValueError, match="not found. Check config/models.yaml"):
        await provider.complete("coding", [{"role": "user", "content": "hi"}])

def test_env_var_override(monkeypatch: pytest.MonkeyPatch, provider: LLMProvider) -> None:
    monkeypatch.setenv("AGENT_MODEL_PLANNING", "openai/gpt-4o")
    model = provider.get_model_for_task("planning")
    assert model == "openai/gpt-4o"

@pytest.mark.asyncio
@patch("providers.llm.litellm.acompletion")
@patch("providers.llm.litellm.completion_cost")
async def test_retry_on_rate_limit(mock_cost: MagicMock, mock_acompletion: MagicMock, provider: LLMProvider) -> None:
    mock_resp = MagicMock()
    mock_resp.usage.prompt_tokens = 10
    mock_resp.usage.completion_tokens = 20
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = "hello"
    mock_cost.return_value = 0.05

    req = Request("POST", "https://api.openai.com/v1/chat/completions")
    resp = Response(429, request=req)

    mock_acompletion.side_effect = [
        litellm.RateLimitError("rate limit", llm_provider="openai", model="gpt-4", response=resp),
        mock_resp
    ]

    with patch("tenacity.nap.time.sleep"), patch("asyncio.sleep"):
        response = await provider.complete("coding", [{"role": "user", "content": "hi"}])

    assert response.content == "hello"
    assert mock_acompletion.call_count == 2
