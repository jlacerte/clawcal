# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Clawcal — Local coding agent MCP server powered by Ollama. Exposes 7 coding tools + a composite `code_agent` tool over MCP (SSE HTTP ou stdio). Any MCP client can use a local LLM to read, write, edit, search, and execute code autonomously.

## Stack

- Python 3.12+, async/await throughout
- mcp SDK (SSE + stdio transport), starlette, uvicorn, httpx, pydantic, aiosqlite
- Target platform: macOS

## Commands

```bash
# Run all tests
python -m pytest -v

# Run a single test file
python -m pytest tests/test_agent.py -v

# Run a single test
python -m pytest tests/test_agent.py::test_agent_single_tool_call -v

# Start SSE server (default, port 8100)
python -m src.server

# Start in stdio mode (testing/compatibility)
python -m src.server --transport stdio

# Service management (launchd)
./clawcal.sh install    # first time setup
./clawcal.sh status     # check health
./clawcal.sh restart    # after code changes
./clawcal.sh logs       # view recent output

# Install in editable mode (requires venv with Python 3.12+)
pip install -e .
```

## Architecture

**Request flow**: MCP Client → `server.py` → `Agent` → `LlmClient` (Ollama HTTP) → tool execution loop → response back to client.

### Core loop (`agent.py`)

The `Agent.run()` method iterates up to `max_iterations` (default 20):
1. Send messages + tool definitions to LLM
2. If LLM returns plain text → return it (done)
3. If LLM returns tool calls → execute each via `ToolRegistry`, append results to messages, loop

### Hybrid tool call parsing (`llm_client.py`)

`LlmClient.parse_response()` tries three modes in order:
1. **Native** — Ollama `message.tool_calls` field
2. **XML fallback** — `<tool_call>{"name": "...", "arguments": {...}}</tool_call>` regex extraction
3. **Plain text** — no tool calls

### Tool system

Each tool extends `Tool` ABC from `src/tools/base.py` with: `name`, `description`, `input_schema` (JSON Schema), and `async execute(**params) -> str`. All tools are collected in `src/tools/__init__.py` as `ALL_TOOLS` and auto-registered by the server.

To add a tool: create a class in `src/tools/`, add it to `ALL_TOOLS`, write tests. It's automatically exposed via MCP.

### MCP server (`server.py`)

- `@server.list_tools()` returns all native tools + the `code_agent` meta-tool
- `@server.call_tool()` routes: `code_agent` creates a full agent session with observability; other tools execute directly
- Two transport modes:
  - **SSE (default)** : `--transport sse --port 8100` — persistent HTTP service, `/health` endpoint, Ollama check at startup
  - **stdio** : `--transport stdio` — child process mode for testing/compatibility
- CLI args: `--model` (default `qwen3:14b`), `--ollama-url` (default `http://localhost:11434`), `--transport`, `--port`
- Managed as a macOS LaunchAgent via `clawcal.sh` (install/start/stop/status/logs)

### Observability (`src/observability/`)

Per-session pipeline: `MetricsCollector` accumulates `LlmCallEvent` and `ToolEvent` during the agent loop → `finalize()` produces a `SessionEvent` → logged to JSONL (`~/.clawcal/logs/`) + saved to SQLite (`~/.clawcal/metrics.db`). All event types are frozen dataclasses in `events.py`.

## Conventions

- Commits: conventional format (`feat:`, `test:`, `fix:`, `docs:`)
- TDD: write failing test first, then implement
- async/await for all I/O (tools, LLM, store)
- Tools return error strings on failure (no exceptions bubble to MCP)

## Testing patterns

- `FakeLlmClient`: returns a predefined sequence of `LlmResponse` objects — used to test agent logic without Ollama
- Fixtures create isolated `ToolRegistry` instances with fake tools
- All tests are `@pytest.mark.asyncio` with `asyncio_mode = "auto"` in pyproject.toml
- pytest-asyncio required (`pip install pytest pytest-asyncio`)
