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
