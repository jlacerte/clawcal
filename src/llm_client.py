from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import httpx


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict


@dataclass(frozen=True)
class LlmResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)


_TOOL_CALL_RE = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)


@runtime_checkable
class LlmClientProtocol(Protocol):
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LlmResponse: ...

    async def close(self) -> None: ...


class LlmClient:
    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "qwen3:14b",
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> None:
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._http = httpx.AsyncClient(timeout=300.0)

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LlmResponse:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": self.max_tokens,
                "temperature": self.temperature,
            },
        }
        if tools:
            payload["tools"] = tools
        resp = await self._http.post(
            f"{self.ollama_url}/api/chat",
            json=payload,
        )
        resp.raise_for_status()
        return self.parse_response(resp.json())

    @staticmethod
    def parse_response(raw: dict) -> LlmResponse:
        message = raw["message"]
        content = message.get("content", "")
        # Mode 1: native tool calls
        native_calls = message.get("tool_calls")
        if native_calls:
            tool_calls = []
            for tc in native_calls:
                func = tc["function"]
                args = func.get("arguments", {})
                if isinstance(args, str):
                    args = json.loads(args)
                tool_calls.append(ToolCall(name=func["name"], arguments=args))
            return LlmResponse(text=content, tool_calls=tool_calls)
        # Mode 2: fallback XML parsing
        matches = _TOOL_CALL_RE.findall(content)
        if matches:
            tool_calls = []
            for m in matches:
                parsed = json.loads(m)
                tool_calls.append(
                    ToolCall(
                        name=parsed["name"],
                        arguments=parsed.get("arguments", {}),
                    )
                )
            text = _TOOL_CALL_RE.sub("", content).strip()
            return LlmResponse(text=text, tool_calls=tool_calls)
        # Mode 3: plain text
        return LlmResponse(text=content)

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> LlmClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
