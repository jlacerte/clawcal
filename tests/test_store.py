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
