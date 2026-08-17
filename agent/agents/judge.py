import json
from typing import TYPE_CHECKING

from pydantic import BaseModel

from agent.agents.architect import SubTask
from providers.llm import LLMProvider

if TYPE_CHECKING:
    from agent.agents.worker import CodeResult

class Verdict(BaseModel):
    """Judge's review of code changes."""
    approved: bool
    confidence: float = 0.5
    issues: list[str] = []
    suggestions: list[str] = []
    reasoning: str = ""

class JudgeAgent:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def review(self, code_changes: "CodeResult", plan: SubTask, tests_exist: bool) -> Verdict:
        # We would normally read the content of modified/created files here.
        prompt = (
            "You are a code reviewer. Check for correctness, edge cases, error handling, code quality, and security.\n\n"
            f"Plan (SubTask): {plan.description}\n\n"
            f"Files modified: {code_changes.files_modified}\n"
            f"Files created: {code_changes.files_created}\n"
            f"Tests exist: {tests_exist}\n\n"
            "Evaluate the changes and provide a verdict."
        )

        messages = [
            {"role": "system", "content": "You are a code reviewer."},
            {"role": "user", "content": prompt}
        ]

        for _ in range(3):
            response = await self.llm.complete(
                task_type="judge_review",
                messages=messages,
                response_format=Verdict
            )
            try:
                content = response.content
                if isinstance(content, str):
                    verdict_dict = json.loads(content)
                    return Verdict(**verdict_dict)
                else:
                    return Verdict(**content)
            except Exception:
                pass

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": "The generated output was invalid. Please try again."})

        raise ValueError("Failed to generate a valid Verdict after 3 attempts.")
