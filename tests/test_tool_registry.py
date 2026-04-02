from __future__ import annotations

import pytest

from src.tool_registry import ToolRegistry
from src.tools.base import Tool


class FakeTool(Tool):
    name = "fake"
    description = "Fake tool"
    input_schema = {
        "type": "object",
        "properties": {"x": {"type": "string"}},
        "required": ["x"],
    }

    async def execute(self, **params: object) -> str:
        return f"fake:{params['x']}"


class AnotherFakeTool(Tool):
    name = "another"
    description = "Another fake"
    input_schema = {"type": "object", "properties": {}, "required": []}

    async def execute(self, **params: object) -> str:
        return "another"


@pytest.fixture
def registry() -> ToolRegistry:
    r = ToolRegistry()
    r.register(FakeTool())
    r.register(AnotherFakeTool())
    return r


def test_get_definitions(registry: ToolRegistry):
    defs = registry.get_definitions()
    assert len(defs) == 2
    names = {d["function"]["name"] for d in defs}
    assert names == {"fake", "another"}


@pytest.mark.asyncio
async def test_execute_known_tool(registry: ToolRegistry):
    result = await registry.execute("fake", {"x": "bar"})
    assert result == "fake:bar"


@pytest.mark.asyncio
async def test_execute_unknown_tool(registry: ToolRegistry):
    with pytest.raises(KeyError, match="Unknown tool: nope"):
        await registry.execute("nope", {})


def test_register_duplicate(registry: ToolRegistry):
    with pytest.raises(ValueError, match="already registered"):
        registry.register(FakeTool())


from src.tools import ALL_TOOLS


def test_all_tools_loaded():
    assert len(ALL_TOOLS) == 7
    names = {t.name for t in ALL_TOOLS}
    expected = {"read_file", "write_file", "edit_file", "bash", "glob_tool", "grep_tool", "list_directory"}
    assert names == expected
