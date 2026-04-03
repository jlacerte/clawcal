# Fix MCP Session Management & Production Hardening

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the broken Streamable HTTP session management that causes "Failed to reconnect to clawcal" in Claude Code, and address all issues found in the code review.

**Architecture:** Replace the per-request `StreamableHTTPServerTransport` creation with the SDK's `StreamableHTTPSessionManager` which handles session lifecycle, transport pooling, and request routing. Then fix broken tests, add integration tests for the real transport, and harden production code (resource cleanup, error handling, grep exclusions).

**Tech Stack:** Python 3.12+, mcp SDK 1.27.0, Starlette, uvicorn, pytest, pytest-asyncio

---

### Task 1: Fix `handle_mcp()` with `StreamableHTTPSessionManager` (CRITICAL)

**Files:**
- Modify: `src/server.py:112-165` (the `run_http_server` function)

This is the root cause of "Failed to reconnect". The current code creates a new transport per request, breaking MCP's stateful session protocol.

- [ ] **Step 1: Write the failing test**

Create a test that verifies the MCP session lifecycle works (initialize, then tools/list on the same session).

Add to `tests/test_http_integration.py`:

```python
from __future__ import annotations

import json

from starlette.testclient import TestClient

from src.server import create_http_app


def test_mcp_initialize_returns_session_id():
    """POST /mcp with initialize must return 200 and Mcp-Session-Id header."""
    app = create_http_app(model="qwen3:14b", ollama_url="http://localhost:11434")
    client = TestClient(app)
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200
    assert "mcp-session-id" in resp.headers


def test_mcp_tools_list_with_session():
    """After initialize, tools/list with the same session ID must work."""
    app = create_http_app(model="qwen3:14b", ollama_url="http://localhost:11434")
    client = TestClient(app)

    # Step 1: initialize
    init_resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
    )
    assert init_resp.status_code == 200
    session_id = init_resp.headers.get("mcp-session-id")
    assert session_id is not None

    # Step 2: Send initialized notification
    client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "Mcp-Session-Id": session_id,
        },
    )

    # Step 3: tools/list with session ID
    list_resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "Mcp-Session-Id": session_id,
        },
    )
    assert list_resp.status_code == 200
    data = json.loads(list_resp.text.split("data: ")[1].split("\n")[0])
    assert "result" in data
    assert "tools" in data["result"]
    tool_names = [t["name"] for t in data["result"]["tools"]]
    assert "code_agent" in tool_names
    assert "read_file" in tool_names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && .venv/bin/python -m pytest tests/test_http_integration.py -v`
Expected: FAIL because `create_http_app` does not exist yet.

- [ ] **Step 3: Refactor `run_http_server` and extract `create_http_app`**

Replace the entire `run_http_server` function in `src/server.py` (lines 112-165) with:

```python
def create_http_app(
    model: str = "qwen3:14b",
    ollama_url: str = "http://localhost:11434",
) -> "Starlette":
    """Build the Starlette app with StreamableHTTPSessionManager.

    Separated from run_http_server so tests can use it without uvicorn.
    """
    import contextlib

    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    from src.health import check_ollama

    server = create_server(model=model, ollama_url=ollama_url)

    session_manager = StreamableHTTPSessionManager(
        app=server,
        json_response=True,
    )

    async def handle_mcp(request):
        await session_manager.handle_request(
            request.scope, request.receive, request._send
        )

    async def handle_health(request):
        status = await check_ollama(ollama_url)
        return JSONResponse({
            "server": "clawcal",
            "status": "running",
            "model": model,
            "ollama": status,
        })

    @contextlib.asynccontextmanager
    async def lifespan(app):
        async with session_manager.run():
            yield

    return Starlette(
        routes=[
            Route("/health", handle_health, methods=["GET"]),
            Route("/mcp", handle_mcp, methods=["GET", "POST", "DELETE"]),
        ],
        lifespan=lifespan,
    )


async def run_http_server(model: str, ollama_url: str, port: int) -> None:
    import uvicorn

    from src.health import check_ollama

    setup_logging(console=False)

    # Fail fast if Ollama is unreachable
    ollama_status = await check_ollama(ollama_url)
    if ollama_status["status"] != "ok":
        import sys as _sys
        print(f"FATAL: Ollama not reachable at {ollama_url}: {ollama_status.get('error')}", file=_sys.stderr)
        _sys.exit(1)

    app = create_http_app(model=model, ollama_url=ollama_url)

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info")
    uv_server = uvicorn.Server(config)
    await uv_server.serve()
```

