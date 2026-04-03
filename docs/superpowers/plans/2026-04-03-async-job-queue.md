# Async Job Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 3 async MCP tools (submit/status/result) so Claude Code can delegate tasks to clawcal without hitting MCP timeouts.

**Architecture:** New `TaskManager` class manages background `asyncio.Task` instances with in-memory state tracking and file-based signals. Server registers 3 new tools that proxy to TaskManager methods. Existing `code_agent` unchanged.

**Tech Stack:** Python 3.12+, asyncio, mcp SDK, existing Agent/LlmClient/ToolRegistry

**Spec:** `docs/superpowers/specs/2026-04-03-async-job-queue-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/task_manager.py` | Create | TaskManager class — submit, status, result, background execution |
| `tests/test_task_manager.py` | Create | Unit tests for TaskManager with FakeLlmClient |
| `src/server.py` | Modify (lines 35-61, 63-103) | Register 3 new tools, instantiate TaskManager |
| `tests/test_server.py` | Modify | Add tests for new tool registration |

---

### Task 1: TaskManager — submit et exécution background

**Files:**
- Create: `src/task_manager.py`
- Create: `tests/test_task_manager.py`

- [ ] **Step 1: Write the failing test — submit returns task_id with status running**

In `tests/test_task_manager.py`:

```python
from __future__ import annotations

import pytest

from src.task_manager import TaskManager
from src.llm_client import LlmResponse
from src.tool_registry import ToolRegistry
from src.observability.cost_estimator import CostEstimator


class FakeLlmClient:
    def __init__(self, responses: list[LlmResponse]) -> None:
        self._responses = list(responses)
        self._call_index = 0

    async def chat(self, messages, tools=None):
        resp = self._responses[self._call_index]
        self._call_index += 1
        return resp

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_submit_returns_task_id():
    llm = FakeLlmClient([LlmResponse(text="Done!")])
    registry = ToolRegistry()
    cost_est = CostEstimator()
    tm = TaskManager(llm=llm, registry=registry, cost_estimator=cost_est)

    result = await tm.submit("Say hello")
    assert "task_id" in result
    assert result["status"] == "running"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && python -m pytest tests/test_task_manager.py::test_submit_returns_task_id -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.task_manager'`

- [ ] **Step 3: Write minimal TaskManager with submit**

In `src/task_manager.py`:

```python
from __future__ import annotations

import asyncio
import os
import time
import uuid
from pathlib import Path
from typing import Any

from src.agent import Agent
from src.llm_client import LlmClientProtocol
from src.observability.collector import MetricsCollector
from src.observability.cost_estimator import CostEstimator
from src.tool_registry import ToolRegistry

SIGNALS_DIR = Path.home() / ".clawcal" / "signals"


class TaskManager:
    def __init__(
        self,
        llm: LlmClientProtocol,
        registry: ToolRegistry,
        cost_estimator: CostEstimator,
        model: str = "qwen3:14b",
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._cost_estimator = cost_estimator
        self._model = model
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        SIGNALS_DIR.mkdir(parents=True, exist_ok=True)

    async def submit(
        self,
        prompt: str,
        working_directory: str | None = None,
        max_iterations: int = 20,
    ) -> dict:
        task_id = uuid.uuid4().hex[:8]
        entry = {
            "task_id": task_id,
            "status": "running",
            "prompt": prompt,
            "result": None,
            "error": None,
            "started_at": time.monotonic(),
            "finished_at": None,
        }
        self._tasks[task_id] = entry
        asyncio_task = asyncio.create_task(
            self._run_agent(task_id, prompt, working_directory, max_iterations)
        )
        entry["_asyncio_task"] = asyncio_task
        return {"task_id": task_id, "status": "running"}

    async def _run_agent(
        self,
        task_id: str,
        prompt: str,
        working_directory: str | None,
        max_iterations: int,
    ) -> None:
        entry = self._tasks[task_id]
        original_cwd = os.getcwd()
        if working_directory:
            os.chdir(working_directory)

        async with self._lock:
            try:
                session_id = task_id
                collector = MetricsCollector(
                    session_id=session_id,
                    prompt=prompt,
                    model=self._model,
                    cost_estimator=self._cost_estimator,
                )
                agent = Agent(
                    llm=self._llm,
                    registry=self._registry,
                    max_iterations=max_iterations,
                    collector=collector,
                )
                result = await agent.run(prompt)
                entry["status"] = "done"
                entry["result"] = result
                self._write_signal(task_id, "done", result)
            except Exception as e:
                entry["status"] = "error"
                entry["error"] = str(e)
                self._write_signal(task_id, "error", str(e))
            finally:
                entry["finished_at"] = time.monotonic()
                if working_directory:
                    os.chdir(original_cwd)

    def _write_signal(self, task_id: str, suffix: str, content: str) -> None:
        signal_path = SIGNALS_DIR / f"{task_id}.{suffix}"
        signal_path.write_text(content, encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && python -m pytest tests/test_task_manager.py::test_submit_returns_task_id -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal
git add src/task_manager.py tests/test_task_manager.py
git commit -m "feat: add TaskManager with async submit"
```

