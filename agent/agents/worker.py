from typing import Any

from pydantic import BaseModel, Field

from agent.agents.architect import SubTask
from agent.agents.judge import Verdict
from agent.safety.static_analysis import LintError
from agent.tools.aci import ToolRegistry
from providers.llm import LLMProvider


class CodeResult(BaseModel):
    """Result from Worker executing a subtask."""
    files_modified: list[str] = Field(default_factory=list)
    files_created: list[str] = Field(default_factory=list)
    tool_calls_made: list[dict[str, Any]] = Field(default_factory=list)
    tokens_used: int = 0
    cost_usd: float = 0.0
    success: bool = True
    error: str | None = None

class WorkerAgent:
    def __init__(self, llm: LLMProvider, tools: ToolRegistry):
        self.llm = llm
        self.tools = tools

    async def execute(self, subtask: SubTask, context: str) -> CodeResult:
        prompt = (
            "You are an expert coder. Use the provided tools to implement the subtask.\n\n"
            f"Subtask: {subtask.description}\n\n"
            f"Context:\n{context}\n\n"
            "Please call the appropriate tools to complete this task."
        )

        messages = [
            {"role": "system", "content": "You are an expert coder. Use tools to implement the subtask."},
            {"role": "user", "content": prompt}
        ]

        # Using coding model
        response = await self.llm.complete(
            task_type="coding",
            messages=messages
        )

        # Mocking tool extraction logic, as actual implementation would parse function calls from LLMResponse
        # litellm requires tools in acompletion, but we mock the tool_calls for now.
        tool_calls: list[dict[str, Any]] = []
        files_modified: list[str] = []
        files_created: list[str] = []

        for call in tool_calls:
            # We would execute tools here
            # result = await self.tools.execute(call["name"], call["args"], AgentMode.BUILD)
            pass

        return CodeResult(
            files_modified=files_modified,
            files_created=files_created,
            tool_calls_made=tool_calls,
            success=True
        )

    async def fix_lint(self, lint_errors: list[LintError]) -> CodeResult:
        prompt = "Fix the following lint errors:\n" + "\n".join(str(e) for e in lint_errors)
        messages = [
            {"role": "system", "content": "You are an expert coder."},
            {"role": "user", "content": prompt}
        ]
        response = await self.llm.complete(task_type="lint_fix", messages=messages)

        return CodeResult(success=True)

    async def revise(self, code_result: CodeResult, verdict: Verdict) -> CodeResult:
        prompt = (
            "Please revise the code based on the judge's feedback:\n"
            f"Issues: {verdict.issues}\n"
            f"Suggestions: {verdict.suggestions}\n"
        )
        messages = [
            {"role": "system", "content": "You are an expert coder."},
            {"role": "user", "content": prompt}
        ]
        response = await self.llm.complete(task_type="coding", messages=messages)

        return CodeResult(success=True)
