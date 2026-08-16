import json
import logging

from pydantic import BaseModel, Field

from agent.reflection.engine import Hypothesis
from agent.tools.repo_map import RepoMap
from providers.llm import LLMProvider

logger = logging.getLogger(__name__)


class EditLocation(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class LocalizationResult(BaseModel):
    locations: list[EditLocation] = Field(default_factory=list)
    summary: str = ""


class FaultLocalizer:
    """Uses LLM and RepoMap to pinpoint exactly where an error should be fixed."""

    def __init__(self, llm: LLMProvider, repo_map: RepoMap) -> None:
        self.llm = llm
        self.repo_map = repo_map

    async def localize(
        self, hypothesis: Hypothesis, traceback: str, current_state: str
    ) -> LocalizationResult:
        """Finds the files and lines that need to be edited to implement the hypothesis."""
        repo_map_str = self.repo_map.to_markdown()

        system = (
            "You are an expert fault localizer. Given a codebase map, an error, "
            "and a proposed fix, identify exactly which files and line ranges need "
            "to be modified. Output a valid JSON object matching the LocalizationResult schema."
        )

        prompt = f"""
Codebase Structure:
{repo_map_str}

Error Traceback:
{traceback}

Current State Context:
{current_state}

Proposed Fix (Hypothesis):
{hypothesis.description}
Action Plan: {hypothesis.action_plan}

Identify the files and line ranges that need modification to apply this fix.
If the traceback points to a specific file, prioritize it.
If the file is not in the RepoMap, you may still suggest it if you are confident it exists.
Respond with a JSON object containing 'summary' (string) and 'locations' (array of objects 
with keys: file_path, start_line, end_line, content, confidence, reasoning).
"""
        try:
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ]

            resp = await self.llm.complete(
                task_type="localization",
                messages=messages,
                response_format={"type": "json_object"}  # type: ignore
            )

            content = resp.content.strip()
            data = json.loads(content)

            locations = []
            for loc in data.get("locations", []):
                locations.append(EditLocation(
                    file_path=loc.get("file_path", ""),
                    start_line=loc.get("start_line", 1),
                    end_line=loc.get("end_line", 1),
                    content=loc.get("content", ""),
                    confidence=float(loc.get("confidence", 0.5)),
                    reasoning=loc.get("reasoning", "")
                ))

            return LocalizationResult(
                summary=data.get("summary", "Localization completed."),
                locations=locations
            )

        except Exception as e:
            logger.error(f"Localization failed: {e}")
            return LocalizationResult(summary=f"Failed to localize: {e}")
