import json

from pydantic import BaseModel

from agent.tools.sandbox import DockerSandbox


class LintError(BaseModel):
    """A single lint/type/security issue."""
    file: str
    line: int
    column: int = 0
    code: str
    message: str
    severity: str = "error"
    tool: str = "ruff"

class AnalysisResult(BaseModel):
    """Aggregated static analysis result."""
    errors: int = 0
    warnings: int = 0
    security_issues: int = 0
    details: list[LintError] = []
    auto_fixable: int = 0

class StaticAnalyzer:
    def __init__(self, sandbox: DockerSandbox) -> None:
        self.sandbox = sandbox

    async def analyze(self, files: list[str]) -> AnalysisResult:
        if not files:
            return AnalysisResult()

        py_files = [f for f in files if f.endswith('.py')]
        if not py_files:
            return AnalysisResult()

        files_str = " ".join(py_files)

        # 1. Ruff
        code_ruff = f"""import subprocess
import sys
res = subprocess.run(['ruff', 'check', '--output-format=json'] + {repr(py_files)}, capture_output=True, text=True)
sys.stdout.write(res.stdout)
sys.stderr.write(res.stderr)
sys.exit(res.returncode)
"""
        res_ruff = await self.sandbox.execute(code=code_ruff, entrypoint="run_ruff.py")
        ruff_errors, ruff_fixable = self._parse_ruff_json(res_ruff.stdout or "")

        # 2. Mypy
        code_mypy = f"""import subprocess
import sys
res = subprocess.run(['mypy'] + {repr(py_files)}, capture_output=True, text=True)
sys.stdout.write(res.stdout)
sys.stderr.write(res.stderr)
sys.exit(res.returncode)
"""
        res_mypy = await self.sandbox.execute(code=code_mypy, entrypoint="run_mypy.py")
        mypy_errors = self._parse_mypy_output(res_mypy.stdout or "")

        # 3. Bandit
        code_bandit = f"""import subprocess
import sys
res = subprocess.run(['bandit', '-f', 'json'] + {repr(py_files)}, capture_output=True, text=True)
sys.stdout.write(res.stdout)
sys.stderr.write(res.stderr)
sys.exit(res.returncode)
"""
        res_bandit = await self.sandbox.execute(code=code_bandit, entrypoint="run_bandit.py")
        bandit_errors = self._parse_bandit_json(res_bandit.stdout or "")

        all_details = ruff_errors + mypy_errors + bandit_errors

        return AnalysisResult(
            errors=len(ruff_errors) + len(mypy_errors),
            warnings=0,  # Could parse severity from mypy/ruff if needed
            security_issues=len(bandit_errors),
            details=all_details,
            auto_fixable=ruff_fixable
        )

    async def auto_fix_lint(self, files: list[str]) -> list[str]:
        py_files = [f for f in files if f.endswith('.py')]
        if not py_files:
            return []

        code_ruff = f"""import subprocess
import sys
res = subprocess.run(['ruff', 'check', '--fix'] + {repr(py_files)}, capture_output=True, text=True)
sys.stdout.write(res.stdout)
sys.stderr.write(res.stderr)
sys.exit(res.returncode)
"""
        # Ruff check --fix usually exits with 0 if it fixed everything, or non-zero if some things remain.
        # It's hard to track *exactly* which files were modified inside the sandbox just from the output,
        # but we can return all requested files as potentially modified.
        await self.sandbox.execute(code=code_ruff, entrypoint="run_ruff_fix.py")
        return py_files

    def _parse_ruff_json(self, output: str) -> tuple[list[LintError], int]:
        try:
            if not output.strip():
                return [], 0

            # Ruff might output other things before/after json, try to find the list
            try:
                data = json.loads(output)
            except json.JSONDecodeError:
                # Find first [ and last ]
                start = output.find('[')
                end = output.rfind(']')
                if start != -1 and end != -1:
                    data = json.loads(output[start:end+1])
                else:
                    return [], 0

            errors = []
            fixable = 0
            for item in data:
                errors.append(LintError(
                    file=item.get("filename", ""),
                    line=item.get("location", {}).get("row", 0),
                    column=item.get("location", {}).get("column", 0),
                    code=item.get("code", "E"),
                    message=item.get("message", ""),
                    tool="ruff"
                ))
                if item.get("fix"):
                    fixable += 1
            return errors, fixable
        except Exception:
            return [], 0

    def _parse_mypy_output(self, output: str) -> list[LintError]:
        errors = []
        for line in output.splitlines():
            line = line.strip()
            if not line or "Success" in line:
                continue

            parts = line.split(":", 3)
            if len(parts) >= 3:
                filename = parts[0].strip()
                try:
                    lineno = int(parts[1].strip())
                    rest = ":".join(parts[2:]).strip()
                    severity = "error"
                    message = rest
                    if rest.startswith("error:"):
                        message = rest[6:].strip()
                    elif rest.startswith("note:"):
                        severity = "info"
                        message = rest[5:].strip()

                    code = "mypy"
                    if "[" in message and message.endswith("]"):
                        code = message[message.rfind("[")+1:-1]
                        message = message[:message.rfind("[")].strip()

                    if severity == "error":
                        errors.append(LintError(
                            file=filename,
                            line=lineno,
                            code=code,
                            message=message,
                            severity=severity,
                            tool="mypy"
                        ))
                except ValueError:
                    pass
        return errors

    def _parse_bandit_json(self, output: str) -> list[LintError]:
        try:
            if not output.strip():
                return []

            try:
                data = json.loads(output)
            except json.JSONDecodeError:
                start = output.find('{')
                end = output.rfind('}')
                if start != -1 and end != -1:
                    data = json.loads(output[start:end+1])
                else:
                    return []

            results = data.get("results", [])
            errors = []
            for item in results:
                errors.append(LintError(
                    file=item.get("filename", ""),
                    line=item.get("line_number", 0),
                    code=item.get("test_id", "B"),
                    message=item.get("issue_text", ""),
                    severity=item.get("issue_severity", "HIGH").lower(),
                    tool="bandit"
                ))
            return errors
        except Exception:
            return []
