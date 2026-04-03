from __future__ import annotations

import asyncio
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


@pytest.mark.asyncio
async def test_status_running_then_done():
    llm = FakeLlmClient([LlmResponse(text="Done!")])
    registry = ToolRegistry()
    cost_est = CostEstimator()
    tm = TaskManager(llm=llm, registry=registry, cost_estimator=cost_est)

    submit_result = await tm.submit("Say hello")
    task_id = submit_result["task_id"]

    # Let the background task complete
    await asyncio.sleep(0.1)

    status = tm.status(task_id)
    assert status["status"] == "done"
    assert "elapsed_seconds" in status


@pytest.mark.asyncio
async def test_result_returns_output():
    llm = FakeLlmClient([LlmResponse(text="Hello world!")])
    registry = ToolRegistry()
    cost_est = CostEstimator()
    tm = TaskManager(llm=llm, registry=registry, cost_estimator=cost_est)

    submit_result = await tm.submit("Say hello")
    task_id = submit_result["task_id"]

    await asyncio.sleep(0.1)

    result = tm.result(task_id)
    assert result["status"] == "done"
    assert result["result"] == "Hello world!"


@pytest.mark.asyncio
async def test_status_unknown_task():
    llm = FakeLlmClient([])
    registry = ToolRegistry()
    cost_est = CostEstimator()
    tm = TaskManager(llm=llm, registry=registry, cost_estimator=cost_est)

    status = tm.status("nonexistent")
    assert status["status"] == "unknown"


@pytest.mark.asyncio
async def test_result_while_running():
    """result() on a running task returns status running."""
    import asyncio as _asyncio

    async def slow_chat(messages, tools=None):
        await _asyncio.sleep(1)
        return LlmResponse(text="Slow done")

    class SlowLlm:
        async def chat(self, messages, tools=None):
            return await slow_chat(messages, tools)
        async def close(self):
            pass

    registry = ToolRegistry()
    cost_est = CostEstimator()
    tm = TaskManager(llm=SlowLlm(), registry=registry, cost_estimator=cost_est)

    submit_result = await tm.submit("Slow task")
    task_id = submit_result["task_id"]

    result = tm.result(task_id)
    assert result["status"] == "running"


@pytest.mark.asyncio
async def test_signal_file_created_on_done(tmp_path, monkeypatch):
    monkeypatch.setattr("src.task_manager.SIGNALS_DIR", tmp_path)

    llm = FakeLlmClient([LlmResponse(text="Signal result")])
    registry = ToolRegistry()
    cost_est = CostEstimator()
    tm = TaskManager(llm=llm, registry=registry, cost_estimator=cost_est)

    submit_result = await tm.submit("Test signals")
    task_id = submit_result["task_id"]

    await asyncio.sleep(0.1)

    signal_file = tmp_path / f"{task_id}.done"
    assert signal_file.exists()
    assert signal_file.read_text() == "Signal result"


@pytest.mark.asyncio
async def test_signal_file_created_on_error(tmp_path, monkeypatch):
    monkeypatch.setattr("src.task_manager.SIGNALS_DIR", tmp_path)

    class ErrorLlm:
        async def chat(self, messages, tools=None):
            raise RuntimeError("LLM crashed")
        async def close(self):
            pass

    registry = ToolRegistry()
    cost_est = CostEstimator()
    tm = TaskManager(llm=ErrorLlm(), registry=registry, cost_estimator=cost_est)

    submit_result = await tm.submit("Will fail")
    task_id = submit_result["task_id"]

    await asyncio.sleep(0.1)

    signal_file = tmp_path / f"{task_id}.error"
    assert signal_file.exists()
    assert "LLM crashed" in signal_file.read_text()
