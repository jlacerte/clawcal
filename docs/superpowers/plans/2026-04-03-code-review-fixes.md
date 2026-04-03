# Code Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 3 important issues found in code review: dual lock, missing observability, signal file cleanup.

**Architecture:** Consolidate agent execution through TaskManager (eliminating the dual lock), add finalize/log_session calls to async tasks, and prune old signal files at startup + delete on result retrieval.

**Tech Stack:** Python 3.12+, asyncio, existing observability stack

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/task_manager.py` | Modify | Add observability (finalize/log), signal cleanup, accept store param |
| `src/server.py` | Modify | Route `code_agent` through TaskManager, remove `agent_lock`, move `import json` to top |
| `tests/test_task_manager.py` | Modify | Add tests for observability and signal cleanup |
| `tests/test_server.py` | Modify | Verify code_agent still works after routing change |

---

### Task 1: Unify locks — route code_agent through TaskManager

The synchronous `code_agent` and async `code_agent_submit` each have their own lock. If both are used simultaneously, they'll hit Ollama concurrently. Fix: route `code_agent` through `TaskManager.run_sync()` which uses the same lock.

**Files:**
- Modify: `src/task_manager.py`
- Modify: `src/server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Write the failing test — run_sync method exists**

Append to `tests/test_task_manager.py`:

```python
@pytest.mark.asyncio
async def test_run_sync_returns_result():
    """run_sync executes agent synchronously and returns the result string."""
    llm = FakeLlmClient([LlmResponse(text="Sync done!")])
    registry = ToolRegistry()
    cost_est = CostEstimator()
    tm = TaskManager(llm=llm, registry=registry, cost_estimator=cost_est)

    result = await tm.run_sync("Say hello")
    assert result == "Sync done!"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_task_manager.py::test_run_sync_returns_result -v`
Expected: FAIL — `AttributeError: 'TaskManager' object has no attribute 'run_sync'`

- [ ] **Step 3: Add run_sync method to TaskManager**

Add to `src/task_manager.py` in the `TaskManager` class, after `submit()`:

```python
    async def run_sync(
        self,
        prompt: str,
        working_directory: str | None = None,
        max_iterations: int = 20,
    ) -> str:
        """Run agent synchronously under the shared lock. Used by code_agent tool."""
        async with self._lock:
            original_cwd = os.getcwd()
            if working_directory:
                os.chdir(working_directory)
            try:
                collector = MetricsCollector(
                    session_id=uuid.uuid4().hex[:8],
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
                return result
            finally:
                if working_directory:
                    os.chdir(original_cwd)
```

Add `import uuid` at the top of `src/task_manager.py` if not already present.

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_task_manager.py::test_run_sync_returns_result -v`
Expected: PASS

- [ ] **Step 5: Route code_agent through TaskManager in server.py**

In `src/server.py`, move `import json` to the top-level imports (after `import uuid`):

```python
import json
```

Replace the entire `code_agent` handler block (lines 108-141) and the three async tool handlers with:

```python
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name == "code_agent":
            result = await task_manager.run_sync(
                prompt=arguments["prompt"],
                working_directory=arguments.get("working_directory"),
                max_iterations=arguments.get("max_iterations", 20),
            )
            return [TextContent(type="text", text=result)]

        if name == "code_agent_submit":
            result = await task_manager.submit(
                prompt=arguments["prompt"],
                working_directory=arguments.get("working_directory"),
                max_iterations=arguments.get("max_iterations", 20),
            )
            return [TextContent(type="text", text=json.dumps(result))]

        if name == "code_agent_status":
            result = task_manager.status(arguments["task_id"])
            return [TextContent(type="text", text=json.dumps(result))]

        if name == "code_agent_result":
            result = task_manager.result(arguments["task_id"])
            return [TextContent(type="text", text=json.dumps(result))]

        try:
            result = await registry.execute(name, arguments)
        except KeyError as e:
            return [TextContent(type="text", text=f"Error: {e}")]
        except Exception as e:
            return [TextContent(type="text", text=f"Tool execution error: {e}")]
        return [TextContent(type="text", text=result)]
