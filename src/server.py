from __future__ import annotations

import argparse
import asyncio
import os

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool as McpTool, TextContent

from src.agent import Agent
from src.llm_client import LlmClient
from src.tool_registry import ToolRegistry
from src.tools import ALL_TOOLS


def create_server(
    model: str = "qwen3:14b",
    ollama_url: str = "http://localhost:11434",
) -> Server:
    server = Server("clawcal")

    registry = ToolRegistry()
    for tool in ALL_TOOLS:
        registry.register(tool)

    llm = LlmClient(ollama_url=ollama_url, model=model)

    @server.list_tools()
    async def list_tools() -> list[McpTool]:
        tools = []
        for t in ALL_TOOLS:
            tools.append(
                McpTool(
                    name=t.name,
                    description=t.description,
                    inputSchema=t.input_schema,
                )
            )
        tools.append(
            McpTool(
                name="code_agent",
                description="Send a natural language coding task to the local AI agent.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "Natural language coding task"},
                        "working_directory": {"type": "string", "description": "Working directory (default: cwd)"},
                        "max_iterations": {"type": "integer", "description": "Max agent iterations (default: 20)"},
                    },
                    "required": ["prompt"],
                },
            )
        )
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "code_agent":
            cwd = arguments.get("working_directory")
            original_cwd = os.getcwd()
            if cwd:
                os.chdir(cwd)
            try:
                max_iter = arguments.get("max_iterations", 20)
                agent = Agent(llm=llm, registry=registry, max_iterations=max_iter)
                result = await agent.run(arguments["prompt"])
            finally:
                if cwd:
                    os.chdir(original_cwd)
            return [TextContent(type="text", text=result)]
        result = await registry.execute(name, arguments)
        return [TextContent(type="text", text=result)]

    return server


async def run_server(model: str, ollama_url: str) -> None:
    server = create_server(model=model, ollama_url=ollama_url)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    parser = argparse.ArgumentParser(description="Clawcal MCP Server")
    parser.add_argument("--model", default="qwen3:14b", help="Ollama model name")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama URL")
    args = parser.parse_args()
    asyncio.run(run_server(model=args.model, ollama_url=args.ollama_url))


if __name__ == "__main__":
    main()
