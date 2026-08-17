import asyncio
import json
import logging
import os
import uuid
from asyncio.subprocess import PIPE, Process
from typing import Any

from pydantic import BaseModel

from agent.tools.aci import ToolRegistry

logger = logging.getLogger(__name__)

class MCPServerConfig(BaseModel):
    name: str
    command: str
    args: list[str]
    env: dict[str, str] = {}

class MCPToolDefinition(BaseModel):
    server_name: str
    tool_name: str
    qualified_name: str
    description: str
    parameters: dict[str, Any]

class MCPRegistry:
    def __init__(self, tool_registry: ToolRegistry):
        self.tool_registry = tool_registry
        self._servers: dict[str, Process] = {}
        self._tools: dict[str, MCPToolDefinition] = {}

    async def connect(self, config: MCPServerConfig) -> None:
        try:
            env = {**os.environ, **config.env}
            process = await asyncio.create_subprocess_exec(
                config.command,
                *config.args,
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE,
                env=env
            )

            # Send initialize
            init_res = await self._send_jsonrpc(process, "initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "sica", "version": "0.1"}
            })

            # Send initialized notification
            await self._send_notification(process, "notifications/initialized")

            # Discover tools
            tools_res = await self._send_jsonrpc(process, "tools/list", {})
            tools = tools_res.get("tools", [])

            for t in tools:
                tool_name = t.get("name")
                qualified_name = f"{config.name}.{tool_name}"
                desc = t.get("description", "")
                params = t.get("inputSchema", {})

                tool_def = MCPToolDefinition(
                    server_name=config.name,
                    tool_name=tool_name,
                    qualified_name=qualified_name,
                    description=desc,
                    parameters=params
                )

                self._tools[qualified_name] = tool_def

                schema = {
                    "type": "function",
                    "function": {
                        "name": qualified_name,
                        "description": desc,
                        "parameters": params
                    }
                }

                self.tool_registry.register_mcp_tool(schema, self.call_tool)
                # Ensure it's build-only (the permission_gate check in aci.py uses the name)
                # Assuming permission_gate has a way to register or we handle it via name pattern
                self.tool_registry.permission_gate.allow_in_build_only(qualified_name)

            self._servers[config.name] = process
            logger.info(f"Connected to MCP server: {config.name}")

        except Exception as e:
            logger.warning(f"Failed to connect to MCP server {config.name}: {e}")

    async def call_tool(self, qualified_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if qualified_name not in self._tools:
            raise ValueError(f"Unknown MCP tool: {qualified_name}")

        tool_def = self._tools[qualified_name]
        server_name = tool_def.server_name

        if server_name not in self._servers:
            raise RuntimeError(f"MCP server {server_name} is not connected")

        process = self._servers[server_name]

        res = await self._send_jsonrpc(process, "tools/call", {
            "name": tool_def.tool_name,
            "arguments": params
        })
        return res

    async def disconnect(self, server_name: str) -> None:
        if server_name in self._servers:
            process = self._servers[server_name]
            try:
                process.terminate()
            except Exception:
                pass
            del self._servers[server_name]

            # Remove tools
            to_remove = [k for k, v in self._tools.items() if v.server_name == server_name]
            for k in to_remove:
                del self._tools[k]
                if k in self.tool_registry.dynamic_tools:
                    del self.tool_registry.dynamic_tools[k]
                if k in self.tool_registry.mcp_handlers:
                    del self.tool_registry.mcp_handlers[k]

    async def disconnect_all(self) -> None:
        servers = list(self._servers.keys())
        for s in servers:
            await self.disconnect(s)

    async def _send_jsonrpc(self, process: Process, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        req_id = str(uuid.uuid4())
        req = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params
        }

        req_bytes = json.dumps(req).encode('utf-8') + b'\n'
        if process.stdin:
            process.stdin.write(req_bytes)
            await process.stdin.drain()

        if process.stdout:
            line = await process.stdout.readline()
            if not line:
                raise ConnectionError("MCP server disconnected unexpectedly")

            res: dict[str, Any] = json.loads(line.decode('utf-8'))
            if "error" in res:
                raise RuntimeError(f"MCP Error: {res['error']}")
            result: dict[str, Any] = res.get("result", {})
            return result

        raise RuntimeError("Process stdout not available")

    async def _send_notification(self, process: Process, method: str, params: dict[str, Any] | None = None) -> None:
        req = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }

        req_bytes = json.dumps(req).encode('utf-8') + b'\n'
        if process.stdin:
            process.stdin.write(req_bytes)
            await process.stdin.drain()
