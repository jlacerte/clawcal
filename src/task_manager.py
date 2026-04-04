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
from src.observability.logger import log_session
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
        self._prune_old_signals()

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

    async def run_sync(
        self,
        prompt: str,
        working_directory: str | None = None,
        max_iterations: int = 20,
    ) -> str:
        """Run agent synchronously under the shared lock. Used by code_agent tool."""
        async with self._lock:
            original_cwd = os.getcwd()
            if working_directory:
                os.chdir(working_directory)
            collector = None
            try:
                collector = MetricsCollector(
                    session_id=uuid.uuid4().hex[:8],
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
                return result
            finally:
                if working_directory:
                    os.chdir(original_cwd)
                if collector:
                    session_event = collector.finalize()
                    log_session(session_event)

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
            collector = None
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
                entry["_asyncio_task"] = None
                if working_directory:
                    os.chdir(original_cwd)
                if collector:
                    session_event = collector.finalize()
                    log_session(session_event)
                    entry["session_event"] = session_event

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

        self._cleanup_signal(task_id)

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

    def _prune_old_signals(self, max_age_hours: int = 24) -> None:
        max_age_seconds = max_age_hours * 3600
        now = time.time()
        for path in SIGNALS_DIR.iterdir():
            try:
                if path.suffix in (".done", ".error"):
                    age = now - path.stat().st_mtime
                    if age > max_age_seconds:
                        path.unlink(missing_ok=True)
            except OSError:
                pass

    def _cleanup_signal(self, task_id: str) -> None:
        for suffix in ("done", "error"):
            path = SIGNALS_DIR / f"{task_id}.{suffix}"
            path.unlink(missing_ok=True)

    def _write_signal(self, task_id: str, suffix: str, content: str) -> None:
        signal_path = SIGNALS_DIR / f"{task_id}.{suffix}"
        signal_path.write_text(content, encoding="utf-8")
