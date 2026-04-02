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
