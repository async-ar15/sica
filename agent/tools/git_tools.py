import logging
import os
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

try:
    import git  # type: ignore
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False

logger = logging.getLogger(__name__)

class CommitInfo(BaseModel):
    sha: str
    message: str
    files_changed: list[str]
    task_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

class GitManager:
    def __init__(self, project_dir: str):
        self._available = False
        self.repo: Any = None

        if not GIT_AVAILABLE:
            logger.warning("GitPython is not installed. Git integration disabled.")
            return

        try:
            self.repo = git.Repo(project_dir)  # type: ignore
            self._available = True
        except git.InvalidGitRepositoryError:  # type: ignore
            logger.warning(f"Directory {project_dir} is not a valid git repository. Git integration disabled.")
        except Exception as e:
            logger.warning(f"Failed to initialize Git repository at {project_dir}: {e}")

    def stash_user_changes(self) -> bool:
        if not self._available or not self.repo:
            return False

        try:
            if not self.repo.is_dirty(untracked_files=True):
                return False

            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            self.repo.git.stash("push", "-m", f"agent-stash-{timestamp}")
            return True
        except Exception as e:
            logger.warning(f"Failed to stash user changes: {e}")
            return False

    def unstash(self) -> bool:
        if not self._available or not self.repo:
            return False

        try:
            stash_list = self.repo.git.stash("list")
            if not stash_list:
                return False

            self.repo.git.stash("pop")
            return True
        except git.exc.GitCommandError as e:  # type: ignore
            if "conflict" in str(e).lower() or "merge conflict" in str(e).lower():
                logger.warning("Merge conflict on unstash — manual resolution needed")
            else:
                logger.warning(f"GitCommandError on unstash: {e}")
            return False
        except Exception as e:
            logger.warning(f"Failed to unstash changes: {e}")
            return False

    def auto_commit(self, task_id: str, summary: str, files: list[str], metrics: dict[str, Any]) -> CommitInfo | None:
        if not self._available or not self.repo or not files:
            return None

        try:
            # Check if files exist to avoid git add errors
            working_dir: str = str(self.repo.working_tree_dir or "")
            files_to_add: list[str] = []
            for f in files:
                if os.path.exists(os.path.join(working_dir, f)) or self.repo.git.ls_files(f):
                    files_to_add.append(f)

            if not files_to_add:
                return None

            self.repo.git.add(*files_to_add)

            message = (
                f"[agent] task:{task_id} status:success\n\n"
                f"Summary: {summary}\n"
                f"Files changed: {', '.join(files_to_add)}\n"
                f"Iterations: {metrics.get('iterations', 0)}\n"
                f"Tokens used: {metrics.get('tokens', 0):,}\n"
                f"Cost: ${metrics.get('cost', 0.0):.4f}"
            )

            commit = self.repo.index.commit(message)

            return CommitInfo(
                sha=str(commit.hexsha),
                message=message,
                files_changed=files_to_add,
                task_id=task_id
            )
        except Exception as e:
            logger.warning(f"Failed to auto-commit: {e}")
            return None

    def get_diff(self, files: list[str] | None = None) -> str:
        if not self._available or not self.repo:
            return ""

        try:
            working_dir: str = str(self.repo.working_tree_dir or "")
            if files:
                # filter out non-existent files for diff
                existing_files = [f for f in files if os.path.exists(os.path.join(working_dir, f)) or self.repo.git.ls_files(f)]
                if not existing_files:
                    return ""
                return str(self.repo.git.diff("--", *existing_files))
            else:
                return str(self.repo.git.diff())
        except Exception as e:
            logger.warning(f"Failed to get diff: {e}")
            return ""

    def is_dirty(self) -> bool:
        if not self._available or not self.repo:
            return False

        try:
            return bool(self.repo.is_dirty(untracked_files=True))
        except Exception:
            return False
