from __future__ import annotations

import asyncio
import os
import time
import uuid
from pathlib import Path
from typing import Any

from src.agent import Agent
from src.llm_client import LlmClientProtocol
from src.observability.collector import MetricsCollector
from src.observability.cost_estimator import CostEstimator
from src.tool_registry import ToolRegistry

SIGNALS_DIR = Path.home() / ".clawcal" / "signals"


class TaskManager:
    def __init__(
        self,
        llm: LlmClientProtocol,
        registry: ToolRegistry,
        cost_estimator: CostEstimator,
        model: str = "qwen3:14b",
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._cost_estimator = cost_estimator
        self._model = model
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        SIGNALS_DIR.mkdir(parents=True, exist_ok=True)

    async def submit(
        self,
        prompt: str,
        working_directory: str | None = None,
        max_iterations: int = 20,
    ) -> dict:
        task_id = uuid.uuid4().hex[:8]
        entry = {
            "task_id": task_id,
            "status": "running",
            "prompt": prompt,
            "result": None,
            "error": None,
            "started_at": time.monotonic(),
            "finished_at": None,
        }
        self._tasks[task_id] = entry
        asyncio_task = asyncio.create_task(
            self._run_agent(task_id, prompt, working_directory, max_iterations)
        )
        entry["_asyncio_task"] = asyncio_task
        return {"task_id": task_id, "status": "running"}

    async def _run_agent(
        self,
        task_id: str,
        prompt: str,
        working_directory: str | None,
        max_iterations: int,
    ) -> None:
        entry = self._tasks[task_id]

        async with self._lock:
            original_cwd = os.getcwd()
            if working_directory:
                os.chdir(working_directory)
            try:
                collector = MetricsCollector(
                    session_id=task_id,
                    prompt=prompt,
                    model=self._model,
                    cost_estimator=self._cost_estimator,
                )
                agent = Agent(
                    llm=self._llm,
                    registry=self._registry,
                    max_iterations=max_iterations,
                    collector=collector,
                )
                result = await agent.run(prompt)
                entry["status"] = "done"
                entry["result"] = result
                self._write_signal(task_id, "done", result)
            except Exception as e:
                entry["status"] = "error"
                entry["error"] = str(e)
                self._write_signal(task_id, "error", str(e))
            finally:
                entry["finished_at"] = time.monotonic()
                if working_directory:
                    os.chdir(original_cwd)

    def status(self, task_id: str) -> dict:
        entry = self._tasks.get(task_id)
        if entry is None:
            return {"task_id": task_id, "status": "unknown"}

        elapsed = (entry["finished_at"] or time.monotonic()) - entry["started_at"]
        return {
            "task_id": task_id,
            "status": entry["status"],
            "elapsed_seconds": round(elapsed, 1),
        }

    def result(self, task_id: str) -> dict:
        entry = self._tasks.get(task_id)
        if entry is None:
            return {"task_id": task_id, "status": "unknown"}

        if entry["status"] == "running":
            return {"task_id": task_id, "status": "running", "message": "Pas encore terminé"}

        elapsed = (entry["finished_at"] or time.monotonic()) - entry["started_at"]
        if entry["status"] == "error":
            return {
                "task_id": task_id,
                "status": "error",
                "error": entry["error"],
                "elapsed_seconds": round(elapsed, 1),
            }

        return {
            "task_id": task_id,
            "status": "done",
            "result": entry["result"],
            "elapsed_seconds": round(elapsed, 1),
        }

    def _write_signal(self, task_id: str, suffix: str, content: str) -> None:
        signal_path = SIGNALS_DIR / f"{task_id}.{suffix}"
        signal_path.write_text(content, encoding="utf-8")
