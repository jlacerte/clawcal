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
