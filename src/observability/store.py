from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import aiosqlite

from src.observability.events import LlmCallEvent, SessionEvent, ToolEvent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    timestamp TEXT,
    prompt TEXT,
    model TEXT,
    total_iterations INTEGER,
    total_llm_calls INTEGER,
    total_prompt_tokens INTEGER,
    total_completion_tokens INTEGER,
    total_tool_calls INTEGER,
    tools_used TEXT,
    total_duration_ms REAL,
    estimated_cloud_cost TEXT,
    local_cost REAL
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    timestamp TEXT,
    model TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    latency_ms REAL,
    tokens_per_second REAL,
    had_tool_calls INTEGER
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    timestamp TEXT,
    tool_name TEXT,
    parameters TEXT,
    duration_ms REAL,
    success INTEGER,
    error TEXT,
    result_length INTEGER
);
"""


class MetricsStore:
    def __init__(self, db_path: str = "~/.clawcal/metrics.db") -> None:
        self._db_path = os.path.expanduser(db_path)
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.executescript(_SCHEMA)
        await self._db.commit()

    async def save_session(
        self,
        session: SessionEvent,
        llm_events: list[LlmCallEvent],
        tool_events: list[ToolEvent],
    ) -> None:
        assert self._db is not None
        await self._db.execute(
            "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                session.session_id,
                session.timestamp,
                session.prompt,
                session.model,
                session.total_iterations,
                session.total_llm_calls,
                session.total_prompt_tokens,
                session.total_completion_tokens,
                session.total_tool_calls,
                json.dumps(session.tools_used),
                session.total_duration_ms,
                json.dumps(session.estimated_cloud_cost),
                session.local_cost,
            ),
        )
        for e in llm_events:
            await self._db.execute(
                "INSERT INTO llm_calls (session_id, timestamp, model, prompt_tokens, "
                "completion_tokens, total_tokens, latency_ms, tokens_per_second, had_tool_calls) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    e.session_id, e.timestamp, e.model, e.prompt_tokens,
                    e.completion_tokens, e.total_tokens, e.latency_ms,
                    e.tokens_per_second, int(e.had_tool_calls),
                ),
            )
        for e in tool_events:
            await self._db.execute(
                "INSERT INTO tool_calls (session_id, timestamp, tool_name, parameters, "
                "duration_ms, success, error, result_length) VALUES (?,?,?,?,?,?,?,?)",
                (
                    e.session_id, e.timestamp, e.tool_name, json.dumps(e.parameters),
                    e.duration_ms, int(e.success), e.error, e.result_length,
                ),
            )
        await self._db.commit()

    async def get_usage_summary(self, days: int = 7) -> dict:
        assert self._db is not None
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cursor = await self._db.execute(
            "SELECT COUNT(*), COALESCE(SUM(total_prompt_tokens), 0), "
            "COALESCE(SUM(total_completion_tokens), 0), COALESCE(SUM(total_duration_ms), 0) "
            "FROM sessions WHERE timestamp >= ?",
            (since,),
        )
        row = await cursor.fetchone()
        return {
            "total_sessions": row[0],
            "total_prompt_tokens": row[1],
            "total_completion_tokens": row[2],
            "total_duration_ms": row[3],
        }

    async def get_cost_savings(self, days: int = 7) -> dict[str, float]:
        assert self._db is not None
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cursor = await self._db.execute(
            "SELECT estimated_cloud_cost FROM sessions WHERE timestamp >= ?",
            (since,),
        )
        totals: dict[str, float] = {}
        async for row in cursor:
            costs = json.loads(row[0])
            for model, cost in costs.items():
                totals[model] = totals.get(model, 0.0) + cost
        return totals

    async def get_tool_stats(self) -> list[dict]:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT tool_name, COUNT(*) as call_count, "
            "AVG(duration_ms) as avg_duration_ms, "
            "CAST(SUM(success) AS REAL) / COUNT(*) as success_rate "
            "FROM tool_calls GROUP BY tool_name ORDER BY call_count DESC"
        )
        rows = await cursor.fetchall()
        return [
            {
                "tool_name": r[0],
                "call_count": r[1],
                "avg_duration_ms": round(r[2], 1),
                "success_rate": round(r[3], 2),
            }
            for r in rows
        ]

    async def get_model_stats(self) -> list[dict]:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT model, COUNT(*) as call_count, "
            "SUM(prompt_tokens) as total_prompt, SUM(completion_tokens) as total_completion, "
            "AVG(tokens_per_second) as avg_tps "
            "FROM llm_calls GROUP BY model ORDER BY call_count DESC"
        )
        rows = await cursor.fetchall()
        return [
            {
                "model": r[0],
                "call_count": r[1],
                "total_prompt_tokens": r[2],
                "total_completion_tokens": r[3],
                "avg_tokens_per_second": round(r[4], 1),
            }
            for r in rows
        ]

    async def close(self) -> None:
        if self._db:
            await self._db.close()
