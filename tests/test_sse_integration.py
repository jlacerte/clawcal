from __future__ import annotations

from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.testclient import TestClient
from mcp.server.sse import SseServerTransport

from src.server import create_server


def _make_app():
    """Build the Starlette app without uvicorn for testing."""
    server = create_server()
    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())
        return Response()

    async def handle_health(request):
        return JSONResponse({
            "server": "clawcal",
            "status": "running",
            "model": "qwen3:14b",
            "ollama": {"status": "ok", "models": []},
        })

    return Starlette(
        routes=[
            Route("/health", handle_health, methods=["GET"]),
            Route("/sse", handle_sse, methods=["GET"]),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )


def test_health_endpoint():
    app = _make_app()
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["server"] == "clawcal"
    assert data["status"] == "running"


def test_health_returns_expected_fields():
    app = _make_app()
    client = TestClient(app)
    data = client.get("/health").json()
    assert "server" in data
    assert "model" in data
    assert "ollama" in data
    assert data["ollama"]["status"] == "ok"
