from __future__ import annotations

import httpx


async def check_ollama(ollama_url: str, timeout: float = 5.0) -> dict:
    """Check Ollama connectivity. Returns a status dict."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{ollama_url.rstrip('/')}/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            return {"status": "ok", "models": models}
    except (httpx.HTTPError, httpx.ConnectError, Exception) as exc:
        return {"status": "error", "error": str(exc)}
