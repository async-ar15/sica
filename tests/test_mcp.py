import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.tools.aci import ToolRegistry
from agent.tools.mcp import MCPRegistry, MCPServerConfig


@pytest.fixture
def mock_tool_registry():
    sandbox = MagicMock()
    working_memory = MagicMock()
    permission_gate = MagicMock()
    registry = ToolRegistry(sandbox=sandbox, working_memory=working_memory, permission_gate=permission_gate)
    return registry

@pytest.fixture
def mcp_registry(mock_tool_registry):
    return MCPRegistry(tool_registry=mock_tool_registry)

@pytest.fixture
def mock_subprocess():
    with patch('agent.tools.mcp.asyncio.create_subprocess_exec') as mock_exec:
        mock_process = AsyncMock()
        mock_process.stdin = AsyncMock()
        mock_process.stdout = AsyncMock()
        mock_process.terminate = MagicMock()
        mock_exec.return_value = mock_process
        yield mock_exec, mock_process

@pytest.mark.asyncio
async def test_connect_launches_subprocess(mcp_registry, mock_subprocess):
    mock_exec, mock_process = mock_subprocess

    # Mock responses: initialize, tools/list
    mock_process.stdout.readline.side_effect = [
        json.dumps({"jsonrpc": "2.0", "result": {}}).encode() + b"\n",
        json.dumps({"jsonrpc": "2.0", "result": {"tools": []}}).encode() + b"\n"
    ]

    config = MCPServerConfig(name="test_server", command="dummy", args=["--arg"])
    await mcp_registry.connect(config)

    mock_exec.assert_called_once()
    assert "test_server" in mcp_registry._servers

@pytest.mark.asyncio
async def test_tool_discovery_registers_tools(mcp_registry, mock_subprocess):
    mock_exec, mock_process = mock_subprocess

    # Mock responses
    tools_list = {
        "tools": [
            {
                "name": "my_tool",
                "description": "A tool",
                "inputSchema": {"type": "object", "properties": {}}
            }
        ]
    }

    mock_process.stdout.readline.side_effect = [
        json.dumps({"jsonrpc": "2.0", "result": {}}).encode() + b"\n",
        json.dumps({"jsonrpc": "2.0", "result": tools_list}).encode() + b"\n"
    ]

    config = MCPServerConfig(name="test_server", command="dummy", args=[])
    await mcp_registry.connect(config)

    assert "test_server.my_tool" in mcp_registry._tools
    assert "test_server.my_tool" in mcp_registry.tool_registry.dynamic_tools

@pytest.mark.asyncio
async def test_tool_naming_uses_prefix(mcp_registry, mock_subprocess):
    mock_exec, mock_process = mock_subprocess

    tools_list = {"tools": [{"name": "read_file", "inputSchema": {}}]}
    mock_process.stdout.readline.side_effect = [
        json.dumps({"jsonrpc": "2.0", "result": {}}).encode() + b"\n",
        json.dumps({"jsonrpc": "2.0", "result": tools_list}).encode() + b"\n"
    ]

    await mcp_registry.connect(MCPServerConfig(name="fs", command="dummy", args=[]))
    assert "fs.read_file" in mcp_registry._tools

@pytest.mark.asyncio
async def test_call_tool_sends_jsonrpc(mcp_registry, mock_subprocess):
    mock_exec, mock_process = mock_subprocess

    tools_list = {"tools": [{"name": "my_tool", "inputSchema": {}}]}
    mock_process.stdout.readline.side_effect = [
        json.dumps({"jsonrpc": "2.0", "result": {}}).encode() + b"\n",
        json.dumps({"jsonrpc": "2.0", "result": tools_list}).encode() + b"\n",
        json.dumps({"jsonrpc": "2.0", "result": {"content": "tool output"}}).encode() + b"\n"
    ]

    await mcp_registry.connect(MCPServerConfig(name="test", command="dummy", args=[]))

    res = await mcp_registry.call_tool("test.my_tool", {"param": 1})
    assert res == {"content": "tool output"}

    # Check that tools/call was written to stdin
    written = mock_process.stdin.write.call_args_list[-1][0][0]
    req = json.loads(written.decode())
    assert req["method"] == "tools/call"
    assert req["params"]["name"] == "my_tool"

@pytest.mark.asyncio
async def test_disconnect_terminates_process(mcp_registry, mock_subprocess):
    mock_exec, mock_process = mock_subprocess

    mock_process.stdout.readline.side_effect = [
        json.dumps({"jsonrpc": "2.0", "result": {}}).encode() + b"\n",
        json.dumps({"jsonrpc": "2.0", "result": {"tools": []}}).encode() + b"\n"
    ]

    await mcp_registry.connect(MCPServerConfig(name="test", command="dummy", args=[]))
    assert "test" in mcp_registry._servers

    await mcp_registry.disconnect("test")
    assert "test" not in mcp_registry._servers
    mock_process.terminate.assert_called_once()

@pytest.mark.asyncio
async def test_disconnect_all_cleans_up(mcp_registry, mock_subprocess):
    mock_exec, mock_process = mock_subprocess

    mock_process.stdout.readline.side_effect = [
        json.dumps({"jsonrpc": "2.0", "result": {}}).encode() + b"\n",
        json.dumps({"jsonrpc": "2.0", "result": {"tools": []}}).encode() + b"\n",
        json.dumps({"jsonrpc": "2.0", "result": {}}).encode() + b"\n",
        json.dumps({"jsonrpc": "2.0", "result": {"tools": []}}).encode() + b"\n"
    ]

    await mcp_registry.connect(MCPServerConfig(name="test1", command="dummy", args=[]))
    await mcp_registry.connect(MCPServerConfig(name="test2", command="dummy", args=[]))

    assert len(mcp_registry._servers) == 2
    await mcp_registry.disconnect_all()
    assert len(mcp_registry._servers) == 0

@pytest.mark.asyncio
async def test_failed_server_skipped(mcp_registry, mock_subprocess):
    mock_exec, mock_process = mock_subprocess
    mock_exec.side_effect = Exception("Failed to launch")

    await mcp_registry.connect(MCPServerConfig(name="test", command="dummy", args=[]))
    assert "test" not in mcp_registry._servers

@pytest.mark.asyncio
async def test_build_only_permissions(mcp_registry, mock_subprocess):
    mock_exec, mock_process = mock_subprocess

    tools_list = {"tools": [{"name": "my_tool", "inputSchema": {}}]}
    mock_process.stdout.readline.side_effect = [
        json.dumps({"jsonrpc": "2.0", "result": {}}).encode() + b"\n",
        json.dumps({"jsonrpc": "2.0", "result": tools_list}).encode() + b"\n"
    ]

    await mcp_registry.connect(MCPServerConfig(name="test", command="dummy", args=[]))
    mcp_registry.tool_registry.permission_gate.allow_in_build_only.assert_called_with("test.my_tool")