---

### Task 2: TaskManager — status et result

**Files:**
- Modify: `src/task_manager.py`
- Modify: `tests/test_task_manager.py`

- [ ] **Step 1: Write the failing tests — status and result**

Append to `tests/test_task_manager.py`:

```python
@pytest.mark.asyncio
async def test_status_running_then_done():
    llm = FakeLlmClient([LlmResponse(text="Done!")])
    registry = ToolRegistry()
    cost_est = CostEstimator()
    tm = TaskManager(llm=llm, registry=registry, cost_estimator=cost_est)

    submit_result = await tm.submit("Say hello")
    task_id = submit_result["task_id"]

    # Let the background task complete
    await asyncio.sleep(0.1)

    status = tm.status(task_id)
    assert status["status"] == "done"
    assert "elapsed_seconds" in status


@pytest.mark.asyncio
async def test_result_returns_output():
    llm = FakeLlmClient([LlmResponse(text="Hello world!")])
    registry = ToolRegistry()
    cost_est = CostEstimator()
    tm = TaskManager(llm=llm, registry=registry, cost_estimator=cost_est)

    submit_result = await tm.submit("Say hello")
    task_id = submit_result["task_id"]

    await asyncio.sleep(0.1)

    result = tm.result(task_id)
    assert result["status"] == "done"
    assert result["result"] == "Hello world!"


@pytest.mark.asyncio
async def test_status_unknown_task():
    llm = FakeLlmClient([])
    registry = ToolRegistry()
    cost_est = CostEstimator()
    tm = TaskManager(llm=llm, registry=registry, cost_estimator=cost_est)

    status = tm.status("nonexistent")
    assert status["status"] == "unknown"


@pytest.mark.asyncio
async def test_result_while_running():
    """result() on a running task returns status running."""
    import asyncio as _asyncio

    async def slow_chat(messages, tools=None):
        await _asyncio.sleep(1)
        return LlmResponse(text="Slow done")

    class SlowLlm:
        async def chat(self, messages, tools=None):
            return await slow_chat(messages, tools)
        async def close(self):
            pass

    registry = ToolRegistry()
    cost_est = CostEstimator()
    tm = TaskManager(llm=SlowLlm(), registry=registry, cost_estimator=cost_est)

    submit_result = await tm.submit("Slow task")
    task_id = submit_result["task_id"]

    result = tm.result(task_id)
    assert result["status"] == "running"
```

Add `import asyncio` at the top of the test file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && python -m pytest tests/test_task_manager.py -v`
Expected: FAIL — `AttributeError: 'TaskManager' object has no attribute 'status'`

- [ ] **Step 3: Add status and result methods to TaskManager**

Add to `src/task_manager.py` in the `TaskManager` class:

```python
    def status(self, task_id: str) -> dict:
        entry = self._tasks.get(task_id)
        if entry is None:
            return {"task_id": task_id, "status": "unknown"}

        elapsed = (entry["finished_at"] or time.monotonic()) - entry["started_at"]
        return {
            "task_id": task_id,
            "status": entry["status"],
            "elapsed_seconds": round(elapsed, 1),
        }

    def result(self, task_id: str) -> dict:
        entry = self._tasks.get(task_id)
        if entry is None:
            return {"task_id": task_id, "status": "unknown"}

        if entry["status"] == "running":
            return {"task_id": task_id, "status": "running", "message": "Pas encore terminé"}

        elapsed = (entry["finished_at"] or time.monotonic()) - entry["started_at"]
        if entry["status"] == "error":
            return {
                "task_id": task_id,
                "status": "error",
                "error": entry["error"],
                "elapsed_seconds": round(elapsed, 1),
            }

        return {
            "task_id": task_id,
            "status": "done",
            "result": entry["result"],
            "elapsed_seconds": round(elapsed, 1),
        }
```

- [ ] **Step 4: Run all TaskManager tests**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && python -m pytest tests/test_task_manager.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal
git add src/task_manager.py tests/test_task_manager.py
git commit -m "feat: add status and result methods to TaskManager"
```

---

### Task 3: Signal file tests

**Files:**
- Modify: `tests/test_task_manager.py`

- [ ] **Step 1: Write the failing test — signal file created on completion**

Append to `tests/test_task_manager.py`:

```python
@pytest.mark.asyncio
async def test_signal_file_created_on_done(tmp_path, monkeypatch):
    monkeypatch.setattr("src.task_manager.SIGNALS_DIR", tmp_path)

    llm = FakeLlmClient([LlmResponse(text="Signal result")])
    registry = ToolRegistry()
    cost_est = CostEstimator()
    tm = TaskManager(llm=llm, registry=registry, cost_estimator=cost_est)

    submit_result = await tm.submit("Test signals")
    task_id = submit_result["task_id"]

    await asyncio.sleep(0.1)

    signal_file = tmp_path / f"{task_id}.done"
    assert signal_file.exists()
    assert signal_file.read_text() == "Signal result"
```

