import os
import time
from collections.abc import AsyncIterator
from typing import Any

import litellm  # pyright: ignore[reportMissingImports]
import yaml
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class LLMResponse(BaseModel):
    content: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str
    latency_ms: int

class LLMProvider:
    def __init__(self, config_path: str = "config/models.yaml") -> None:
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        self.routing = self.config.get("routing", {})
        self.total_cost = 0.0
        self.total_tokens = 0

    def get_model_for_task(self, task_type: str) -> str:
        env_override = os.getenv(f"AGENT_MODEL_{task_type.upper()}")
        if env_override:
            return env_override
        model = self.routing.get(task_type)
        if not model:
            raise ValueError(f"No model configured for task type: {task_type}")
        return str(model)

    def reset_counters(self) -> None:
        self.total_cost = 0.0
        self.total_tokens = 0

    def get_total_cost(self) -> float:
        return self.total_cost

    def get_total_tokens(self) -> int:
        return self.total_tokens

    def _handle_litellm_error(self, e: Exception, model: str) -> None:
        if isinstance(e, litellm.AuthenticationError):  # type: ignore[attr-defined] # litellm typings lack explicit exports
            provider = model.split("/")[0] if "/" in model else "provider"
            raise ValueError(
                f"API key for {provider} is invalid or missing. Check your .env file."
            ) from e
        if isinstance(e, litellm.NotFoundError):  # type: ignore[attr-defined] # litellm typings lack explicit exports
            raise ValueError(
                f"Model {model} not found. Check config/models.yaml. "
                "Remember: Gemini models need 'gemini/' prefix."
            ) from e
        raise e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        retry=retry_if_exception_type((litellm.RateLimitError, litellm.ServiceUnavailableError))  # type: ignore[attr-defined] # litellm typings lack explicit exports
    )
    async def _do_acompletion(
        self,
        model: str,
        messages: list[dict[str, Any]],
        response_format: type[Any] | None = None
    ) -> Any:
        try:
            return await litellm.acompletion(
                model=model,
                messages=messages,
                response_format=response_format,
            )
        except Exception as e:
            self._handle_litellm_error(e, model)

    async def complete(
        self,
        task_type: str,
        messages: list[dict[str, Any]],
        response_format: type[Any] | None = None
    ) -> LLMResponse:
        model = self.get_model_for_task(task_type)
        start_time = time.time()

        response = await self._do_acompletion(model, messages, response_format)

        latency_ms = int((time.time() - start_time) * 1000)

        usage = response.usage if hasattr(response, "usage") else None
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        try:
            cost = litellm.completion_cost(completion_response=response)
        except Exception:
            cost = 0.0

        self.total_tokens += (input_tokens + output_tokens)
        self.total_cost += cost

        return LLMResponse(
            content=response.choices[0].message.content or "",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            model=model,
            latency_ms=latency_ms
        )

    async def stream(
        self, task_type: str, messages: list[dict[str, Any]]
    ) -> AsyncIterator[str]:
        model = self.get_model_for_task(task_type)

        try:
            response_stream = await litellm.acompletion(
                model=model,
                messages=messages,
                stream=True
            )
            async for chunk in response_stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            self._handle_litellm_error(e, model)