Note: the `MetricsStore` (SQLite persistence) is removed from the HTTP startup for now. The `create_server` function already accepts `store=None` and handles it. The store will be re-added properly in Task 5 (resource cleanup).

- [ ] **Step 4: Run the integration tests**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && .venv/bin/python -m pytest tests/test_http_integration.py -v`
Expected: PASS for both tests.

If the `json_response=True` approach doesn't match the expected response format in the test assertions, adjust the test parsing. The key thing: `initialize` returns 200 with an `mcp-session-id` header, and `tools/list` returns the tool list within the same session.

- [ ] **Step 5: Run all existing tests to check for regressions**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && .venv/bin/python -m pytest -v`
Expected: All tests pass except possibly `test_main_parses_sse_transport` (fixed in Task 2).

- [ ] **Step 6: Commit**

```bash
git add src/server.py tests/test_http_integration.py
git commit -m "fix: replace per-request transport with StreamableHTTPSessionManager

Fixes 'Failed to reconnect' by using the SDK's session manager
for proper MCP session lifecycle handling."
```

---

### Task 2: Fix broken test `test_main_parses_sse_transport`

**Files:**
- Modify: `tests/test_server.py:31-42`

The test references `run_sse_server` and `--transport sse`, both of which no longer exist after the migration to Streamable HTTP.

- [ ] **Step 1: Update the test to match current code**

Replace lines 31-42 in `tests/test_server.py` with:

```python
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
```

- [ ] **Step 2: Run the test**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && .venv/bin/python -m pytest tests/test_server.py -v`
Expected: All 3 tests PASS (test_all_tools_available, test_create_server_returns_server, test_main_parses_http_transport, test_main_parses_stdio_transport).

- [ ] **Step 3: Commit**

```bash
git add tests/test_server.py
git commit -m "fix: update transport test from SSE to Streamable HTTP"
```

---

### Task 3: Rewrite `test_sse_integration.py` for Streamable HTTP

**Files:**
- Delete: `tests/test_sse_integration.py`
- The integration tests are now in `tests/test_http_integration.py` (created in Task 1)

The old SSE integration test file imports `SseServerTransport` and builds a test app with `/sse` and `/messages/` endpoints that no longer match the server. The health endpoint tests are redundant with the new integration test file.

- [ ] **Step 1: Add health endpoint tests to `test_http_integration.py`**

Append to `tests/test_http_integration.py`:

```python
def test_health_endpoint():
    app = create_http_app(model="qwen3:14b", ollama_url="http://localhost:11434")
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["server"] == "clawcal"
    assert data["status"] == "running"


def test_health_returns_expected_fields():
    app = create_http_app(model="qwen3:14b", ollama_url="http://localhost:11434")
    client = TestClient(app)
    data = client.get("/health").json()
    assert "server" in data
    assert "model" in data
    assert "ollama" in data
```

- [ ] **Step 2: Delete the old SSE integration test file**

```bash
rm tests/test_sse_integration.py
```

- [ ] **Step 3: Run all tests**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && .venv/bin/python -m pytest -v`
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_http_integration.py
git rm tests/test_sse_integration.py
git commit -m "refactor: replace SSE integration tests with Streamable HTTP tests"
```

---

### Task 4: Add error handling for direct tool execution

**Files:**
- Modify: `src/server.py:92` (the `call_tool` handler, direct tool path)
- Modify: `tests/test_server.py` (add test)

When a tool other than `code_agent` is called, `registry.execute()` can raise `KeyError` for unknown tools. This exception propagates unhandled and crashes the request.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_server.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_call_unknown_tool_returns_error():
    """Calling an unknown tool should return an error message, not raise."""
    server = create_server()
    # Access the registered call_tool handler
    handler = server.request_handlers.get("tools/call")
    assert handler is not None
    from mcp.types import CallToolRequest, CallToolRequestParams
    request = CallToolRequest(
        method="tools/call",
        params=CallToolRequestParams(name="nonexistent_tool", arguments={}),
    )
    result = await handler(request)
    assert len(result.content) == 1
    assert "Unknown tool" in result.content[0].text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && .venv/bin/python -m pytest tests/test_server.py::test_call_unknown_tool_returns_error -v`
Expected: FAIL with `KeyError: 'Unknown tool: nonexistent_tool'`

- [ ] **Step 3: Add try/except around direct tool execution**

In `src/server.py`, in the `call_tool` handler, replace line 92:

```python
        result = await registry.execute(name, arguments)
        return [TextContent(type="text", text=result)]
```

