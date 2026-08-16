import pytest
from typing import Any, Generator
from unittest.mock import patch, MagicMock
from agent.tools.sandbox import DockerSandbox, SandboxConfig, DockerUnavailableError
import requests

@pytest.fixture
def mock_docker() -> Generator[MagicMock, None, None]:
    with patch("agent.tools.sandbox.docker.from_env") as mock_env:
        mock_client = MagicMock()
        mock_env.return_value = mock_client
        yield mock_client

def test_sandbox_init_no_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKER_ENABLED", "true")
    with patch("agent.tools.sandbox.docker.from_env", side_effect=Exception("No docker")):
        with pytest.raises(DockerUnavailableError):
            DockerSandbox(SandboxConfig())

def test_sandbox_init_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKER_ENABLED", "false")
    sandbox = DockerSandbox(SandboxConfig())
    assert sandbox._fallback_mode is True

@pytest.mark.asyncio
async def test_execute_happy_path(mock_docker: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKER_ENABLED", "true")
    sandbox = DockerSandbox(SandboxConfig())
    
    mock_container = MagicMock()
    mock_container.wait.return_value = {"StatusCode": 0}
    mock_container.logs.return_value = (b"hello world\n", b"")
    mock_container.attrs = {"State": {"OOMKilled": False}}
    mock_docker.containers.run.return_value = mock_container

    result = await sandbox.execute('print("hello world")')
    
    assert result.exit_code == 0
    assert result.stdout == "hello world\n"
    assert result.stderr == ""
    assert result.timeout is False
    assert result.oom_killed is False
    assert mock_container.remove.called

@pytest.mark.asyncio
async def test_timeout_killed(mock_docker: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKER_ENABLED", "true")
    sandbox = DockerSandbox(SandboxConfig())
    
    mock_container = MagicMock()
    mock_container.wait.side_effect = requests.exceptions.ReadTimeout("Timeout")
    mock_docker.containers.run.return_value = mock_container

    result = await sandbox.execute("while True: pass")
    
    assert result.timeout is True
    assert result.stderr == "Execution timed out."
    assert mock_container.remove.called

@pytest.mark.asyncio
async def test_oom_killed(mock_docker: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKER_ENABLED", "true")
    sandbox = DockerSandbox(SandboxConfig())
    
    mock_container = MagicMock()
    mock_container.wait.return_value = {"StatusCode": 137}
    mock_container.logs.return_value = (b"", b"Killed")
    mock_container.attrs = {"State": {"OOMKilled": True}}
    mock_docker.containers.run.return_value = mock_container

    result = await sandbox.execute("a = []\nwhile True: a.append(' ' * 10**6)")
    
    assert result.oom_killed is True
    assert result.exit_code == 137

def test_cleanup_orphans(mock_docker: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCKER_ENABLED", "true")
    sandbox = DockerSandbox(SandboxConfig())
    
    mock_c1 = MagicMock()
    mock_c2 = MagicMock()
    mock_docker.containers.list.return_value = [mock_c1, mock_c2]
    
    sandbox.cleanup_orphans()
    
    assert mock_c1.remove.called
    assert mock_c2.remove.called
