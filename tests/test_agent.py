from __future__ import annotations

import os
import tempfile

import pytest

from src.agent import Agent
from src.llm_client import LlmResponse, ToolCall
from src.tool_registry import ToolRegistry
from src.tools.base import Tool
from src.tools import ALL_TOOLS


class EchoTool(Tool):
    name = "echo"
    description = "Echo input"
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    async def execute(self, **params: object) -> str:
        return f"echoed: {params['text']}"


class FakeLlmClient:
    """Simulates LLM responses in sequence."""

    def __init__(self, responses: list[LlmResponse]) -> None:
        self._responses = list(responses)
        self._call_index = 0

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LlmResponse:
        resp = self._responses[self._call_index]
        self._call_index += 1
        return resp

    async def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_agent_plain_text_response():
    registry = ToolRegistry()
    fake_llm = FakeLlmClient([LlmResponse(text="Hello!")])
    agent = Agent(llm=fake_llm, registry=registry)
    result = await agent.run("Hi")
    assert result == "Hello!"


@pytest.mark.asyncio
async def test_agent_single_tool_call():
    registry = ToolRegistry()
    registry.register(EchoTool())
    fake_llm = FakeLlmClient([
        LlmResponse(text="", tool_calls=[ToolCall(name="echo", arguments={"text": "yo"})]),
        LlmResponse(text="Done! The echo said yo."),
    ])
    agent = Agent(llm=fake_llm, registry=registry)
    result = await agent.run("Echo yo")
    assert "Done" in result


@pytest.mark.asyncio
async def test_agent_max_iterations():
    registry = ToolRegistry()
    registry.register(EchoTool())
    infinite_tool = LlmResponse(text="", tool_calls=[ToolCall(name="echo", arguments={"text": "loop"})])
    fake_llm = FakeLlmClient([infinite_tool] * 5)
    agent = Agent(llm=fake_llm, registry=registry, max_iterations=3)
    result = await agent.run("Loop forever")
    assert "max iterations" in result.lower()


@pytest.mark.asyncio
async def test_agent_reads_file_with_fake_llm():
    """End-to-end: agent uses read_file tool to read a real file."""
    tmpdir = tempfile.mkdtemp()
    filepath = os.path.join(tmpdir, "test.txt")
    with open(filepath, "w") as f:
        f.write("hello from e2e test\n")
    registry = ToolRegistry()
    for tool in ALL_TOOLS:
        registry.register(tool)
    fake_llm = FakeLlmClient([
        LlmResponse(
            text="",
            tool_calls=[ToolCall(name="read_file", arguments={"path": filepath})],
        ),
        LlmResponse(text="The file contains: hello from e2e test"),
    ])
    agent = Agent(llm=fake_llm, registry=registry)
    result = await agent.run("Read that file")
    assert "hello from e2e test" in result
