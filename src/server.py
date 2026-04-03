from __future__ import annotations

import argparse
import asyncio
import os
import uuid

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool as McpTool, TextContent

from src.agent import Agent
from src.llm_client import LlmClient
from src.observability import MetricsCollector, CostEstimator, MetricsStore, setup_logging, log_session
from src.tool_registry import ToolRegistry
from src.tools import ALL_TOOLS


def create_server(
    model: str = "qwen3:14b",
    ollama_url: str = "http://localhost:11434",
    store: MetricsStore | None = None,
) -> Server:
    server = Server("clawcal")

    registry = ToolRegistry()
    for tool in ALL_TOOLS:
        registry.register(tool)

    llm = LlmClient(ollama_url=ollama_url, model=model)
    cost_estimator = CostEstimator()

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

            session_id = str(uuid.uuid4())
            collector = MetricsCollector(
                session_id=session_id,
                prompt=arguments["prompt"],
                model=model,
                cost_estimator=cost_estimator,
            )

            try:
                max_iter = arguments.get("max_iterations", 20)
                agent = Agent(llm=llm, registry=registry, max_iterations=max_iter, collector=collector)
                result = await agent.run(arguments["prompt"])
            finally:
                if cwd:
                    os.chdir(original_cwd)

            session_event = collector.finalize()
            log_session(session_event)

            if store:
                await store.save_session(session_event, collector.llm_events, collector.tool_events)

            return [TextContent(type="text", text=result)]
        result = await registry.execute(name, arguments)
        return [TextContent(type="text", text=result)]

    return server


async def run_server(model: str, ollama_url: str) -> None:
    setup_logging()

    store = MetricsStore()
    await store.init()

    server = create_server(model=model, ollama_url=ollama_url, store=store)
    try:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    finally:
        await store.close()


async def run_sse_server(model: str, ollama_url: str, port: int) -> None:
    import uvicorn
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Mount, Route
    from mcp.server.sse import SseServerTransport

    from src.health import check_ollama

    setup_logging(console=False)

    # Fail fast if Ollama is unreachable
    ollama_status = await check_ollama(ollama_url)
    if ollama_status["status"] != "ok":
        import sys as _sys
        print(f"FATAL: Ollama not reachable at {ollama_url}: {ollama_status.get('error')}", file=_sys.stderr)
        _sys.exit(1)

    store = MetricsStore()
    await store.init()

    server = create_server(model=model, ollama_url=ollama_url, store=store)
    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())
        return Response()

    async def handle_health(request):
        status = await check_ollama(ollama_url)
        return JSONResponse({
            "server": "clawcal",
            "status": "running",
            "model": model,
            "ollama": status,
        })

    app = Starlette(
        routes=[
            Route("/health", handle_health, methods=["GET"]),
            Route("/sse", handle_sse, methods=["GET"]),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    uv_server = uvicorn.Server(config)
    try:
        await uv_server.serve()
    finally:
        await store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Clawcal MCP Server")
    parser.add_argument("--model", default="qwen3:14b", help="Ollama model name")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama URL")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="sse", help="Transport mode")
    parser.add_argument("--port", type=int, default=8100, help="SSE server port")
    args = parser.parse_args()

    if args.transport == "sse":
        asyncio.run(run_sse_server(model=args.model, ollama_url=args.ollama_url, port=args.port))
    else:
        asyncio.run(run_server(model=args.model, ollama_url=args.ollama_url))


if __name__ == "__main__":
    main()
