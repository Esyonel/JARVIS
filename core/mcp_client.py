"""
Real MCP (Model Context Protocol) client for JARVIS's own runtime.

Connects to the stdio MCP servers declared in JARVIS/.mcp.json — the same file
Claude Code reads when developing this project — so JARVIS itself can call
those servers' tools (e.g. Playwright browser control) directly, with no
Claude Code involved at runtime.

Lifecycle: `start()` is called once from JarvisLive.run() (after the asyncio
event loop exists), spawns every configured server, and keeps the stdio
connections open for the process lifetime via an AsyncExitStack. Tool
declarations are exposed the same way core/plugin_loader.py exposes plugins,
so main.py's _build_config()/_execute_tool() only need one extra call each.
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Callable

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

BASE_DIR = Path(__file__).resolve().parent.parent
MCP_CONFIG_PATH = BASE_DIR / ".mcp.json"
_CONNECT_TIMEOUT = 60  # npx may need to download the package on first run

_TYPE_MAP = {
    "string": "STRING", "integer": "INTEGER", "number": "NUMBER",
    "boolean": "BOOLEAN", "array": "ARRAY", "object": "OBJECT",
}


def _to_gemini_schema(schema: dict) -> dict:
    """Rewrites an MCP tool's JSON-Schema inputSchema into the upper-case
    type names Gemini's function-declarations expect."""
    if not isinstance(schema, dict):
        return {"type": "OBJECT", "properties": {}}
    out: dict[str, Any] = {"type": _TYPE_MAP.get(schema.get("type", "object"), "OBJECT")}
    if schema.get("description"):
        out["description"] = schema["description"]
    if schema.get("enum"):
        out["enum"] = schema["enum"]
    if out["type"] == "OBJECT":
        props = schema.get("properties") or {}
        out["properties"] = {k: _to_gemini_schema(v) for k, v in props.items()}
        if schema.get("required"):
            out["required"] = schema["required"]
    elif out["type"] == "ARRAY":
        out["items"] = _to_gemini_schema(schema.get("items") or {"type": "string"})
    return out


class MCPToolClient:
    """Owns one long-lived stdio connection per server in .mcp.json and
    exposes every server's tools as Gemini-style function declarations."""

    def __init__(self, logger: Callable[[str], None] = print):
        self._logger = logger
        self._stack = AsyncExitStack()
        self._sessions: dict[str, ClientSession] = {}   # server_name -> session
        self._tool_owner: dict[str, str] = {}           # exposed_name -> server_name
        self._tool_real_name: dict[str, str] = {}       # exposed_name -> tool name on the server
        self._declarations: list[dict] = []

    @staticmethod
    def _load_config() -> dict:
        try:
            return json.loads(MCP_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"mcpServers": {}}

    async def start(self) -> None:
        servers = self._load_config().get("mcpServers", {})
        for name, cfg in servers.items():
            try:
                await self._connect_one(name, cfg)
            except Exception as e:
                self._logger(f"MCP server '{name}' failed to start: {e}")

    async def _connect_one(self, name: str, cfg: dict) -> None:
        command = cfg.get("command")
        if not command:
            self._logger(f"MCP server '{name}' has no 'command' — skipped.")
            return

        env = dict(os.environ)
        for k, v in (cfg.get("env") or {}).items():
            env[k] = os.path.expandvars(v)

        params = StdioServerParameters(command=command, args=cfg.get("args") or [], env=env)

        # asyncio.timeout() (not wait_for) keeps the cancel scope in THIS task —
        # wait_for would run enter_async_context in a separate inner Task, and
        # anyio's stdio_client/ClientSession task groups refuse to close from a
        # different task than the one that opened them.
        async with asyncio.timeout(_CONNECT_TIMEOUT):
            read, write = await self._stack.enter_async_context(stdio_client(params))
            session = await self._stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            tools = (await session.list_tools()).tools

        self._sessions[name] = session
        for tool in tools:
            exposed_name = tool.name if tool.name not in self._tool_owner else f"{name}_{tool.name}"
            self._tool_owner[exposed_name] = name
            self._tool_real_name[exposed_name] = tool.name
            self._declarations.append({
                "name": exposed_name,
                "description": tool.description or f"MCP tool '{tool.name}' from server '{name}'.",
                "parameters": _to_gemini_schema(tool.input_schema or {}),
            })
        self._logger(
            f"MCP server '{name}' connected — {len(tools)} tool(s): "
            f"{', '.join(t.name for t in tools) or 'none'}"
        )

    def get_tool_declarations(self) -> list[dict]:
        return list(self._declarations)

    def has(self, name: str) -> bool:
        return name in self._tool_owner

    async def call(self, name: str, arguments: dict) -> str:
        server_name = self._tool_owner.get(name)
        session = self._sessions.get(server_name) if server_name else None
        if session is None:
            return f"MCP tool '{name}' is not available."

        real_name = self._tool_real_name.get(name, name)
        try:
            result = await session.call_tool(real_name, arguments or {})
        except Exception as e:
            return f"MCP tool '{name}' failed: {e}"

        parts = [block.text for block in (result.content or []) if getattr(block, "text", None)]
        return "\n".join(parts) if parts else "Done."

    async def close(self) -> None:
        await self._stack.aclose()
