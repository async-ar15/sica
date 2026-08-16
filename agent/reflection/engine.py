import json
import logging
import re
from enum import StrEnum

from pydantic import BaseModel, Field

from agent.memory.failure import FailureMemory
from providers.llm import LLMProvider

logger = logging.getLogger(__name__)

class ErrorCategory(StrEnum):
    SYNTAX = "syntax"
    TYPE = "type"
    LOGIC = "logic"
    ENVIRONMENT = "environment"
    NETWORK = "network"
    UNKNOWN = "unknown"

class ErrorSignature(BaseModel):
    file_path: str = ""
    line_number: int | None = None
    error_type: str = "Unknown"
    message: str = ""
    full_traceback: str = ""

    def __str__(self) -> str:
        return f"{self.error_type}: {self.message} at {self.file_path}:{self.line_number or '?'}"

class Hypothesis(BaseModel):
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    action_plan: str
    category: ErrorCategory = ErrorCategory.UNKNOWN

class ReflectionEngine:
    """Implements a 6-step reasoning pipeline to recover from errors."""

    def __init__(self, llm: LLMProvider, failure_memory: FailureMemory | None = None) -> None:
        self.llm = llm
        self.failure_memory = failure_memory

    async def reflect(
        self, traceback: str, current_state: str, tried_hypotheses: list[str]
    ) -> Hypothesis:
        """Runs the full reflection pipeline."""
        # Step 1: EXTRACT
        signature = self.extract_signature(traceback)

        # Step 2: SEARCH
        similar_fixes = self.search_failures(signature)

        # Step 3: CLASSIFY
        category = await self.classify_error(signature)

        # Step 4: HYPOTHESIZE
        hypotheses = await self.generate_hypotheses(
            signature, current_state, category, similar_fixes, tried_hypotheses
        )

        # Step 5: SELECT
        chosen = self.select_best_hypothesis(hypotheses)

        # Step 6: PLAN
        # The Hypothesis object already contains the action plan from the LLM,
        # but we ensure it's fully populated.
        chosen.category = category
        return chosen

    def extract_signature(self, traceback: str) -> ErrorSignature:
        """Parses a traceback to extract structural information."""
        # Fallback extraction logic, can be enhanced with tree-sitter or better regex
        sig = ErrorSignature(full_traceback=traceback)

        lines = traceback.strip().splitlines()
        if not lines:
            return sig

        # The last line usually contains ErrorType: Message
        last_line = lines[-1]
        type_match = re.match(r"^([A-Za-z0-9_]+Error|Exception):\s*(.*)", last_line)
        if type_match:
            sig.error_type = type_match.group(1)
            sig.message = type_match.group(2)
        else:
            sig.message = last_line

        # Try to find the file and line number from the last File line
        # e.g., File "/path/to/file.py", line 42, in <module>
        file_matches = list(re.finditer(r'File "([^"]+)", line (\d+)', traceback))
        if file_matches:
            last_file_match = file_matches[-1]
            sig.file_path = last_file_match.group(1)
            sig.line_number = int(last_file_match.group(2))

        return sig

    def search_failures(self, signature: ErrorSignature) -> list[dict[str, str]]:
        """Queries FailureMemory for similar past failures and their successful resolutions."""
        if not self.failure_memory:
            return []

        records = self.failure_memory.search_similar_errors(str(signature), limit=3)
        return [
            {"hypothesis": r.hypothesis, "result": r.result}
            for r in records
            if r.result.lower() == "success"
        ]

    async def classify_error(self, signature: ErrorSignature) -> ErrorCategory:
        """Uses LLM to classify the error."""
        prompt = (
            f"Classify this error into one of: {[c.value for c in ErrorCategory]}.\n"
            f"Type: {signature.error_type}\n"
            f"Message: {signature.message}\n"
            "Return ONLY the category word."
        )
        try:
            messages = [
                {"role": "system", "content": "You are an error classifier."},
                {"role": "user", "content": prompt}
            ]
            resp = await self.llm.complete("reflection", messages=messages)
            cat_str = resp.content.strip().lower()
            for c in ErrorCategory:
                if c.value in cat_str:
                    return c
        except Exception as e:
            logger.warning(f"Error classification failed: {e}")

        return ErrorCategory.UNKNOWN

    async def generate_hypotheses(
        self,
        signature: ErrorSignature,
        current_state: str,
        category: ErrorCategory,
        similar_fixes: list[dict[str, str]],
        tried_hypotheses: list[str]
    ) -> list[Hypothesis]:
        """Generates multiple potential fixes, explicitly excluding already tried approaches."""

        system = (
            "You are an expert software debugger. Output valid JSON array of objects "
            "with keys: description, confidence (0.0-1.0), action_plan."
        )

        tried_str = "\n".join(f"- {h}" for h in tried_hypotheses) if tried_hypotheses else "None"
        fixes_str = (
            "\n".join(f"- Try: {f['hypothesis']}" for f in similar_fixes)
            if similar_fixes else "None"
        )

        prompt = f"""
Analyze this error and propose 3 distinct hypotheses to fix it.

Context: {current_state}
Category: {category.value}
Error: {signature}
Traceback: {signature.full_traceback}

Past successful fixes for similar errors:
{fixes_str}

CRITICAL: DO NOT suggest any of the following hypotheses as they have already failed:
{tried_str}

Respond with a JSON array containing 3 distinct hypotheses.
"""
        try:
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ]
            resp = await self.llm.complete(
                "reflection", messages=messages, response_format={"type": "json_object"}  # type: ignore
            )
            content = resp.content.strip()

            # The LLM might return {"hypotheses": [...]} or just [...]
            data = json.loads(content)
            items = data.get("hypotheses", data) if isinstance(data, dict) else data

            hypotheses = []
            for item in items:
                hypotheses.append(Hypothesis(
                    description=item.get("description", "Unknown fix"),
                    confidence=float(item.get("confidence", 0.5)),
                    action_plan=item.get("action_plan", "No plan provided")
                ))

            if hypotheses:
                return hypotheses
        except Exception as e:
            logger.error(f"Failed to generate hypotheses: {e}")

        # Fallback generic hypothesis
        return [Hypothesis(
            description="Investigate the error interactively.",
            confidence=0.5,
            action_plan="Read the file and search for the error source.",
            category=category
        )]

    def select_best_hypothesis(self, hypotheses: list[Hypothesis]) -> Hypothesis:
        """Selects the hypothesis with the highest confidence."""
        if not hypotheses:
            return Hypothesis(description="Fallback", confidence=0.0, action_plan="Fallback")

        return max(hypotheses, key=lambda h: h.confidence)
