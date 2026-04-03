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


def test_main_parses_sse_transport(monkeypatch):
    """--transport sse triggers run_sse_server."""
    import src.server as mod
    called_with = {}

    async def fake_run_sse(model, ollama_url, port):
        called_with.update(model=model, ollama_url=ollama_url, port=port)

    monkeypatch.setattr(mod, "run_sse_server", fake_run_sse)
    monkeypatch.setattr(sys, "argv", ["server", "--transport", "sse", "--port", "9999"])
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
