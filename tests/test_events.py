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
