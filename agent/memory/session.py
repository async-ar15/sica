import logging
import os
import platform
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class CheckpointData(BaseModel):
    """State snapshot for resume-on-crash."""
    version: str = "2.0"
    current_goal: str
    current_state: str
    iteration_count: int
    last_error: str | None = None
    files_modified: list[str] = Field(default_factory=list)
    current_hypothesis: str = ""
    tried_hypotheses: list[str] = Field(default_factory=list)
    task_id: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MemoryCategory(StrEnum):
    """Categories for MEMORY.md entries."""
    ARCHITECTURE = "architecture"
    PATTERN = "pattern"
    ERROR = "error"
    CONVENTION = "convention"
    FACT = "fact"

@contextmanager
def file_lock(path: Path) -> Generator[None, None, None]:
    """Cross-platform file locking."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with open(lock_path, "a+") as f:
        try:
            if platform.system() == "Windows":
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl  # pyright: ignore[reportMissingImports]
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # type: ignore
            yield
        finally:
            try:
                if platform.system() == "Windows":
                    import msvcrt
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl  # pyright: ignore[reportMissingImports]
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # type: ignore
            except OSError:
                pass


class SessionMemory:
    """Manages the agent's long-term human-readable memory."""

    HEADER_TEMPLATE = (
        "# Agent Memory\n\n"
        "## Architecture\n\n"
        "## Patterns\n\n"
        "## Errors\n\n"
        "## Conventions\n\n"
        "## Facts\n"
    )

    def __init__(self, memory_dir: str = "memory/") -> None:
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.task_logs_dir = self.memory_dir / "task_logs"
        self.task_logs_dir.mkdir(parents=True, exist_ok=True)

        self.memory_file = self.memory_dir / "MEMORY.md"
        self.checkpoint_file = self.memory_dir / "checkpoint.md"
        self.notes_file = self.memory_dir / "notes.md"

    # --- MEMORY.md Operations ---

    def read_memory(self) -> str:
        """Reads MEMORY.md, creating it with the template if it doesn't exist."""
        if not self.memory_file.exists():
            with file_lock(self.memory_file):
                if not self.memory_file.exists():
                    self._atomic_write(self.memory_file, self.HEADER_TEMPLATE)
                    return self.HEADER_TEMPLATE

        return self.memory_file.read_text(encoding="utf-8")

    def append_fact(self, fact: str, category: MemoryCategory, source_task: str) -> None:
        """Appends a fact under the correct section header in MEMORY.md."""
        content = self.read_memory()

        timestamp = datetime.now(timezone.utc).isoformat()
        fact_line = f"- [{category.value}] {fact} (from task: {source_task}, {timestamp})"

        header = f"## {category.value.capitalize()}"

        lines = content.splitlines()
        new_lines = []
        inserted = False

        for line in lines:
            new_lines.append(line)
            if not inserted and line.strip() == header:
                new_lines.append(fact_line)
                inserted = True

        if not inserted:
            new_lines.append(f"\n{header}")
            new_lines.append(fact_line)

        new_content = "\n".join(new_lines) + "\n"

        with file_lock(self.memory_file):
            self._atomic_write(self.memory_file, new_content)

        self.get_memory_size()

    def search_memory(self, query: str) -> list[str]:
        """Simple case-insensitive substring search across MEMORY.md lines."""
        content = self.read_memory()
        query_lower = query.lower()
        results = []
        for line in content.splitlines():
            if query_lower in line.lower() and line.startswith("- ["):
                results.append(line)
        return results

    def get_memory_size(self) -> int:
        """Returns MEMORY.md file size in bytes, warns if > 50KB."""
        if not self.memory_file.exists():
            return 0
        size = self.memory_file.stat().st_size
        if size > 50 * 1024:
            logger.warning("MEMORY.md has exceeded 50KB. Consider running /dream for compression.")
        return size

    # --- checkpoint.md Operations ---

    def save_checkpoint(self, data: CheckpointData) -> None:
        """Saves CheckpointData as structured Markdown."""
        content = (
            "# Checkpoint\n"
            f"## Version: {data.version}\n"
            f"## Goal: {data.current_goal}\n"
            f"## State: {data.current_state}\n"
            f"## Iteration: {data.iteration_count}\n"
            f"## Last Error: {data.last_error or ''}\n"
            f"## Files Modified: {','.join(data.files_modified)}\n"
            f"## Hypothesis: {data.current_hypothesis}\n"
            f"## Tried: {','.join(data.tried_hypotheses)}\n"
            f"## Task ID: {data.task_id}\n"
            f"## Timestamp: {data.timestamp.isoformat()}\n"
        )
        self._atomic_write(self.checkpoint_file, content)

    def load_checkpoint(self) -> CheckpointData | None:
        """Loads and parses checkpoint.md into CheckpointData."""
        if not self.checkpoint_file.exists():
            return None

        content = self.checkpoint_file.read_text(encoding="utf-8")

        try:
            data_dict: dict[str, Any] = {}
            lines = content.splitlines()
            for line in lines:
                if line.startswith("## Version: "):
                    data_dict["version"] = line[12:].strip()
                elif line.startswith("## Goal: "):
                    data_dict["current_goal"] = line[9:].strip()
                elif line.startswith("## State: "):
                    data_dict["current_state"] = line[10:].strip()
                elif line.startswith("## Iteration: "):
                    data_dict["iteration_count"] = int(line[14:].strip())
                elif line.startswith("## Last Error: "):
                    data_dict["last_error"] = line[15:].strip() or None
                elif line.startswith("## Files Modified: "):
                    files = line[19:].strip()
                    data_dict["files_modified"] = files.split(",") if files else []
                elif line.startswith("## Hypothesis: "):
                    data_dict["current_hypothesis"] = line[15:].strip()
                elif line.startswith("## Tried: "):
                    tried = line[10:].strip()
                    data_dict["tried_hypotheses"] = tried.split(",") if tried else []
                elif line.startswith("## Task ID: "):
                    data_dict["task_id"] = line[12:].strip()
                elif line.startswith("## Timestamp: "):
                    data_dict["timestamp"] = datetime.fromisoformat(line[14:].strip())

            if (
                not data_dict.get("version")
                or not data_dict.get("current_goal")
                or not data_dict.get("current_state")
            ):
                raise ValueError("Missing essential checkpoint fields")

            if data_dict.get("version") != "2.0":
                logger.warning(
                    f"Checkpoint version mismatch: found {data_dict.get('version')}, expected 2.0."
                )
                return None

            return CheckpointData(**data_dict)

        except Exception as e:
            logger.warning(f"Failed to parse checkpoint (corrupt): {e}")
            corrupt_file = self.memory_dir / ".checkpoint.md.corrupt"
            import contextlib
            with contextlib.suppress(OSError):
                self.checkpoint_file.rename(corrupt_file)
            return None

    def clear_checkpoint(self) -> None:
        """Deletes checkpoint.md if it exists."""
        try:
            if self.checkpoint_file.exists():
                self.checkpoint_file.unlink()
        except OSError:
            pass

    # --- task_logs Operations ---

    def create_task_log(self, task_id: str, goal: str) -> None:
        """Creates a new task log file."""
        log_file = self.task_logs_dir / f"{task_id}.md"
        timestamp = datetime.now(timezone.utc).isoformat()
        content = f"# Task: {task_id}\n## Goal: {goal}\n## Started: {timestamp}\n"
        self._atomic_write(log_file, content)

    def append_to_task_log(self, task_id: str, iteration: int, content: str) -> None:
        """Appends an iteration log to a task log."""
        log_file = self.task_logs_dir / f"{task_id}.md"
        append_content = f"\n### Iteration {iteration}\n{content}\n"

        with file_lock(log_file):
            if log_file.exists():
                current_content = log_file.read_text(encoding="utf-8")
                self._atomic_write(log_file, current_content + append_content)
            else:
                self._atomic_write(log_file, append_content)

    def get_task_log(self, task_id: str) -> str:
        """Reads and returns the full task log."""
        log_file = self.task_logs_dir / f"{task_id}.md"
        if log_file.exists():
            return log_file.read_text(encoding="utf-8")
        return ""

    def list_task_logs(self) -> list[str]:
        """Lists all task IDs from the logs directory."""
        return [f.stem for f in self.task_logs_dir.glob("*.md")]

    # --- notes.md Operations ---

    def write_note(self, content: str) -> None:
        """Overwrites the notes scratchpad."""
        self._atomic_write(self.notes_file, content)

    def read_notes(self) -> str:
        """Reads the notes scratchpad."""
        if self.notes_file.exists():
            return self.notes_file.read_text(encoding="utf-8")
        return ""

    # --- Helpers ---

    def _atomic_write(self, path: Path, content: str) -> None:
        """Writes content to a temporary file and atomically renames it."""
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        try:
            os.replace(tmp_path, path)
        except Exception:
            tmp_path.rename(path)
