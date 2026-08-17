from __future__ import annotations
import os
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent.safety.permissions import PermissionGate

from pydantic import BaseModel

from agent.memory.working import WorkingMemory
from agent.tools.sandbox import DockerSandbox


class AgentMode(StrEnum):
    """Permission modes controlling what tools the agent can use."""
    PLAN = "plan"       # Read-only: view_file, find_in_repo, run_tests, remember
    BUILD = "build"     # Full power: all 7 tools
    REVIEW = "review"   # Read + test: view_file, find_in_repo, run_tests, remember, run_command (read-only)

class ToolResult(BaseModel):
    """Result from any tool execution."""
    success: bool
    output: str = ""
    error: str | None = None
    files_modified: list[str] = []

class ToolDefinition(BaseModel):
    """Schema for a single tool (OpenAI function-calling format)."""
    name: str
    description: str
    parameters: dict[str, Any]
    required_params: list[str] = []
    allowed_modes: list[AgentMode]


class ToolRegistry:
    def __init__(self, sandbox: DockerSandbox, working_memory: WorkingMemory, permission_gate: "PermissionGate | None" = None) -> None:
        self.sandbox = sandbox
        self.working_memory = working_memory

        if permission_gate is None:
            from agent.safety.permissions import PermissionGate
            self.permission_gate = PermissionGate()
        else:
            self.permission_gate = permission_gate

        self.dynamic_tools = {}
        self.mcp_handlers = {}

    def register_mcp_tool(self, schema: dict[str, Any], handler: Any) -> None:
        name = schema["function"]["name"]
        self.dynamic_tools[name] = schema
        self.mcp_handlers[name] = handler

    def _view_file(self, path: str, start_line: int = 1, end_line: int = -1) -> ToolResult:
        try:
            target_path = Path(path).resolve()

            if not target_path.exists():
                return ToolResult(success=False, error="File does not exist.")

            # Check binary (first 8KB for null bytes)
            with open(target_path, "rb") as f:
                chunk = f.read(8192)
                if b"\x00" in chunk:
                    return ToolResult(success=False, error="File is binary.")

            with open(target_path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            if start_line < 1:
                start_line = 1
            if end_line == -1 or end_line > len(lines):
                end_line = len(lines)

            num_lines = end_line - start_line + 1
            if num_lines > 200:
                end_line = start_line + 199

            output_lines = []
            nl = '\n'
            for i in range(start_line - 1, end_line):
                output_lines.append(f"{i+1}: {lines[i].rstrip(nl)}")

            return ToolResult(success=True, output="\n".join(output_lines))
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _find_in_repo(self, query: str, file_pattern: str = "*", max_results: int = 20) -> ToolResult:
        try:
            import fnmatch
            results = []
            project_root = Path(os.getcwd()).resolve()
            excludes = {".git", "node_modules", "__pycache__", ".venv", ".pytest_cache"}

            for root, dirs, files in os.walk(project_root):
                dirs[:] = [d for d in dirs if d not in excludes]
                for file in files:
                    if not fnmatch.fnmatch(file, file_pattern):
                        continue
                    file_path = Path(root) / file
                    try:
                        with open(file_path, encoding="utf-8", errors="ignore") as f:
                            for i, line in enumerate(f):
                                if query in line:
                                    rel_path = file_path.relative_to(project_root)
                                    results.append(f"{rel_path}:{i+1}: {line.strip()}")
                                    if len(results) >= max_results:
                                        break
                    except Exception:
                        pass
                    if len(results) >= max_results:
                        break
                if len(results) >= max_results:
                    break

            if not results:
                return ToolResult(success=True, output="No matches found.")
            return ToolResult(success=True, output="\n".join(results))
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _edit_file(self, path: str, start_line: int, end_line: int, new_content: str) -> ToolResult:
        try:
            target_path = Path(path).resolve()
            if not target_path.exists():
                return ToolResult(success=False, error="File does not exist.")
            if start_line > end_line or start_line < 1:
                return ToolResult(success=False, error="Invalid line range.")

            with open(target_path, encoding="utf-8") as f:
                lines = f.readlines()

            if start_line > len(lines):
                return ToolResult(success=False, error="start_line is beyond file length.")

            prefix = lines[:start_line - 1]
            suffix = lines[end_line:] if end_line <= len(lines) else []

            new_lines = new_content.splitlines(keepends=True)
            nl = '\n'
            if new_content and not new_content.endswith(nl) and (not new_lines or not new_lines[-1].endswith(nl)):
                if new_lines:
                    new_lines[-1] += nl
                else:
                    new_lines = [nl]

            final_lines = prefix + new_lines + suffix

            temp_path = target_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                f.writelines(final_lines)
            temp_path.replace(target_path)

            return ToolResult(success=True, output="File edited successfully.", files_modified=[str(target_path)])
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _create_file(self, path: str, content: str) -> ToolResult:
        try:
            target_path = Path(path).resolve()
            project_root = Path(os.getcwd()).resolve()

            if not target_path.is_relative_to(project_root):
                return ToolResult(success=False, error="Path traversal denied.")

            if target_path.exists():
                return ToolResult(success=False, error="File already exists.")

            target_path.parent.mkdir(parents=True, exist_ok=True)

            temp_path = target_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(content)
            temp_path.replace(target_path)

            return ToolResult(success=True, output="File created successfully.", files_modified=[str(target_path)])
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def _run_command(self, command: str) -> ToolResult:
        try:
            dangerous = ["rm -rf /", "mkfs", "dd if=", "curl | bash", "wget | bash"]
            for d in dangerous:
                if d in command:
                    return ToolResult(success=False, error="Command blocked for safety.")

            code = f"""import subprocess
import sys
res = subprocess.run({repr(command)}, shell=True, capture_output=True, text=True)
sys.stdout.write(res.stdout)
sys.stderr.write(res.stderr)
sys.exit(res.returncode)
"""
            res = await self.sandbox.execute(code=code, entrypoint="run_cmd.py")
            output = ""
            if res.stdout:
                output += res.stdout
            if res.stderr:
                output += "\n" + res.stderr
            return ToolResult(
                success=(res.exit_code == 0),
                output=output.strip(),
                error=None if res.exit_code == 0 else "Command failed"
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def _run_tests(self, test_path: str = "tests/", verbose: bool = False) -> ToolResult:
        try:
            res = await self.sandbox.run_tests(test_path)
            output = res.raw_output
            if res.all_passed:
                return ToolResult(success=True, output=output)
            else:
                return ToolResult(success=False, error="Tests failed.", output=output)
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _remember(self, key: str, value: str) -> ToolResult:
        try:
            self.working_memory.remember(key, value)
            return ToolResult(success=True, output=f"Remembered: {key}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def execute(self, tool_name: str, params: dict[str, Any], mode: AgentMode) -> ToolResult:
        if not self.permission_gate.check(tool_name, mode):
            return ToolResult(success=False, error=f"{tool_name} not allowed in {mode} mode")

        try:
            if tool_name == "view_file":
                return self._view_file(**params)
            elif tool_name == "find_in_repo":
                return self._find_in_repo(**params)
            elif tool_name == "edit_file":
                return self._edit_file(**params)
            elif tool_name == "create_file":
                return self._create_file(**params)
            elif tool_name == "run_command":
                return await self._run_command(**params)
            elif tool_name == "run_tests":
                return await self._run_tests(**params)
            elif tool_name == "remember":
                return self._remember(**params)
            elif tool_name in self.dynamic_tools:
                try:
                    import inspect
                    handler = self.mcp_handlers[tool_name]
                    if inspect.iscoroutinefunction(handler):
                        res = await handler(tool_name, params)
                    else:
                        res = handler(tool_name, params)
                    return ToolResult(success=True, output=str(res))
                except Exception as e:
                    return ToolResult(success=False, error=str(e))
            else:
                return ToolResult(success=False, error=f"Unknown tool: {tool_name}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "view_file",
                    "description": "View a file in the repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "start_line": {"type": "integer"},
                            "end_line": {"type": "integer"}
                        },
                        "required": ["path"]
                    }
                }
            },
            # Add other definitions similarly...
            {
                "type": "function",
                "function": {
                    "name": "find_in_repo",
                    "description": "Search the repository for a query.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "file_pattern": {"type": "string"},
                            "max_results": {"type": "integer"}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "edit_file",
                    "description": "Edit lines in an existing file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "start_line": {"type": "integer"},
                            "end_line": {"type": "integer"},
                            "new_content": {"type": "string"}
                        },
                        "required": ["path", "start_line", "end_line", "new_content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_file",
                    "description": "Create a new file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"}
                        },
                        "required": ["path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Run a shell command in the sandbox.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"}
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_tests",
                    "description": "Run tests in the sandbox.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "test_path": {"type": "string"},
                            "verbose": {"type": "boolean"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "remember",
                    "description": "Store a key-value pair in memory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "value": {"type": "string"}
                        },
                        "required": ["key", "value"]
                    }
                }
            }
        ]
