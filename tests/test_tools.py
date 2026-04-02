from __future__ import annotations

import pytest

from src.tools.base import Tool


class DummyTool(Tool):
    name = "dummy"
    description = "A dummy tool for testing"
    input_schema = {
        "type": "object",
        "properties": {
            "value": {"type": "string", "description": "A value"},
        },
        "required": ["value"],
    }

    async def execute(self, **params: object) -> str:
        return f"got {params['value']}"


@pytest.mark.asyncio
async def test_dummy_tool_execute():
    tool = DummyTool()
    result = await tool.execute(value="hello")
    assert result == "got hello"


def test_tool_definition():
    tool = DummyTool()
    defn = tool.definition()
    assert defn["type"] == "function"
    assert defn["function"]["name"] == "dummy"
    assert defn["function"]["description"] == "A dummy tool for testing"
    assert "value" in defn["function"]["parameters"]["properties"]
