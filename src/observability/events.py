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
