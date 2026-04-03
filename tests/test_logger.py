from __future__ import annotations

import json
import logging
import os
import tempfile

from src.observability.logger import setup_logging, log_llm_call, log_tool_call, log_session
from src.observability.events import LlmCallEvent, ToolEvent, SessionEvent


def test_setup_logging_creates_dir():
    tmpdir = os.path.join(tempfile.mkdtemp(), "logs")
    setup_logging(log_dir=tmpdir)
    assert os.path.isdir(tmpdir)


def test_log_llm_call_writes_jsonl(tmp_path):
    log_dir = str(tmp_path / "logs")
    setup_logging(log_dir=log_dir)

    event = LlmCallEvent(
        timestamp="2026-04-02T14:00:00",
        session_id="test-123",
        model="qwen3:14b",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        latency_ms=1200.0,
        tokens_per_second=41.7,
        had_tool_calls=False,
    )
    log_llm_call(event)

    logfile = os.path.join(log_dir, "clawcal.jsonl")
    assert os.path.exists(logfile)
    with open(logfile) as f:
        lines = f.readlines()
    last_line = json.loads(lines[-1])
    assert last_line["event_type"] == "llm_call"
    assert last_line["model"] == "qwen3:14b"
    assert last_line["total_tokens"] == 150


def test_log_tool_call_writes_jsonl(tmp_path):
    log_dir = str(tmp_path / "logs")
    setup_logging(log_dir=log_dir)

    event = ToolEvent(
        timestamp="2026-04-02T14:00:01",
        session_id="test-123",
        tool_name="bash",
        parameters={"command": "echo hi"},
        duration_ms=30.0,
        success=True,
        error=None,
        result_length=3,
    )
    log_tool_call(event)

    logfile = os.path.join(log_dir, "clawcal.jsonl")
    with open(logfile) as f:
        lines = f.readlines()
    last_line = json.loads(lines[-1])
    assert last_line["event_type"] == "tool_call"
    assert last_line["tool_name"] == "bash"


def test_log_session_writes_jsonl(tmp_path):
    log_dir = str(tmp_path / "logs")
    setup_logging(log_dir=log_dir)

    event = SessionEvent(
        timestamp="2026-04-02T14:00:05",
        session_id="test-123",
        prompt="Fix bug",
        model="qwen3:14b",
        total_iterations=2,
        total_llm_calls=2,
        total_prompt_tokens=300,
        total_completion_tokens=150,
        total_tool_calls=3,
        tools_used=["read_file", "bash"],
        total_duration_ms=4000.0,
        estimated_cloud_cost={"claude-sonnet-4": 0.01},
        local_cost=0.0,
    )
    log_session(event)

    logfile = os.path.join(log_dir, "clawcal.jsonl")
    with open(logfile) as f:
        lines = f.readlines()
    last_line = json.loads(lines[-1])
    assert last_line["event_type"] == "session"
    assert last_line["total_iterations"] == 2


def test_setup_logging_no_console(tmp_path):
    """Console handler is omitted when console=False."""
    log_dir = str(tmp_path / "logs")
    setup_logging(log_dir=log_dir, console=False)
    console_logger = logging.getLogger("clawcal.console")
    assert len(console_logger.handlers) == 0
