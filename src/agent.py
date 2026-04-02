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
                from src.observability.logger import log_llm_call

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