- [ ] **Step 2: Run test to verify it passes** (signal writing already implemented in Task 1)

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && python -m pytest tests/test_task_manager.py::test_signal_file_created_on_done -v`
Expected: PASS (already implemented)

- [ ] **Step 3: Write test — signal file on error**

Append to `tests/test_task_manager.py`:

```python
@pytest.mark.asyncio
async def test_signal_file_created_on_error(tmp_path, monkeypatch):
    monkeypatch.setattr("src.task_manager.SIGNALS_DIR", tmp_path)

    class ErrorLlm:
        async def chat(self, messages, tools=None):
            raise RuntimeError("LLM crashed")
        async def close(self):
            pass

    registry = ToolRegistry()
    cost_est = CostEstimator()
    tm = TaskManager(llm=ErrorLlm(), registry=registry, cost_estimator=cost_est)

    submit_result = await tm.submit("Will fail")
    task_id = submit_result["task_id"]

    await asyncio.sleep(0.1)

    signal_file = tmp_path / f"{task_id}.error"
    assert signal_file.exists()
    assert "LLM crashed" in signal_file.read_text()
```

- [ ] **Step 4: Run all signal tests**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && python -m pytest tests/test_task_manager.py -k signal -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal
git add tests/test_task_manager.py
git commit -m "test: add signal file tests for TaskManager"
```

---

### Task 4: Register new tools in server.py

**Files:**
- Modify: `src/server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Write the failing test — new tools appear in list_tools**

Append to `tests/test_server.py`:

```python
import pytest
from src.server import create_server


@pytest.mark.asyncio
async def test_async_tools_registered():
    server = create_server()
    handler = server.request_handlers.get("tools/list")
    assert handler is not None
    result = await handler(None)
    tool_names = [t.name for t in result.tools]
    assert "code_agent_submit" in tool_names
    assert "code_agent_status" in tool_names
    assert "code_agent_result" in tool_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && python -m pytest tests/test_server.py::test_async_tools_registered -v`
Expected: FAIL — `code_agent_submit` not in tool names

- [ ] **Step 3: Add TaskManager and 3 new tools to server.py**

In `src/server.py`, add import at top:

```python
from src.task_manager import TaskManager
```

In `create_server()`, after `cost_estimator = CostEstimator()` (line 33), add:

```python
    task_manager = TaskManager(
        llm=llm, registry=registry, cost_estimator=cost_estimator, model=model,
    )
```

In `list_tools()`, after the `code_agent` McpTool append (before `return tools`), add:

```python
        tools.append(
            McpTool(
                name="code_agent_submit",
                description="Submit a coding task for async background execution. Returns immediately with a task_id.",
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
        tools.append(
            McpTool(
                name="code_agent_status",
                description="Check the status of a submitted task.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "Task ID from code_agent_submit"},
                    },
                    "required": ["task_id"],
                },
            )
        )
        tools.append(
            McpTool(
                name="code_agent_result",
                description="Get the result of a completed task.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "Task ID from code_agent_submit"},
                    },
                    "required": ["task_id"],
                },
            )
        )
```

In `call_tool()`, add handling before the existing `try` block at line 97:

```python
        if name == "code_agent_submit":
            import json
            result = await task_manager.submit(
                prompt=arguments["prompt"],
                working_directory=arguments.get("working_directory"),
                max_iterations=arguments.get("max_iterations", 20),
            )
            return [TextContent(type="text", text=json.dumps(result))]

        if name == "code_agent_status":
            import json
            result = task_manager.status(arguments["task_id"])
            return [TextContent(type="text", text=json.dumps(result))]

        if name == "code_agent_result":
            import json
            result = task_manager.result(arguments["task_id"])
            return [TextContent(type="text", text=json.dumps(result))]
```

- [ ] **Step 4: Run server tests**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && python -m pytest tests/test_server.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && python -m pytest -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal
git add src/server.py src/task_manager.py tests/test_server.py
git commit -m "feat: register async job queue tools in MCP server"
```

---

### Task 5: Restart service et test end-to-end

**Files:** None (manual validation)

- [ ] **Step 1: Restart clawcal service**

```bash
cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && ./clawcal.sh restart
```

- [ ] **Step 2: Verify health check**

```bash
curl -s http://127.0.0.1:8100/health | python3 -m json.tool
```

Expected: `{"server": "clawcal", "status": "running", ...}`

- [ ] **Step 3: Test submit via MCP**

Use `mcp__clawcal__code_agent_submit` with a simple prompt. Verify it returns a task_id immediately.

- [ ] **Step 4: Test status via MCP**

Use `mcp__clawcal__code_agent_status` with the task_id. Verify it returns status.

- [ ] **Step 5: Test result via MCP**

Wait for task to complete, then use `mcp__clawcal__code_agent_result`. Verify it returns the result.

- [ ] **Step 6: Commit and push**

```bash
cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal
git push origin master
```