```

Remove the now-unused `agent_lock = asyncio.Lock()` line and the `import uuid` from server.py (uuid is no longer used there, it's in task_manager.py).

- [ ] **Step 6: Run full test suite**

Run: `source .venv/bin/activate && python -m pytest -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/task_manager.py src/server.py tests/test_task_manager.py
git commit -m "fix: unify agent lock by routing code_agent through TaskManager"
```

---

### Task 2: Add observability to async tasks

Async tasks create a MetricsCollector but never call finalize() or log_session(). Fix: add observability calls in _run_agent, and accept an optional store for persistence.

**Files:**
- Modify: `src/task_manager.py`
- Modify: `tests/test_task_manager.py`

- [ ] **Step 1: Write the failing test — async task produces session event**

Append to `tests/test_task_manager.py`:

```python
@pytest.mark.asyncio
async def test_async_task_produces_session_event():
    """Verify that _run_agent calls finalize() and stores the session event."""
    llm = FakeLlmClient([LlmResponse(text="Observable!")])
    registry = ToolRegistry()
    cost_est = CostEstimator()
    tm = TaskManager(llm=llm, registry=registry, cost_estimator=cost_est)

    submit_result = await tm.submit("Say hello")
    task_id = submit_result["task_id"]

    await asyncio.sleep(0.1)

    entry = tm._tasks[task_id]
    assert entry.get("session_event") is not None
    assert entry["session_event"].total_iterations > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_task_manager.py::test_async_task_produces_session_event -v`
Expected: FAIL — `session_event` not in entry or is None

- [ ] **Step 3: Add observability to _run_agent**

In `src/task_manager.py`, add import at top:

```python
from src.observability.logger import log_session
```

In `_run_agent`, after `entry["status"] = "done"` and `entry["result"] = result`, add finalize and log:

Replace the try/except/finally block in `_run_agent` with:

```python
            try:
                collector = MetricsCollector(
                    session_id=task_id,
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
                if collector:
                    session_event = collector.finalize()
                    log_session(session_event)
                    entry["session_event"] = session_event
```

Also initialize `collector = None` before the try block:

```python
            collector = None
            try:
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_task_manager.py::test_async_task_produces_session_event -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `source .venv/bin/activate && python -m pytest -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/task_manager.py tests/test_task_manager.py
git commit -m "fix: add observability (finalize + log_session) to async tasks"
```

---

### Task 3: Signal file cleanup

Signal files accumulate in ~/.clawcal/signals/ indefinitely. Fix: delete signal file when result() is called, and prune files older than 24h at startup.

**Files:**
- Modify: `src/task_manager.py`
- Modify: `tests/test_task_manager.py`

- [ ] **Step 1: Write the failing test — signal file deleted after result retrieval**

Append to `tests/test_task_manager.py`:

```python
@pytest.mark.asyncio
async def test_signal_file_deleted_after_result(tmp_path, monkeypatch):
    monkeypatch.setattr("src.task_manager.SIGNALS_DIR", tmp_path)

    llm = FakeLlmClient([LlmResponse(text="Cleanup test")])
    registry = ToolRegistry()
    cost_est = CostEstimator()
    tm = TaskManager(llm=llm, registry=registry, cost_estimator=cost_est)

    submit_result = await tm.submit("Test cleanup")
    task_id = submit_result["task_id"]

    await asyncio.sleep(0.1)

    signal_file = tmp_path / f"{task_id}.done"
    assert signal_file.exists()

    tm.result(task_id)
    assert not signal_file.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_task_manager.py::test_signal_file_deleted_after_result -v`
Expected: FAIL — signal file still exists after result()

- [ ] **Step 3: Add cleanup to result() method**

In `src/task_manager.py`, modify the `result()` method. After the final return block (the `status == "done"` case), add signal file deletion. Replace the entire `result()` method with:

```python
    def result(self, task_id: str) -> dict:
        entry = self._tasks.get(task_id)
        if entry is None:
            return {"task_id": task_id, "status": "unknown"}

        if entry["status"] == "running":
            return {"task_id": task_id, "status": "running", "message": "Pas encore terminé"}

        elapsed = (entry["finished_at"] or time.monotonic()) - entry["started_at"]

        self._cleanup_signal(task_id)

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

    def _cleanup_signal(self, task_id: str) -> None:
        for suffix in ("done", "error"):
            path = SIGNALS_DIR / f"{task_id}.{suffix}"
            path.unlink(missing_ok=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_task_manager.py::test_signal_file_deleted_after_result -v`
Expected: PASS

- [ ] **Step 5: Write test — old signal files pruned at startup**

Append to `tests/test_task_manager.py`:

```python
import time as _time

@pytest.mark.asyncio
async def test_old_signals_pruned_at_startup(tmp_path, monkeypatch):
    monkeypatch.setattr("src.task_manager.SIGNALS_DIR", tmp_path)

    old_file = tmp_path / "oldtask.done"
    old_file.write_text("old result")
    old_mtime = _time.time() - (25 * 3600)
    os.utime(old_file, (old_mtime, old_mtime))

    recent_file = tmp_path / "newtask.done"
    recent_file.write_text("recent result")

    llm = FakeLlmClient([])
    registry = ToolRegistry()
    cost_est = CostEstimator()
    TaskManager(llm=llm, registry=registry, cost_estimator=cost_est)

    assert not old_file.exists()
    assert recent_file.exists()
```

Add `import os` at the top of the test file.

- [ ] **Step 6: Add startup pruning to TaskManager.__init__**

In `src/task_manager.py`, add this method to TaskManager and call it from `__init__`:

In `__init__`, after `SIGNALS_DIR.mkdir(parents=True, exist_ok=True)`, add:

```python
        self._prune_old_signals()
```

Add the method:

```python
    def _prune_old_signals(self, max_age_hours: int = 24) -> None:
        max_age_seconds = max_age_hours * 3600
        now = time.time()
        for path in SIGNALS_DIR.iterdir():
            if path.suffix in (".done", ".error"):
                age = now - path.stat().st_mtime
                if age > max_age_seconds:
                    path.unlink(missing_ok=True)
```

- [ ] **Step 7: Run all tests**

Run: `source .venv/bin/activate && python -m pytest -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/task_manager.py tests/test_task_manager.py
git commit -m "fix: add signal file cleanup on result retrieval and startup pruning"
```

---

### Task 4: Final verification and push

**Files:** None (validation only)

- [ ] **Step 1: Run full test suite**

Run: `source .venv/bin/activate && python -m pytest -v`
Expected: All PASS

- [ ] **Step 2: Restart clawcal service**

```bash
cd /Users/justinlacerte/Documents/ClaudeCodeLocal/clawcal && ./clawcal.sh restart
```

- [ ] **Step 3: Verify health check**

```bash
curl -s http://127.0.0.1:8100/health | python3 -m json.tool
```

- [ ] **Step 4: Push to GitHub**

```bash
git push origin master
```
