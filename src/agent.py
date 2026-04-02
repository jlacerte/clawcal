from __future__ import annotations

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
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._max_iterations = max_iterations
        self._system_prompt = system_prompt

    async def run(self, user_message: str) -> str:
        messages: list[dict] = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": user_message},
        ]
        tools = self._registry.get_definitions()

        for _ in range(self._max_iterations):
            response = await self._llm.chat(messages, tools=tools or None)

            if not response.tool_calls:
                return response.text

            # Append assistant message with tool calls
            messages.append({"role": "assistant", "content": response.text or ""})

            # Execute each tool call and append results
            for tc in response.tool_calls:
                try:
                    result = await self._registry.execute(tc.name, tc.arguments)
                except Exception as e:
                    result = f"Error executing tool '{tc.name}': {e}"

                messages.append({
                    "role": "tool",
                    "content": result,
                })

        return "Stopped: reached max iterations without a final answer."
