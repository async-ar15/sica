import asyncio
import contextlib
import os
import shutil
import tempfile
import time
from typing import Any

import requests
import yaml
from pydantic import BaseModel

import docker


class SandboxConfig(BaseModel):
    image: str = "python:3.11-slim"
    memory_limit: str = "512m"
    cpu_quota: int = 50000
    timeout_seconds: int = 120
    network_mode: str = "none"
    read_only_root: bool = True
    workspace_mount: str = "/workspace"

class ExecutionResult(BaseModel):
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    duration_ms: int = 0
    files_created: list[str] = []
    timeout: bool = False
    oom_killed: bool = False

class TestResult(BaseModel):
    passed: int = 0
    failed: int = 0
    errors: int = 0
    details: list[dict[str, Any]] = []
    all_passed: bool = False
    raw_output: str = ""

class LintResult(BaseModel):
    errors: int = 0
    warnings: int = 0
    details: list[dict[str, Any]] = []

class DockerUnavailableError(Exception):
    pass

class DockerSandbox:
    def __init__(self, config: SandboxConfig | None = None) -> None:
        if config is None:
            with open("config/default.yaml") as f:
                raw_config = yaml.safe_load(f)
                sandbox_dict = raw_config.get("sandbox", {})
                self.config = SandboxConfig(**sandbox_dict)
        else:
            self.config = config

        self._fallback_mode = False
        docker_enabled = os.getenv("DOCKER_ENABLED", "true").lower() == "true"

        if not docker_enabled:
            print("WARNING: DOCKER_ENABLED is false. Sandbox running in fallback mode.")
            self._fallback_mode = True
        else:
            try:
                self.client = docker.from_env()  # type: ignore[attr-defined]
                self.client.ping()
            except Exception as e:
                raise DockerUnavailableError(
                    "Docker daemon is not running or not accessible."
                ) from e

    def cleanup_orphans(self) -> None:
        if self._fallback_mode:
            return
        containers = self.client.containers.list(all=True, filters={"label": "agent.sandbox=true"})
        for c in containers:
            with contextlib.suppress(Exception):
                c.remove(force=True)

    def _execute_sync(
        self, code: str, entrypoint: str = "main.py", requirements: list[str] | None = None
    ) -> ExecutionResult:
        if self._fallback_mode:
            return ExecutionResult(stderr="Docker is disabled (fallback mode).", exit_code=1)

        start_time = time.time()
        temp_dir = tempfile.mkdtemp(dir=os.getcwd())
        container = None

        try:
            with open(os.path.join(temp_dir, entrypoint), "w", encoding="utf-8") as f:
                f.write(code)

            cmd_str = f"python {self.config.workspace_mount}/{entrypoint}"
            if requirements:
                with open(os.path.join(temp_dir, "requirements.txt"), "w", encoding="utf-8") as f:
                    f.write("\n".join(requirements))
                cmd_str = (
                    f"pip install -r {self.config.workspace_mount}/requirements.txt "
                    f"2>/dev/null; {cmd_str}"
                )

            cmd = ["bash", "-c", cmd_str]

            container = self.client.containers.run(
                image=self.config.image,
                command=cmd,
                labels={"agent.sandbox": "true"},
                mem_limit=self.config.memory_limit,
                cpu_quota=self.config.cpu_quota,
                network_mode=self.config.network_mode,
                read_only=self.config.read_only_root,
                tmpfs={"/tmp": ""},
                volumes={
                    os.path.abspath(temp_dir): {
                        "bind": self.config.workspace_mount,
                        "mode": "rw",
                    }
                },
                working_dir=self.config.workspace_mount,
                detach=True,
            )

            try:
                result = container.wait(timeout=self.config.timeout_seconds)
                exit_code = result["StatusCode"]
                logs = container.logs(stdout=True, stderr=True)
                # Without demux, logs is just a single bytes object with everything.
                stdout = logs.decode("utf-8", errors="replace") if logs else ""
                stderr = ""

                container.reload()
                oom_killed = container.attrs.get("State", {}).get("OOMKilled", False)

                ignore_files = {entrypoint, "requirements.txt"}
                files_created = [f for f in os.listdir(temp_dir) if f not in ignore_files]

                return ExecutionResult(
                    stdout=stdout,
                    stderr=stderr,
                    exit_code=exit_code,
                    duration_ms=int((time.time() - start_time) * 1000),
                    files_created=files_created,
                    timeout=False,
                    oom_killed=oom_killed
                )
            except requests.exceptions.ReadTimeout:
                return ExecutionResult(
                    stderr="Execution timed out.",
                    timeout=True,
                    duration_ms=int((time.time() - start_time) * 1000),
                )
        finally:
            if container:
                with contextlib.suppress(Exception):
                    container.remove(force=True)
            with contextlib.suppress(Exception):
                shutil.rmtree(temp_dir, ignore_errors=True)

    async def execute(
        self, code: str, entrypoint: str = "main.py", requirements: list[str] | None = None
    ) -> ExecutionResult:
        return await asyncio.to_thread(self._execute_sync, code, entrypoint, requirements)

    def _run_tests_sync(self, test_dir: str = "tests/") -> TestResult:
        if self._fallback_mode:
            return TestResult()

        cmd = ["pytest", test_dir, "--tb=short", "-q"]
        container = None
        try:
            container = self.client.containers.run(
                image=self.config.image,
                command=cmd,
                labels={"agent.sandbox": "true"},
                mem_limit=self.config.memory_limit,
                cpu_quota=self.config.cpu_quota,
                network_mode=self.config.network_mode,
                read_only=self.config.read_only_root,
                tmpfs={"/tmp": ""},
                volumes={
                    os.path.abspath(os.getcwd()): {
                        "bind": self.config.workspace_mount,
                        "mode": "rw",
                    }
                },
                working_dir=self.config.workspace_mount,
                detach=True,
            )
            result = container.wait(timeout=self.config.timeout_seconds)
            logs = container.logs(stdout=True, stderr=True)
            raw_output = logs.decode("utf-8", errors="replace") if logs else ""
            exit_code = result["StatusCode"]

            return TestResult(
                all_passed=(exit_code == 0),
                raw_output=raw_output
            )
        except Exception as e:
            return TestResult(raw_output=f"Error running tests: {e}")
        finally:
            if container:
                with contextlib.suppress(Exception):
                    container.remove(force=True)

    async def run_tests(self, test_dir: str = "tests/") -> TestResult:
        return await asyncio.to_thread(self._run_tests_sync, test_dir)

    def _run_lint_sync(self, files: list[str]) -> LintResult:
        if self._fallback_mode:
            return LintResult()

        files_str = " ".join(files) if files else "."
        cmd = ["bash", "-c", f"ruff check {files_str} && mypy {files_str} --strict"]
        container = None
        try:
            container = self.client.containers.run(
                image=self.config.image,
                command=cmd,
                labels={"agent.sandbox": "true"},
                mem_limit=self.config.memory_limit,
                cpu_quota=self.config.cpu_quota,
                network_mode=self.config.network_mode,
                read_only=self.config.read_only_root,
                tmpfs={"/tmp": ""},
                volumes={
                    os.path.abspath(os.getcwd()): {
                        "bind": self.config.workspace_mount,
                        "mode": "rw",
                    }
                },
                working_dir=self.config.workspace_mount,
                detach=True,
            )
            result = container.wait(timeout=self.config.timeout_seconds)
            exit_code = result["StatusCode"]
            return LintResult(errors=1 if exit_code != 0 else 0)
        except Exception:
            return LintResult(errors=1)
        finally:
            if container:
                with contextlib.suppress(Exception):
                    container.remove(force=True)

    async def run_lint(self, files: list[str]) -> LintResult:
        return await asyncio.to_thread(self._run_lint_sync, files)
