from __future__ import annotations

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
