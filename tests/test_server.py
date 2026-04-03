from __future__ import annotations

import sys

from src.server import create_server
from src.tool_registry import ToolRegistry
from src.tools import ALL_TOOLS


def test_all_tools_available():
    registry = ToolRegistry()
    for tool in ALL_TOOLS:
        registry.register(tool)
    names = registry.names()
    assert len(names) == 7
    assert "read_file" in names
    assert "write_file" in names
    assert "edit_file" in names
    assert "bash" in names
    assert "glob_tool" in names
    assert "grep_tool" in names
    assert "list_directory" in names


def test_create_server_returns_server():
    server = create_server()
    assert server is not None
    assert server.name == "clawcal"


def test_main_parses_http_transport(monkeypatch):
    """--transport http triggers run_http_server."""
    import src.server as mod
    called_with = {}

    async def fake_run_http(model, ollama_url, port):
        called_with.update(model=model, ollama_url=ollama_url, port=port)

    monkeypatch.setattr(mod, "run_http_server", fake_run_http)
    monkeypatch.setattr(sys, "argv", ["server", "--transport", "http", "--port", "9999"])
    mod.main()
    assert called_with["port"] == 9999
    assert called_with["model"] == "qwen3:14b"


def test_main_parses_stdio_transport(monkeypatch):
    """--transport stdio triggers run_server."""
    import src.server as mod
    called_with = {}

    async def fake_run_stdio(model, ollama_url):
        called_with.update(model=model, ollama_url=ollama_url)

    monkeypatch.setattr(mod, "run_server", fake_run_stdio)
    monkeypatch.setattr(sys, "argv", ["server", "--transport", "stdio"])
    mod.main()
    assert called_with["model"] == "qwen3:14b"


import pytest
from mcp.types import ListToolsRequest


@pytest.mark.asyncio
async def test_async_tools_registered():
    server = create_server()
    handler = server.request_handlers.get(ListToolsRequest)
    assert handler is not None
    result = await handler(None)
    tool_names = [t.name for t in result.root.tools]
    assert "code_agent_submit" in tool_names
    assert "code_agent_status" in tool_names
    assert "code_agent_result" in tool_names
