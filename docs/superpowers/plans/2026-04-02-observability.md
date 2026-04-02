# Clawcal Observability — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured logging, metrics collection, SQLite persistence, and cloud cost estimation to Clawcal so every LLM call, tool execution, and agent session is measured and queryable.

**Architecture:** New `src/observability/` module with 5 files (events, logger, collector, store, cost_estimator). Integrated into existing code via optional callback pattern — zero regression on 32 existing tests. SQLite for persistence, Python `logging` for dual output (terminal + JSON file).

**Tech Stack:** Python 3.12+, aiosqlite, Python logging stdlib, SQLite

---

## File Map

| File | Responsibility |
|------|---------------|
| `src/observability/__init__.py` | Public exports |
| `src/observability/events.py` | Frozen dataclasses: LlmCallEvent, ToolEvent, SessionEvent |
| `src/observability/cost_estimator.py` | Configurable price table, cloud cost calculation |
| `src/observability/logger.py` | Dual logging: terminal text + JSON file with rotation |
| `src/observability/collector.py` | Per-session metrics aggregation, produces SessionEvent |
| `src/observability/store.py` | SQLite persistence + query methods |
| `src/llm_client.py` | MODIFY: add LlmUsage dataclass, extract usage from Ollama response |
| `src/agent.py` | MODIFY: accept optional collector, record events |
| `src/server.py` | MODIFY: init logging + store, wire collector per session |
| `pyproject.toml` | MODIFY: add aiosqlite dependency |
| `tests/test_events.py` | Tests for events dataclasses |
| `tests/test_cost_estimator.py` | Tests for cost estimation |
| `tests/test_logger.py` | Tests for structured logging |
| `tests/test_collector.py` | Tests for metrics collector |
| `tests/test_store.py` | Tests for SQLite store |
| `tests/test_agent.py` | MODIFY: add tests for collector integration |
| `tests/test_llm_client.py` | MODIFY: add tests for LlmUsage parsing |

---

## Task 1: Events dataclasses

**Files:**
- Create: `src/observability/__init__.py`
- Create: `src/observability/events.py`
- Create: `tests/test_events.py`

- [ ] **Step 1: Create observability package**

`src/observability/__init__.py`:
```python
```

- [ ] **Step 2: Write the failing tests**

`tests/test_events.py`:
```python
from __future__ import annotations

from src.observability.events import LlmCallEvent, ToolEvent, SessionEvent


def test_llm_call_event_frozen():
    event = LlmCallEvent(
        timestamp="2026-04-02T14:00:00",
        session_id="abc-123",
        model="qwen3:14b",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        latency_ms=1200.0,
        tokens_per_second=41.7,
        had_tool_calls=True,
    )
    assert event.total_tokens == 150
    assert event.had_tool_calls is True


def test_tool_event_frozen():
    event = ToolEvent(
        timestamp="2026-04-02T14:00:01",
        session_id="abc-123",
        tool_name="read_file",
        parameters={"path": "/tmp/test.txt"},
        duration_ms=45.0,
        success=True,
        error=None,
        result_length=120,
    )
    assert event.tool_name == "read_file"
    assert event.success is True
    assert event.error is None


def test_session_event_frozen():
    event = SessionEvent(
        timestamp="2026-04-02T14:00:05",
        session_id="abc-123",
        prompt="Fix the bug",
        model="qwen3:14b",
        total_iterations=3,
        total_llm_calls=3,
        total_prompt_tokens=500,
        total_completion_tokens=200,
        total_tool_calls=4,
        tools_used=["read_file", "edit_file"],
        total_duration_ms=5200.0,
        estimated_cloud_cost={"claude-sonnet-4": 0.017},
        local_cost=0.0,
    )
    assert event.total_iterations == 3
    assert event.local_cost == 0.0
    assert "read_file" in event.tools_used
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd C:/Users/lokim/clawcal && python -m pytest tests/test_events.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement events**

`src/observability/events.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LlmCallEvent:
    timestamp: str
    session_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    tokens_per_second: float
    had_tool_calls: bool


@dataclass(frozen=True)
class ToolEvent:
    timestamp: str
    session_id: str
    tool_name: str
    parameters: dict
    duration_ms: float
    success: bool
    error: str | None
    result_length: int


@dataclass(frozen=True)
class SessionEvent:
    timestamp: str
    session_id: str
    prompt: str
    model: str
    total_iterations: int
    total_llm_calls: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tool_calls: int
    tools_used: list[str]
    total_duration_ms: float
    estimated_cloud_cost: dict[str, float]
    local_cost: float
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd C:/Users/lokim/clawcal && python -m pytest tests/test_events.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
cd C:/Users/lokim/clawcal && git add -A && git commit -m "feat: observability event dataclasses (LlmCallEvent, ToolEvent, SessionEvent)"
```

---

## Task 2: Cost estimator

**Files:**
- Create: `src/observability/cost_estimator.py`
- Create: `tests/test_cost_estimator.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_cost_estimator.py`:
```python
from __future__ import annotations

