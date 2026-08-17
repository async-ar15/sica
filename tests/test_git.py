from pathlib import Path

import git  # pyright: ignore[reportMissingImports]
import pytest

from agent.tools.git_tools import GitManager


@pytest.fixture
def repo_dir(tmp_path):
    repo = git.Repo.init(str(tmp_path))
    readme = tmp_path / "README.md"
    readme.write_text("initial")
    repo.index.add([str(readme)])
    repo.index.commit("Initial commit")
    return tmp_path

@pytest.fixture
def git_manager(repo_dir):
    return GitManager(str(repo_dir))

def test_stash_user_changes_when_dirty(git_manager, repo_dir):
    file_path = Path(repo_dir) / "README.md"
    file_path.write_text("modified")

    assert git_manager.is_dirty() is True
    assert git_manager.stash_user_changes() is True
    assert git_manager.is_dirty() is False

def test_stash_returns_false_when_clean(git_manager):
    assert git_manager.is_dirty() is False
    assert git_manager.stash_user_changes() is False

def test_unstash_restores_changes(git_manager, repo_dir):
    file_path = Path(repo_dir) / "README.md"
    file_path.write_text("modified")
    git_manager.stash_user_changes()

    assert file_path.read_text() == "initial"

    assert git_manager.unstash() is True
    assert file_path.read_text() == "modified"

def test_auto_commit_adds_specific_files(git_manager, repo_dir):
    file1 = Path(repo_dir) / "file1.txt"
    file2 = Path(repo_dir) / "file2.txt"
    file1.write_text("file1")
    file2.write_text("file2")

    metrics = {"iterations": 2, "tokens": 1000, "cost": 0.05}
    info = git_manager.auto_commit("task-1", "summary", ["file1.txt"], metrics)

    assert info is not None
    assert "file1.txt" in info.files_changed
    assert "file2.txt" not in info.files_changed

    # check git log
    repo = git.Repo(repo_dir)
    commit = repo.head.commit
    assert "file1.txt" in commit.stats.files
    assert "file2.txt" not in commit.stats.files

def test_auto_commit_never_uses_add_all(git_manager, repo_dir):
    file1 = Path(repo_dir) / "file1.txt"
    file2 = Path(repo_dir) / "file2.txt"
    file1.write_text("1")
    file2.write_text("2")

    info = git_manager.auto_commit("task-2", "summary", ["file1.txt"], {})
    repo = git.Repo(repo_dir)
    assert "file2.txt" in repo.untracked_files

def test_commit_message_format(git_manager, repo_dir):
    file1 = Path(repo_dir) / "f.txt"
    file1.write_text("test")

    metrics = {"iterations": 3, "tokens": 1500, "cost": 0.015}
    info = git_manager.auto_commit("task-123", "did something", ["f.txt"], metrics)

    msg = info.message
    assert "[agent] task:task-123 status:success" in msg
    assert "Summary: did something" in msg
    assert "Files changed: f.txt" in msg
    assert "Iterations: 3" in msg
    assert "Tokens used: 1,500" in msg
    assert "Cost: $0.0150" in msg

def test_get_diff_shows_changes(git_manager, repo_dir):
    file1 = Path(repo_dir) / "README.md"
    file1.write_text("new content")

    diff = git_manager.get_diff(["README.md"])
    assert "new content" in diff
    assert "initial" in diff

    # diff without files should also work
    diff_all = git_manager.get_diff()
    assert "new content" in diff_all

def test_not_a_git_repo_no_crash(tmp_path):
    gm = GitManager(str(tmp_path))
    assert gm._available is False
    assert gm.stash_user_changes() is False
    assert gm.unstash() is False
    assert gm.auto_commit("t", "s", [], {}) is None
    assert gm.get_diff() == ""
    assert gm.is_dirty() is False

def test_is_dirty_detects_changes(git_manager, repo_dir):
    assert git_manager.is_dirty() is False
    untracked = Path(repo_dir) / "untracked.txt"
    untracked.write_text("hi")
    assert git_manager.is_dirty() is True
