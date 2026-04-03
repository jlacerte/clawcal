from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from logging.handlers import RotatingFileHandler

from src.observability.events import LlmCallEvent, ToolEvent, SessionEvent

_LOGGER_NAME = "clawcal"
_json_logger: logging.Logger | None = None
_console_logger: logging.Logger | None = None


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if hasattr(record, "event_data"):
            return json.dumps(record.event_data, default=str)
        return json.dumps({"message": record.getMessage()})


def setup_logging(
    log_dir: str = "~/.clawcal/logs",
    level: int = logging.INFO,
    console: bool = True,
) -> None:
    global _json_logger, _console_logger

    log_dir = os.path.expanduser(log_dir)
    os.makedirs(log_dir, exist_ok=True)

    # JSON file logger
    _json_logger = logging.getLogger(f"{_LOGGER_NAME}.json")
    _json_logger.setLevel(level)
    _json_logger.handlers.clear()

    json_handler = RotatingFileHandler(
        os.path.join(log_dir, "clawcal.jsonl"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    json_handler.setFormatter(_JsonFormatter())
    _json_logger.addHandler(json_handler)

    # Console logger
    _console_logger = logging.getLogger(f"{_LOGGER_NAME}.console")
    _console_logger.setLevel(level)
    _console_logger.handlers.clear()

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
        _console_logger.addHandler(console_handler)


def _log_event(event_type: str, data: dict, console_msg: str) -> None:
    data["event_type"] = event_type
    if _json_logger:
        record = _json_logger.makeRecord(
            _json_logger.name, logging.INFO, "", 0, "", (), None
        )
        record.event_data = data
        _json_logger.handle(record)
    if _console_logger:
        _console_logger.info(console_msg)


def log_llm_call(event: LlmCallEvent) -> None:
    data = asdict(event)
    msg = (
        f"LLM {event.model} | "
        f"{event.prompt_tokens} tok in, {event.completion_tokens} tok out | "
        f"{event.latency_ms / 1000:.1f}s"
    )
    _log_event("llm_call", data, msg)


def log_tool_call(event: ToolEvent) -> None:
    data = asdict(event)
    status = "OK" if event.success else f"FAIL: {event.error}"
    msg = f"TOOL {event.tool_name} | {event.duration_ms:.0f}ms | {status}"
    _log_event("tool_call", data, msg)


def log_session(event: SessionEvent) -> None:
    data = asdict(event)
    costs = ", ".join(f"{m} ${c:.4f}" for m, c in event.estimated_cloud_cost.items())
    msg = (
        f"SESSION COMPLETE | {event.total_iterations} iterations | "
        f"{event.total_prompt_tokens} tok in, {event.total_completion_tokens} tok out | "
        f"{event.total_duration_ms / 1000:.1f}s\n"
        f"  Local cost: $0.00 | Cloud equivalent: {costs}"
    )
    _log_event("session", data, msg)
