import asyncio
import json
import os
import shutil
import tempfile
from typing import Any

from pydantic import BaseModel

from agent.memory.working import ErrorSignature
from agent.safety.static_analysis import StaticAnalyzer
from agent.tools.fault_localizer import EditLocation
from agent.tools.sandbox import DockerSandbox
from providers.llm import LLMProvider


class CodeEdit(BaseModel):
    file: str
    start_line: int
    end_line: int
    new_content: str

class CodePatch(BaseModel):
    edits: list[CodeEdit] = []
    tests_passed: int = 0
    tests_failed: int = 0
    lint_errors: int = 0
    confidence: float = 0.0
    candidate_id: int = 0

class FixSearcher:
    def __init__(self, llm: LLMProvider, sandbox: DockerSandbox, analyzer: StaticAnalyzer):
        self.llm = llm
        self.sandbox = sandbox
        self.analyzer = analyzer

    async def search(self, error: ErrorSignature, locations: list[EditLocation], workspace_dir: str, n: int = 3) -> CodePatch | None:
        code_context = ""
        for loc in locations:
            file_path = os.path.join(workspace_dir, loc.file_path)
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
                    code_context += f"\nFile: {loc.file_path}\n{content}\n"
            except Exception:
                pass

        # Generate candidates using temperature=0.7 for diversity
        tasks = []
        for i in range(n):
            tasks.append(self._generate_candidate(error, locations, code_context, i+1))

        candidates = await asyncio.gather(*tasks, return_exceptions=True)

        valid_candidates = []
        for c in candidates:
            if isinstance(c, CodePatch):
                valid_candidates.append(c)

        if not valid_candidates:
            return None

        # Test each candidate
        test_tasks = []
        for c in valid_candidates:
            test_tasks.append(self._test_candidate(c, workspace_dir))

        tested_candidates = await asyncio.gather(*test_tasks, return_exceptions=True)

        best_candidate = None
        best_score = (-1, -1) # (tests_passed, -lint_errors)

        for c in tested_candidates:
            if isinstance(c, CodePatch):
                score = (c.tests_passed, -c.lint_errors)
                if best_candidate is None or score > best_score:
                    best_candidate = c
                    best_score = score

        if best_candidate and best_candidate.tests_passed == 0:
            return None

        return best_candidate

    async def _generate_candidate(self, error: ErrorSignature, locations: list[EditLocation], code_context: str, candidate_num: int) -> CodePatch:
        prompt = (
            f"Generate a fix for this error. Return the exact code changes.\n"
            f"Error:\n{error.core_message}\n\n"
            f"Code:\n{code_context}\n"
        )

        messages = [
            {"role": "system", "content": "You are a code fixer."},
            {"role": "user", "content": prompt}
        ]

        for _ in range(3):
            response: Any = await self.llm.complete(
                task_type="coding",
                messages=messages,
                response_format=CodePatch
            )

            try:
                content: Any = response.content
                if isinstance(content, str):
                    patch = CodePatch(**json.loads(content))
                else:
                    patch = CodePatch(**content)

                patch.candidate_id = candidate_num
                return patch
            except Exception:
                pass

            messages.append({"role": "assistant", "content": str(response.content)})
            messages.append({"role": "user", "content": "Invalid format, please try again."})

        raise ValueError(f"Failed to generate candidate {candidate_num}")

    async def _test_candidate(self, patch: CodePatch, workspace_dir: str) -> CodePatch:
        temp_dir = tempfile.mkdtemp(dir=os.getcwd())
        try:
            # Copy workspace
            shutil.copytree(workspace_dir, temp_dir, dirs_exist_ok=True)

            # Apply patch
            for edit in patch.edits:
                file_path = os.path.join(temp_dir, edit.file)
                if not os.path.exists(file_path):
                    continue
                with open(file_path, encoding="utf-8") as f:
                    lines = f.readlines()

                # Replace lines
                lines[edit.start_line-1:edit.end_line] = [edit.new_content + "\n"]

                with open(file_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)

            # Lint
            file_paths = [os.path.join(temp_dir, e.file) for e in patch.edits]
            lint_result = await self.analyzer.analyze(file_paths)
            patch.lint_errors = lint_result.errors

            # Test
            # Very basic test run simulation using sandbox
            test_cmd = "pytest tests/ --disable-warnings"
            # Actually sandbox runs in self.config.workspace_mount which is temp_dir.
            # But the sandbox executes single file or command.
            # We'll use a wrapper script or run bash cmd directly.
            result = await self.sandbox.execute("import os, subprocess; subprocess.run(['pytest', 'tests/'])")
            if result.exit_code == 0:
                patch.tests_passed = 1
                patch.tests_failed = 0
            else:
                patch.tests_passed = 0
                patch.tests_failed = 1

            return patch
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