import json
import os
import tempfile

from src.observability.cost_estimator import CostEstimator


def test_estimate_default_prices():
    est = CostEstimator()
    result = est.estimate(prompt_tokens=1000, completion_tokens=500)
    # claude-sonnet-4: (1000/1M * 3.00) + (500/1M * 15.00) = 0.003 + 0.0075 = 0.0105
    assert abs(result["claude-sonnet-4"] - 0.0105) < 0.0001
    assert "claude-opus-4" in result
    assert "gpt-4o" in result


def test_estimate_zero_tokens():
    est = CostEstimator()
    result = est.estimate(prompt_tokens=0, completion_tokens=0)
    for cost in result.values():
        assert cost == 0.0


def test_add_model():
    est = CostEstimator()
    est.add_model("custom-model", input_price=1.0, output_price=2.0)
    result = est.estimate(prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert abs(result["custom-model"] - 3.0) < 0.0001


def test_load_prices_from_file():
    tmpdir = tempfile.mkdtemp()
    prices_file = os.path.join(tmpdir, "prices.json")
    custom_prices = {"my-model": {"input": 5.0, "output": 10.0}}
    with open(prices_file, "w") as f:
        json.dump(custom_prices, f)

    est = CostEstimator(prices_file=prices_file)
    result = est.estimate(prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert "my-model" in result
    assert abs(result["my-model"] - 15.0) < 0.0001
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:/Users/lokim/clawcal && python -m pytest tests/test_cost_estimator.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement cost estimator**

`src/observability/cost_estimator.py`:
```python
from __future__ import annotations

import json
import os


DEFAULT_PRICES: dict[str, dict[str, float]] = {
    "claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "claude-opus-4": {"input": 15.00, "output": 75.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}


class CostEstimator:
    def __init__(self, prices_file: str | None = None) -> None:
        if prices_file and os.path.exists(prices_file):
            with open(prices_file, encoding="utf-8") as f:
                self._prices: dict[str, dict[str, float]] = json.load(f)
        else:
            self._prices = dict(DEFAULT_PRICES)

    def estimate(self, prompt_tokens: int, completion_tokens: int) -> dict[str, float]:
        results: dict[str, float] = {}
        for model, prices in self._prices.items():
            cost = (prompt_tokens / 1_000_000 * prices["input"]) + (
                completion_tokens / 1_000_000 * prices["output"]
            )
            results[model] = round(cost, 6)
        return results

    def add_model(self, name: str, input_price: float, output_price: float) -> None:
        self._prices[name] = {"input": input_price, "output": output_price}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd C:/Users/lokim/clawcal && python -m pytest tests/test_cost_estimator.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
cd C:/Users/lokim/clawcal && git add -A && git commit -m "feat: cost estimator with configurable cloud pricing"
```

---

## Task 3: LlmUsage in LlmResponse

**Files:**
- Modify: `src/llm_client.py`
- Modify: `tests/test_llm_client.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_llm_client.py`:
```python
from src.llm_client import LlmUsage


def test_parse_response_with_usage():
    raw = {
        "message": {
            "role": "assistant",
            "content": "Hello!",
        },
        "prompt_eval_count": 100,
        "eval_count": 50,
        "total_duration": 1_500_000_000,  # 1.5s in nanoseconds
    }
    response = LlmClient.parse_response(raw)
    assert response.usage is not None
    assert response.usage.prompt_tokens == 100
    assert response.usage.completion_tokens == 50
    assert response.usage.total_tokens == 150
    assert abs(response.usage.latency_ms - 1500.0) < 0.1
    assert response.usage.tokens_per_second > 0


def test_parse_response_without_usage():
    raw = {
        "message": {
            "role": "assistant",
            "content": "Hello!",
        },
    }
    response = LlmClient.parse_response(raw)
    assert response.usage is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:/Users/lokim/clawcal && python -m pytest tests/test_llm_client.py::test_parse_response_with_usage -v
```

Expected: FAIL — `ImportError: cannot import name 'LlmUsage'`

- [ ] **Step 3: Add LlmUsage dataclass and modify parse_response**

Add after `LlmResponse` in `src/llm_client.py`:

```python
@dataclass(frozen=True)
class LlmUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    tokens_per_second: float
```

Modify `LlmResponse` to add usage field:

```python
@dataclass(frozen=True)
class LlmResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: LlmUsage | None = None
```

Modify `parse_response` — add usage extraction at the top of the method, before the `message` parsing, and pass `usage` to all three return statements:

```python
    @staticmethod
    def parse_response(raw: dict) -> LlmResponse:
        message = raw["message"]
        content = message.get("content", "")

        # Extract usage metrics from Ollama response
        usage = None
        prompt_eval = raw.get("prompt_eval_count")
        eval_count = raw.get("eval_count")
        total_duration = raw.get("total_duration")
        if prompt_eval is not None and eval_count is not None:
            total = prompt_eval + eval_count
            latency_ms = (total_duration / 1_000_000) if total_duration else 0.0
            tps = (eval_count / (latency_ms / 1000)) if latency_ms > 0 else 0.0
            usage = LlmUsage(
                prompt_tokens=prompt_eval,
                completion_tokens=eval_count,
                total_tokens=total,
                latency_ms=latency_ms,
                tokens_per_second=round(tps, 1),
            )

        # Mode 1: native tool calls
        native_calls = message.get("tool_calls")
        if native_calls:
            tool_calls = []
            for tc in native_calls:
                func = tc["function"]
                args = func.get("arguments", {})
                if isinstance(args, str):
                    args = json.loads(args)
                tool_calls.append(ToolCall(name=func["name"], arguments=args))
            return LlmResponse(text=content, tool_calls=tool_calls, usage=usage)
        # Mode 2: fallback XML parsing
        matches = _TOOL_CALL_RE.findall(content)
        if matches:
            tool_calls = []
            for m in matches:
                parsed = json.loads(m)
                tool_calls.append(
                    ToolCall(
                        name=parsed["name"],
                        arguments=parsed.get("arguments", {}),
                    )
                )
            text = _TOOL_CALL_RE.sub("", content).strip()
            return LlmResponse(text=text, tool_calls=tool_calls, usage=usage)
        # Mode 3: plain text
        return LlmResponse(text=content, usage=usage)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:/Users/lokim/clawcal && python -m pytest tests/test_llm_client.py -v
```

Expected: 6 passed (4 existing + 2 new)

- [ ] **Step 5: Run full suite for regression**

```bash
cd C:/Users/lokim/clawcal && python -m pytest -v
```

Expected: 32 passed (existing tests unaffected — usage defaults to None)

- [ ] **Step 6: Commit**

```bash
cd C:/Users/lokim/clawcal && git add -A && git commit -m "feat: extract LLM usage metrics (tokens, latency) from Ollama response"
```

---

## Task 4: Structured logger

**Files:**
- Create: `src/observability/logger.py`
- Create: `tests/test_logger.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_logger.py`:
```python
from __future__ import annotations

import json
import logging
import os
import tempfile

from src.observability.logger import setup_logging, log_llm_call, log_tool_call, log_session
from src.observability.events import LlmCallEvent, ToolEvent, SessionEvent


def test_setup_logging_creates_dir():
    tmpdir = os.path.join(tempfile.mkdtemp(), "logs")
    setup_logging(log_dir=tmpdir)
    assert os.path.isdir(tmpdir)


def test_log_llm_call_writes_jsonl(tmp_path):
    log_dir = str(tmp_path / "logs")
    setup_logging(log_dir=log_dir)

    event = LlmCallEvent(
        timestamp="2026-04-02T14:00:00",
        session_id="test-123",
        model="qwen3:14b",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        latency_ms=1200.0,
        tokens_per_second=41.7,
        had_tool_calls=False,
    )
    log_llm_call(event)

    logfile = os.path.join(log_dir, "clawcal.jsonl")
    assert os.path.exists(logfile)
    with open(logfile) as f:
        lines = f.readlines()
    last_line = json.loads(lines[-1])
    assert last_line["event_type"] == "llm_call"
    assert last_line["model"] == "qwen3:14b"
    assert last_line["total_tokens"] == 150


def test_log_tool_call_writes_jsonl(tmp_path):
    log_dir = str(tmp_path / "logs")
    setup_logging(log_dir=log_dir)

    event = ToolEvent(
        timestamp="2026-04-02T14:00:01",
        session_id="test-123",
        tool_name="bash",
        parameters={"command": "echo hi"},
        duration_ms=30.0,
        success=True,
        error=None,
        result_length=3,
    )
    log_tool_call(event)

    logfile = os.path.join(log_dir, "clawcal.jsonl")
    with open(logfile) as f:
        lines = f.readlines()
    last_line = json.loads(lines[-1])
    assert last_line["event_type"] == "tool_call"
    assert last_line["tool_name"] == "bash"


def test_log_session_writes_jsonl(tmp_path):
    log_dir = str(tmp_path / "logs")
    setup_logging(log_dir=log_dir)

    event = SessionEvent(
        timestamp="2026-04-02T14:00:05",
        session_id="test-123",
        prompt="Fix bug",
        model="qwen3:14b",
        total_iterations=2,
        total_llm_calls=2,
        total_prompt_tokens=300,
        total_completion_tokens=150,
        total_tool_calls=3,
        tools_used=["read_file", "bash"],
        total_duration_ms=4000.0,
        estimated_cloud_cost={"claude-sonnet-4": 0.01},
        local_cost=0.0,
    )
    log_session(event)

    logfile = os.path.join(log_dir, "clawcal.jsonl")
    with open(logfile) as f:
        lines = f.readlines()
    last_line = json.loads(lines[-1])
    assert last_line["event_type"] == "session"
    assert last_line["total_iterations"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:/Users/lokim/clawcal && python -m pytest tests/test_logger.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement logger**

`src/observability/logger.py`:
```python
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from logging.handlers import RotatingFileHandler

from src.observability.events import LlmCallEvent, ToolEvent, SessionEvent

_LOGGER_NAME = "clawcal"
_json_logger: logging.Logger | None = None
_console_logger: logging.Logger | None = None


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if hasattr(record, "event_data"):
            return json.dumps(record.event_data, default=str)
        return json.dumps({"message": record.getMessage()})


def setup_logging(
    log_dir: str = "~/.clawcal/logs",
    level: int = logging.INFO,
) -> None:
    global _json_logger, _console_logger

    log_dir = os.path.expanduser(log_dir)
    os.makedirs(log_dir, exist_ok=True)

    # JSON file logger
    _json_logger = logging.getLogger(f"{_LOGGER_NAME}.json")
    _json_logger.setLevel(level)
    _json_logger.handlers.clear()

    json_handler = RotatingFileHandler(
        os.path.join(log_dir, "clawcal.jsonl"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    json_handler.setFormatter(_JsonFormatter())
    _json_logger.addHandler(json_handler)

    # Console logger
    _console_logger = logging.getLogger(f"{_LOGGER_NAME}.console")
    _console_logger.setLevel(level)
    _console_logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    _console_logger.addHandler(console_handler)


def _log_event(event_type: str, data: dict, console_msg: str) -> None:
    data["event_type"] = event_type
    if _json_logger:
        record = _json_logger.makeRecord(
            _json_logger.name, logging.INFO, "", 0, "", (), None
        )
        record.event_data = data
        _json_logger.handle(record)
    if _console_logger:
        _console_logger.info(console_msg)


def log_llm_call(event: LlmCallEvent) -> None:
    data = asdict(event)
    msg = (
        f"LLM {event.model} | "
        f"{event.prompt_tokens} tok in, {event.completion_tokens} tok out | "
        f"{event.latency_ms / 1000:.1f}s"
    )
    _log_event("llm_call", data, msg)


def log_tool_call(event: ToolEvent) -> None:
    data = asdict(event)
    status = "OK" if event.success else f"FAIL: {event.error}"
    msg = f"TOOL {event.tool_name} | {event.duration_ms:.0f}ms | {status}"
    _log_event("tool_call", data, msg)


def log_session(event: SessionEvent) -> None:
    data = asdict(event)
    costs = ", ".join(f"{m} ${c:.4f}" for m, c in event.estimated_cloud_cost.items())
    msg = (
        f"SESSION COMPLETE | {event.total_iterations} iterations | "
        f"{event.total_prompt_tokens} tok in, {event.total_completion_tokens} tok out | "
        f"{event.total_duration_ms / 1000:.1f}s\n"
        f"  Local cost: $0.00 | Cloud equivalent: {costs}"
    )
    _log_event("session", data, msg)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:/Users/lokim/clawcal && python -m pytest tests/test_logger.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
cd C:/Users/lokim/clawcal && git add -A && git commit -m "feat: structured logging with JSON file + terminal output"
```

---

## Task 5: Metrics collector

**Files:**
- Create: `src/observability/collector.py`
- Create: `tests/test_collector.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_collector.py`:
```python
from __future__ import annotations

from src.observability.collector import MetricsCollector
from src.observability.events import LlmCallEvent, ToolEvent
from src.observability.cost_estimator import CostEstimator


def _make_llm_event(session_id: str, prompt_tokens: int = 100, completion_tokens: int = 50) -> LlmCallEvent:
    return LlmCallEvent(
        timestamp="2026-04-02T14:00:00",
        session_id=session_id,
        model="qwen3:14b",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        latency_ms=1000.0,
        tokens_per_second=50.0,
        had_tool_calls=True,
    )


def _make_tool_event(session_id: str, tool_name: str = "read_file") -> ToolEvent:
    return ToolEvent(
        timestamp="2026-04-02T14:00:01",
        session_id=session_id,
        tool_name=tool_name,
        parameters={},
        duration_ms=50.0,
        success=True,
        error=None,
        result_length=100,
    )


def test_collector_records_and_finalizes():
    collector = MetricsCollector(
        session_id="test-1",
        prompt="Fix the bug",
        model="qwen3:14b",
        cost_estimator=CostEstimator(),
    )
    collector.record_llm_call(_make_llm_event("test-1", 100, 50))
    collector.record_llm_call(_make_llm_event("test-1", 200, 100))
    collector.record_tool_call(_make_tool_event("test-1", "read_file"))
    collector.record_tool_call(_make_tool_event("test-1", "bash"))

    session = collector.finalize()
    assert session.session_id == "test-1"
    assert session.prompt == "Fix the bug"
    assert session.total_llm_calls == 2
    assert session.total_prompt_tokens == 300
    assert session.total_completion_tokens == 150
    assert session.total_tool_calls == 2
    assert set(session.tools_used) == {"read_file", "bash"}
    assert session.local_cost == 0.0
    assert "claude-sonnet-4" in session.estimated_cloud_cost


def test_collector_empty_session():
    collector = MetricsCollector(
        session_id="test-2",
        prompt="Hello",
        model="qwen3:14b",
        cost_estimator=CostEstimator(),
    )
    session = collector.finalize()
    assert session.total_llm_calls == 0
    assert session.total_tool_calls == 0
    assert session.total_prompt_tokens == 0


def test_collector_tracks_iterations():
    collector = MetricsCollector(
        session_id="test-3",
        prompt="Do something",
        model="qwen3:14b",
        cost_estimator=CostEstimator(),
    )
    collector.increment_iteration()
    collector.increment_iteration()
    collector.increment_iteration()
    session = collector.finalize()
    assert session.total_iterations == 3


def test_collector_exposes_events():
    collector = MetricsCollector(
        session_id="test-4",
        prompt="Test",
        model="qwen3:14b",
        cost_estimator=CostEstimator(),
    )
    llm_event = _make_llm_event("test-4")
    tool_event = _make_tool_event("test-4")
    collector.record_llm_call(llm_event)
    collector.record_tool_call(tool_event)
    assert collector.llm_events == [llm_event]
    assert collector.tool_events == [tool_event]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:/Users/lokim/clawcal && python -m pytest tests/test_collector.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement collector**

`src/observability/collector.py`:
```python
from __future__ import annotations

import time
from datetime import datetime, timezone

from src.observability.cost_estimator import CostEstimator
from src.observability.events import LlmCallEvent, SessionEvent, ToolEvent


class MetricsCollector:
    def __init__(
        self,
        session_id: str,
        prompt: str,
        model: str,
        cost_estimator: CostEstimator,
    ) -> None:
        self._session_id = session_id
        self._prompt = prompt
        self._model = model
        self._cost_estimator = cost_estimator
        self._start_time = time.monotonic()
        self._iterations = 0
        self._llm_events: list[LlmCallEvent] = []
        self._tool_events: list[ToolEvent] = []

    @property
    def llm_events(self) -> list[LlmCallEvent]:
        return list(self._llm_events)

    @property
    def tool_events(self) -> list[ToolEvent]:
        return list(self._tool_events)

    def record_llm_call(self, event: LlmCallEvent) -> None:
        self._llm_events.append(event)

    def record_tool_call(self, event: ToolEvent) -> None:
        self._tool_events.append(event)

    def increment_iteration(self) -> None:
        self._iterations += 1

    def finalize(self) -> SessionEvent:
        total_prompt = sum(e.prompt_tokens for e in self._llm_events)
        total_completion = sum(e.completion_tokens for e in self._llm_events)
        tools_used = sorted(set(e.tool_name for e in self._tool_events))
        total_duration = (time.monotonic() - self._start_time) * 1000

        cloud_cost = self._cost_estimator.estimate(total_prompt, total_completion)

        return SessionEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id=self._session_id,
            prompt=self._prompt,
            model=self._model,
            total_iterations=self._iterations,
            total_llm_calls=len(self._llm_events),
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_completion,
            total_tool_calls=len(self._tool_events),
            tools_used=tools_used,
            total_duration_ms=round(total_duration, 1),
            estimated_cloud_cost=cloud_cost,
            local_cost=0.0,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:/Users/lokim/clawcal && python -m pytest tests/test_collector.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
cd C:/Users/lokim/clawcal && git add -A && git commit -m "feat: metrics collector aggregates events into SessionEvent"
```

---

## Task 6: SQLite store

**Files:**
- Create: `src/observability/store.py`
- Create: `tests/test_store.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add aiosqlite dependency**

In `pyproject.toml`, change the dependencies list to:
```toml
dependencies = [
    "mcp>=1.0.0",
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
    "aiosqlite>=0.20.0",
]
```

Then install:
```bash
cd C:/Users/lokim/clawcal && pip install aiosqlite
```

- [ ] **Step 2: Write the failing tests**

`tests/test_store.py`:
```python
from __future__ import annotations

import os
import tempfile

import pytest

from src.observability.events import LlmCallEvent, ToolEvent, SessionEvent
from src.observability.store import MetricsStore


@pytest.fixture
async def store():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test_metrics.db")
    s = MetricsStore(db_path=db_path)
    await s.init()
    yield s
    await s.close()


def _make_session() -> tuple[SessionEvent, list[LlmCallEvent], list[ToolEvent]]:
    session = SessionEvent(
        timestamp="2026-04-02T14:00:05",
        session_id="store-test-1",
        prompt="Fix bug",
        model="qwen3:14b",
        total_iterations=2,
        total_llm_calls=2,
        total_prompt_tokens=300,
        total_completion_tokens=150,
        total_tool_calls=3,
        tools_used=["read_file", "bash"],
        total_duration_ms=4000.0,
        estimated_cloud_cost={"claude-sonnet-4": 0.01},
        local_cost=0.0,
    )
    llm_events = [
        LlmCallEvent(
            timestamp="2026-04-02T14:00:00",
            session_id="store-test-1",
            model="qwen3:14b",
            prompt_tokens=150,
            completion_tokens=75,
            total_tokens=225,
            latency_ms=1000.0,
            tokens_per_second=75.0,
            had_tool_calls=True,
        ),
        LlmCallEvent(
            timestamp="2026-04-02T14:00:02",
            session_id="store-test-1",
            model="qwen3:14b",
            prompt_tokens=150,
            completion_tokens=75,
            total_tokens=225,
            latency_ms=1000.0,
            tokens_per_second=75.0,
            had_tool_calls=False,
        ),
    ]
    tool_events = [
        ToolEvent(
            timestamp="2026-04-02T14:00:01",
            session_id="store-test-1",
            tool_name="read_file",
            parameters={"path": "/tmp/x"},
            duration_ms=30.0,
            success=True,
            error=None,
            result_length=100,
        ),
    ]
    return session, llm_events, tool_events


@pytest.mark.asyncio
async def test_save_and_get_usage_summary(store: MetricsStore):
    session, llm_events, tool_events = _make_session()
    await store.save_session(session, llm_events, tool_events)

    summary = await store.get_usage_summary(days=7)
    assert summary["total_sessions"] == 1
    assert summary["total_prompt_tokens"] == 300
    assert summary["total_completion_tokens"] == 150


@pytest.mark.asyncio
async def test_get_cost_savings(store: MetricsStore):
    session, llm_events, tool_events = _make_session()
    await store.save_session(session, llm_events, tool_events)

    savings = await store.get_cost_savings(days=7)
    assert "claude-sonnet-4" in savings
    assert savings["claude-sonnet-4"] > 0


@pytest.mark.asyncio
async def test_get_tool_stats(store: MetricsStore):
    session, llm_events, tool_events = _make_session()
    await store.save_session(session, llm_events, tool_events)

    stats = await store.get_tool_stats()
    assert len(stats) > 0
    assert stats[0]["tool_name"] == "read_file"
    assert stats[0]["call_count"] == 1
    assert stats[0]["success_rate"] == 1.0


@pytest.mark.asyncio
async def test_empty_store(store: MetricsStore):
    summary = await store.get_usage_summary(days=7)
    assert summary["total_sessions"] == 0
    assert summary["total_prompt_tokens"] == 0
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd C:/Users/lokim/clawcal && python -m pytest tests/test_store.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement SQLite store**

`src/observability/store.py`:
```python
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import aiosqlite

from src.observability.events import LlmCallEvent, SessionEvent, ToolEvent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    timestamp TEXT,
    prompt TEXT,
    model TEXT,
    total_iterations INTEGER,
    total_llm_calls INTEGER,
    total_prompt_tokens INTEGER,
    total_completion_tokens INTEGER,
    total_tool_calls INTEGER,
    tools_used TEXT,
    total_duration_ms REAL,
    estimated_cloud_cost TEXT,
    local_cost REAL
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    timestamp TEXT,
    model TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    latency_ms REAL,
    tokens_per_second REAL,
    had_tool_calls INTEGER
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    timestamp TEXT,
    tool_name TEXT,
    parameters TEXT,
    duration_ms REAL,
    success INTEGER,
    error TEXT,
    result_length INTEGER
);
"""


class MetricsStore:
    def __init__(self, db_path: str = "~/.clawcal/metrics.db") -> None:
        self._db_path = os.path.expanduser(db_path)
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.executescript(_SCHEMA)
        await self._db.commit()

    async def save_session(
        self,
        session: SessionEvent,
        llm_events: list[LlmCallEvent],
        tool_events: list[ToolEvent],
    ) -> None:
        assert self._db is not None
        await self._db.execute(
            "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                session.session_id,
                session.timestamp,
                session.prompt,
                session.model,
                session.total_iterations,
                session.total_llm_calls,
                session.total_prompt_tokens,
                session.total_completion_tokens,
                session.total_tool_calls,
                json.dumps(session.tools_used),
                session.total_duration_ms,
                json.dumps(session.estimated_cloud_cost),
                session.local_cost,
            ),
        )
        for e in llm_events:
            await self._db.execute(
                "INSERT INTO llm_calls (session_id, timestamp, model, prompt_tokens, "
                "completion_tokens, total_tokens, latency_ms, tokens_per_second, had_tool_calls) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    e.session_id, e.timestamp, e.model, e.prompt_tokens,
                    e.completion_tokens, e.total_tokens, e.latency_ms,
                    e.tokens_per_second, int(e.had_tool_calls),
                ),
            )
        for e in tool_events:
            await self._db.execute(
                "INSERT INTO tool_calls (session_id, timestamp, tool_name, parameters, "
                "duration_ms, success, error, result_length) VALUES (?,?,?,?,?,?,?,?)",
                (
                    e.session_id, e.timestamp, e.tool_name, json.dumps(e.parameters),
                    e.duration_ms, int(e.success), e.error, e.result_length,
                ),
            )
        await self._db.commit()

    async def get_usage_summary(self, days: int = 7) -> dict:
        assert self._db is not None
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cursor = await self._db.execute(
            "SELECT COUNT(*), COALESCE(SUM(total_prompt_tokens), 0), "
            "COALESCE(SUM(total_completion_tokens), 0), COALESCE(SUM(total_duration_ms), 0) "
            "FROM sessions WHERE timestamp >= ?",
            (since,),
        )
        row = await cursor.fetchone()
        return {
            "total_sessions": row[0],
            "total_prompt_tokens": row[1],
            "total_completion_tokens": row[2],
            "total_duration_ms": row[3],
        }

    async def get_cost_savings(self, days: int = 7) -> dict[str, float]:
        assert self._db is not None
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cursor = await self._db.execute(
            "SELECT estimated_cloud_cost FROM sessions WHERE timestamp >= ?",
            (since,),
        )
        totals: dict[str, float] = {}
        async for row in cursor:
            costs = json.loads(row[0])
            for model, cost in costs.items():
                totals[model] = totals.get(model, 0.0) + cost
        return totals

    async def get_tool_stats(self) -> list[dict]:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT tool_name, COUNT(*) as call_count, "
            "AVG(duration_ms) as avg_duration_ms, "
            "CAST(SUM(success) AS REAL) / COUNT(*) as success_rate "
            "FROM tool_calls GROUP BY tool_name ORDER BY call_count DESC"
        )
        rows = await cursor.fetchall()
        return [
            {
                "tool_name": r[0],
                "call_count": r[1],
                "avg_duration_ms": round(r[2], 1),
                "success_rate": round(r[3], 2),
            }
            for r in rows
        ]

    async def get_model_stats(self) -> list[dict]:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT model, COUNT(*) as call_count, "
            "SUM(prompt_tokens) as total_prompt, SUM(completion_tokens) as total_completion, "
            "AVG(tokens_per_second) as avg_tps "
            "FROM llm_calls GROUP BY model ORDER BY call_count DESC"
        )
        rows = await cursor.fetchall()
        return [
            {
                "model": r[0],
                "call_count": r[1],
                "total_prompt_tokens": r[2],
                "total_completion_tokens": r[3],
                "avg_tokens_per_second": round(r[4], 1),
            }
            for r in rows
        ]

    async def close(self) -> None:
        if self._db:
            await self._db.close()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd C:/Users/lokim/clawcal && python -m pytest tests/test_store.py -v
```

Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
cd C:/Users/lokim/clawcal && git add -A && git commit -m "feat: SQLite metrics store with usage, cost, and tool stats queries"
```

---

## Task 7: Wire observability into agent and server

**Files:**
- Modify: `src/agent.py`
- Modify: `src/server.py`
- Modify: `src/observability/__init__.py`
- Modify: `tests/test_agent.py`

- [ ] **Step 1: Update observability __init__.py with public exports**

`src/observability/__init__.py`:
```python
from src.observability.collector import MetricsCollector
from src.observability.cost_estimator import CostEstimator
from src.observability.events import LlmCallEvent, SessionEvent, ToolEvent
from src.observability.logger import log_llm_call, log_session, log_tool_call, setup_logging
from src.observability.store import MetricsStore
```

- [ ] **Step 2: Write the failing test for agent with collector**

Append to `tests/test_agent.py`:
```python
from src.observability.collector import MetricsCollector
from src.observability.cost_estimator import CostEstimator


@pytest.mark.asyncio
async def test_agent_with_collector():
    registry = ToolRegistry()
    registry.register(EchoTool())

    collector = MetricsCollector(
        session_id="agent-test-1",
        prompt="Echo yo",
        model="test-model",
        cost_estimator=CostEstimator(),
    )

    fake_llm = FakeLlmClient([
        LlmResponse(text="", tool_calls=[ToolCall(name="echo", arguments={"text": "yo"})]),
        LlmResponse(text="Done!"),
    ])
    agent = Agent(llm=fake_llm, registry=registry, collector=collector)

    result = await agent.run("Echo yo")
    assert "Done" in result

    session = collector.finalize()
    assert session.total_tool_calls == 1
    assert session.total_iterations == 2
    assert "echo" in session.tools_used
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd C:/Users/lokim/clawcal && python -m pytest tests/test_agent.py::test_agent_with_collector -v
```

Expected: FAIL — `TypeError: Agent.__init__() got an unexpected keyword argument 'collector'`

- [ ] **Step 4: Modify agent.py to accept and use collector**

Replace `src/agent.py` with:
```python
from __future__ import annotations

import time
from datetime import datetime, timezone

from src.llm_client import LlmClientProtocol
from src.tool_registry import ToolRegistry


SYSTEM_PROMPT = """You are a coding assistant. You have access to the following tools to help accomplish tasks.

When you need to use a tool, respond with a tool call. When you have enough information to answer, respond with plain text.

If the model does not support native tool calling, wrap tool calls in XML:
<tool_call>{"name": "tool_name", "arguments": {"param": "value"}}</tool_call>
"""


class Agent:
    def __init__(
        self,
        llm: LlmClientProtocol,
        registry: ToolRegistry,
        max_iterations: int = 20,
        system_prompt: str = SYSTEM_PROMPT,
        collector: object | None = None,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._max_iterations = max_iterations
        self._system_prompt = system_prompt
        self._collector = collector

    async def run(self, user_message: str) -> str:
        messages: list[dict] = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": user_message},
        ]
        tools = self._registry.get_definitions()

        for _ in range(self._max_iterations):
            if self._collector:
                self._collector.increment_iteration()

            response = await self._llm.chat(messages, tools=tools or None)

            # Record LLM call if collector present and response has usage
            if self._collector and response.usage:
                from src.observability.events import LlmCallEvent

                llm_event = LlmCallEvent(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    session_id=self._collector._session_id,
                    model=self._collector._model,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                    latency_ms=response.usage.latency_ms,
                    tokens_per_second=response.usage.tokens_per_second,
                    had_tool_calls=len(response.tool_calls) > 0,
                )
                self._collector.record_llm_call(llm_event)

                from src.observability.logger import log_llm_call
                log_llm_call(llm_event)

            if not response.tool_calls:
                return response.text

            # Append assistant message with tool calls
            messages.append({"role": "assistant", "content": response.text or ""})

            # Execute each tool call and append results
            for tc in response.tool_calls:
                start = time.monotonic()
                error_msg = None
                try:
                    result = await self._registry.execute(tc.name, tc.arguments)
                    success = True
                except Exception as e:
                    result = f"Error executing tool '{tc.name}': {e}"
                    error_msg = str(e)
                    success = False

                # Record tool call if collector present
                if self._collector:
                    from src.observability.events import ToolEvent
                    from src.observability.logger import log_tool_call

                    duration = (time.monotonic() - start) * 1000
                    tool_event = ToolEvent(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        session_id=self._collector._session_id,
                        tool_name=tc.name,
                        parameters=tc.arguments,
                        duration_ms=round(duration, 1),
                        success=success,
                        error=error_msg,
                        result_length=len(result),
                    )
                    self._collector.record_tool_call(tool_event)
                    log_tool_call(tool_event)

                messages.append({
                    "role": "tool",
                    "content": result,
                })

        return "Stopped: reached max iterations without a final answer."
```

- [ ] **Step 5: Run tests to verify all pass**

```bash
cd C:/Users/lokim/clawcal && python -m pytest -v
```

Expected: all tests pass (32 existing + new ones). Existing tests still work because `collector` defaults to `None`.

- [ ] **Step 6: Modify server.py to wire observability**

Replace `src/server.py` with:
```python
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Clawcal MCP Server")
    parser.add_argument("--model", default="qwen3:14b", help="Ollama model name")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama URL")
    args = parser.parse_args()
    asyncio.run(run_server(model=args.model, ollama_url=args.ollama_url))


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run full test suite**

```bash
cd C:/Users/lokim/clawcal && python -m pytest -v
```

Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
cd C:/Users/lokim/clawcal && git add -A && git commit -m "feat: wire observability into agent loop and MCP server"
```