with:

```python
        try:
            result = await registry.execute(name, arguments)
        except KeyError as e:
            return [TextContent(type="text", text=f"Error: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Tool execution error: {e}")]
        return [TextContent(type="text", text=result)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && .venv/bin/python -m pytest tests/test_server.py::test_call_unknown_tool_returns_error -v`
Expected: PASS

Note: if the MCP `Server` doesn't expose `request_handlers` directly, adjust the test approach. An alternative is to test via the HTTP integration test by sending a `tools/call` JSONRPC request for an unknown tool through `/mcp`, which is more realistic:

```python
def test_call_unknown_tool_returns_error():
    app = create_http_app()
    client = TestClient(app)
    # Initialize session first
    init_resp = client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": {"name": "test", "version": "1.0"}},
    }, headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"})
    session_id = init_resp.headers.get("mcp-session-id")
    # Send initialized notification
    client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                headers={"Accept": "application/json, text/event-stream",
                         "Content-Type": "application/json", "Mcp-Session-Id": session_id})
    # Call unknown tool
    resp = client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "nonexistent_tool", "arguments": {}},
    }, headers={"Accept": "application/json, text/event-stream",
                "Content-Type": "application/json", "Mcp-Session-Id": session_id})
    assert resp.status_code == 200
```

Use whichever approach works with the SDK's internals.

- [ ] **Step 5: Commit**

```bash
git add src/server.py tests/test_server.py
git commit -m "fix: handle unknown tool calls gracefully instead of crashing"
```

---

### Task 5: Fix `LlmClient` resource leak and `MetricsStore` lifecycle

**Files:**
- Modify: `src/server.py` (`create_server` and `create_http_app`)

The `LlmClient` creates an `httpx.AsyncClient` that is never closed in the HTTP server path. The `MetricsStore` was removed from `create_http_app` in Task 1 and needs to be re-added with proper lifecycle.

- [ ] **Step 1: Refactor `create_server` to accept and store the `LlmClient`**

In `src/server.py`, modify `create_server` to accept an optional `llm` parameter:

```python
def create_server(
    model: str = "qwen3:14b",
    ollama_url: str = "http://localhost:11434",
    store: MetricsStore | None = None,
    llm: LlmClient | None = None,
) -> Server:
    server = Server("clawcal")

    registry = ToolRegistry()
    for tool in ALL_TOOLS:
        registry.register(tool)

    if llm is None:
        llm = LlmClient(ollama_url=ollama_url, model=model)
    cost_estimator = CostEstimator()
```

The rest of `create_server` stays the same. This allows tests to pass `llm=None` (auto-creates one) while the HTTP server can manage the lifecycle externally.

- [ ] **Step 2: Add lifecycle management in `create_http_app`**

Update `create_http_app` in `src/server.py` to create and close resources in the lifespan:

```python
def create_http_app(
    model: str = "qwen3:14b",
    ollama_url: str = "http://localhost:11434",
) -> "Starlette":
    import contextlib

    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    from src.health import check_ollama

    llm = LlmClient(ollama_url=ollama_url, model=model)
    store = MetricsStore()
    server = create_server(model=model, ollama_url=ollama_url, store=store, llm=llm)

    session_manager = StreamableHTTPSessionManager(
        app=server,
        json_response=True,
    )

    async def handle_mcp(request):
        await session_manager.handle_request(
            request.scope, request.receive, request._send
        )

    async def handle_health(request):
        status = await check_ollama(ollama_url)
        return JSONResponse({
            "server": "clawcal",
            "status": "running",
            "model": model,
            "ollama": status,
        })

    @contextlib.asynccontextmanager
    async def lifespan(app):
        await store.init()
        async with session_manager.run():
            try:
                yield
            finally:
                await llm.close()
                await store.close()

    return Starlette(
        routes=[
            Route("/health", handle_health, methods=["GET"]),
            Route("/mcp", handle_mcp, methods=["GET", "POST", "DELETE"]),
        ],
        lifespan=lifespan,
    )
```

- [ ] **Step 3: Run all tests**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && .venv/bin/python -m pytest -v`
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add src/server.py
git commit -m "fix: proper lifecycle management for LlmClient and MetricsStore

LlmClient httpx connection and MetricsStore SQLite connection are
now created in lifespan and closed on shutdown."
```

---

### Task 6: Fix `os.chdir` concurrency issue in `code_agent`

**Files:**
- Modify: `src/server.py` (the `call_tool` handler, `code_agent` branch)

