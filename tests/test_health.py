from __future__ import annotations

import httpx
from unittest.mock import AsyncMock, patch

from src.health import check_ollama


async def test_check_ollama_success():
    from unittest.mock import MagicMock
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"models": [{"name": "qwen3:14b"}]}
    mock_resp.raise_for_status = lambda: None

    with patch("src.health.httpx.AsyncClient") as mock_cls:
        instance = AsyncMock()
        instance.get.return_value = mock_resp
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = instance

        result = await check_ollama("http://localhost:11434")
        assert result["status"] == "ok"
        assert "qwen3:14b" in result["models"]


async def test_check_ollama_connection_error():
    with patch("src.health.httpx.AsyncClient") as mock_cls:
        instance = AsyncMock()
        instance.get.side_effect = httpx.ConnectError("refused")
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = instance

        result = await check_ollama("http://localhost:11434")
        assert result["status"] == "error"
        assert "refused" in result["error"]
