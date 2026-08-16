import pytest

from agent.memory.working import WorkingMemory
from agent.tools.aci import AgentMode, ToolRegistry
from agent.tools.sandbox import DockerSandbox


@pytest.fixture
def sandbox(monkeypatch):
    monkeypatch.setenv("DOCKER_ENABLED", "false")
    return DockerSandbox()

@pytest.fixture
def memory():
    return WorkingMemory()

@pytest.fixture
def registry(sandbox, memory):
    return ToolRegistry(sandbox=sandbox, working_memory=memory)

def test_view_file_returns_numbered_lines(registry, tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\nline3")

    res = registry._view_file(str(test_file))
    assert res.success
    assert "1: line1" in res.output
    assert "3: line3" in res.output

def test_view_file_respects_line_limits(registry, tmp_path):
    test_file = tmp_path / "large.txt"
    test_file.write_text("\n".join(f"line {i}" for i in range(1, 301)))

    res = registry._view_file(str(test_file))
    assert res.success
    lines = res.output.split("\n")
    assert len(lines) == 200
    assert "1: line 1" in lines[0]

def test_view_file_binary_detection(registry, tmp_path):
    test_file = tmp_path / "bin.dat"
    test_file.write_bytes(b"\x00\x01\x02\x03\x04")

    res = registry._view_file(str(test_file))
    assert not res.success
    assert "binary" in res.error.lower()

def test_find_in_repo_returns_matches(registry, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    (tmp_path / "file1.txt").write_text("hello world")
    (tmp_path / "file2.txt").write_text("world peace")

    res = registry._find_in_repo("world")
    assert res.success
    assert "file1.txt" in res.output
    assert "file2.txt" in res.output

def test_find_in_repo_caps_results(registry, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    for i in range(5):
        (tmp_path / f"f{i}.txt").write_text("hello\n" * 10)

    res = registry._find_in_repo("hello", max_results=10)
    assert res.success
    assert len(res.output.split("\n")) == 10

def test_edit_file_replaces_lines(registry, tmp_path):
    test_file = tmp_path / "edit.txt"
    test_file.write_text("L1\nL2\nL3\nL4")

    res = registry._edit_file(str(test_file), 2, 3, "NewL2\nNewL3")
    assert res.success
    content = test_file.read_text()
    assert content == "L1\nNewL2\nNewL3\nL4"

def test_edit_file_nonexistent_fails(registry, tmp_path):
    res = registry._edit_file(str(tmp_path / "missing.txt"), 1, 1, "test")
    assert not res.success
    assert "does not exist" in res.error.lower()

def test_create_file_works(registry, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    test_file = tmp_path / "new_dir" / "new_file.txt"
    res = registry._create_file(str(test_file), "hello")
    assert res.success
    assert test_file.read_text() == "hello"

def test_create_file_existing_fails(registry, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    test_file = tmp_path / "existing.txt"
    test_file.write_text("hello")
    res = registry._create_file(str(test_file), "world")
    assert not res.success
    assert "already exists" in res.error.lower()

def test_create_file_path_traversal_blocked(registry, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Outside project root
    target = tmp_path.parent / "out.txt"
    res = registry._create_file(str(target), "hack")
    assert not res.success
    assert "traversal" in res.error.lower()

@pytest.mark.asyncio
async def test_permission_plan_mode_blocks_edit(registry):
    res = await registry.execute("edit_file", {"path": "f", "start_line": 1, "end_line": 1, "new_content": "n"}, AgentMode.PLAN)
    assert not res.success
    assert "not allowed" in res.error.lower()

@pytest.mark.asyncio
async def test_permission_build_mode_allows_all(registry, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # view_file
    f = tmp_path / "a.txt"
    f.write_text("a")
    res = await registry.execute("view_file", {"path": str(f)}, AgentMode.BUILD)
    assert res.success

    # create_file
    res = await registry.execute("create_file", {"path": "b.txt", "content": "b"}, AgentMode.BUILD)
    assert res.success

    # edit_file
    res = await registry.execute("edit_file", {"path": "b.txt", "start_line": 1, "end_line": 1, "new_content": "c"}, AgentMode.BUILD)
    assert res.success

    # find_in_repo
    res = await registry.execute("find_in_repo", {"query": "c"}, AgentMode.BUILD)
    assert res.success

    # remember
    res = await registry.execute("remember", {"key": "k", "value": "v"}, AgentMode.BUILD)
    assert res.success

def test_remember_stores_in_memory(registry, memory):
    registry._remember("x", "y")
    assert any("x" in m and "y" in m for m in memory.relevant_memories)