`os.chdir()` changes the process-wide working directory. If two `code_agent` sessions run concurrently with different `working_directory` values, they corrupt each other.

- [ ] **Step 1: Add an asyncio.Lock to serialize `code_agent` execution**

In `src/server.py`, inside `create_server`, add a lock before the `@server.call_tool()` decorator:

```python
    agent_lock = asyncio.Lock()

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "code_agent":
            async with agent_lock:
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
        try:
            result = await registry.execute(name, arguments)
        except KeyError as e:
            return [TextContent(type="text", text=f"Error: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Tool execution error: {e}")]
        return [TextContent(type="text", text=result)]
```

- [ ] **Step 2: Run all tests**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && .venv/bin/python -m pytest -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add src/server.py
git commit -m "fix: serialize code_agent execution with asyncio.Lock

Prevents os.chdir() race condition when multiple sessions
call code_agent concurrently."
```

---

### Task 7: Add directory exclusions to `GrepTool`

**Files:**
- Modify: `src/tools/grep_tool.py:33`
- Modify: `tests/test_tools.py` (add test)

`os.walk()` traverses `.git`, `.venv`, `node_modules`, `__pycache__` etc., making grep slow on real repos and scanning binary/irrelevant files.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_tools.py`:

```python
@pytest.mark.asyncio
async def test_grep_skips_excluded_directories(tmp_path):
    """grep_tool should skip .git, .venv, node_modules, __pycache__."""
    from src.tools.grep_tool import GrepTool

    # Create files in excluded directories
    for excluded in [".git", ".venv", "node_modules", "__pycache__"]:
        d = tmp_path / excluded
        d.mkdir()
        (d / "match.py").write_text("findme_secret_pattern")

    # Create a file in a normal directory
    (tmp_path / "normal.py").write_text("findme_secret_pattern")

    tool = GrepTool()
    result = await tool.execute(pattern="findme_secret_pattern", path=str(tmp_path))
    assert "normal.py" in result
    assert ".git" not in result
    assert ".venv" not in result
    assert "node_modules" not in result
    assert "__pycache__" not in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && .venv/bin/python -m pytest tests/test_tools.py::test_grep_skips_excluded_directories -v`
Expected: FAIL because `.git/match.py` etc. appear in results.

- [ ] **Step 3: Add directory exclusions to `GrepTool`**

In `src/tools/grep_tool.py`, replace line 33:

```python
        for root, _dirs, files in os.walk(path):
```

with:

```python
        _EXCLUDED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache"}
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in _EXCLUDED_DIRS]
```

Note: `dirs[:] =` modifies in-place to prune `os.walk` traversal.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && .venv/bin/python -m pytest tests/test_tools.py::test_grep_skips_excluded_directories -v`
Expected: PASS

- [ ] **Step 5: Run all tests**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && .venv/bin/python -m pytest -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/tools/grep_tool.py tests/test_tools.py
git commit -m "fix: exclude .git, .venv, node_modules from grep traversal"
```

---

### Task 8: Clean up untracked scripts & end-to-end verification

**Files:**
- Delete: `install_mcp.sh` (outdated stdio-mode installer)
- Delete: `run_server.sh` (redundant with `clawcal.sh`)
- Delete: `start_mcp.sh` (redundant with `clawcal.sh`)
- Delete: `test_live.py` (ad-hoc test script)

These 4 untracked files are leftover from earlier development and are redundant with `clawcal.sh`.

- [ ] **Step 1: Verify scripts are redundant**

Check each file briefly to confirm it's superseded by `clawcal.sh` or the test suite. If any has unique functionality, keep it.

- [ ] **Step 2: Delete redundant scripts**

```bash
rm -f install_mcp.sh run_server.sh start_mcp.sh test_live.py
```

- [ ] **Step 3: Run the full test suite**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && .venv/bin/python -m pytest -v`
Expected: All tests PASS.

- [ ] **Step 4: Restart the service and verify Claude Code connection**

```bash
cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal
./clawcal.sh restart
sleep 3
./clawcal.sh status
```

Then test the MCP endpoint directly:

```bash
curl -s -X POST http://127.0.0.1:8100/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'
```

Expected: 200 response with `mcp-session-id` header and server info in body.

- [ ] **Step 5: Commit**

```bash
git commit -m "chore: remove redundant startup scripts superseded by clawcal.sh"
```

- [ ] **Step 6: Final — restart Claude Code and verify MCP reconnection**

Instruct the user to restart Claude Code. The `/mcp` command should show clawcal as connected.
