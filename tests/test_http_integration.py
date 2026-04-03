from __future__ import annotations

from starlette.testclient import TestClient

from src.server import create_http_app


def test_mcp_initialize_returns_session_id():
    """POST /mcp with initialize must return 200 and Mcp-Session-Id header."""
    app = create_http_app(model="qwen3:14b", ollama_url="http://localhost:11434")
    with TestClient(app) as client:
        resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert "mcp-session-id" in resp.headers


def test_mcp_tools_list_with_session():
    """After initialize, tools/list with the same session ID must work."""
    app = create_http_app(model="qwen3:14b", ollama_url="http://localhost:11434")
    with TestClient(app) as client:
        # Step 1: initialize
        init_resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )
        assert init_resp.status_code == 200
        session_id = init_resp.headers.get("mcp-session-id")
        assert session_id is not None

        # Step 2: Send initialized notification
        client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "Mcp-Session-Id": session_id,
            },
        )

        # Step 3: tools/list with session ID
        list_resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "Mcp-Session-Id": session_id,
            },
        )
        assert list_resp.status_code == 200

        # Verify response body contains tool definitions
        data = list_resp.json()
        assert data.get("jsonrpc") == "2.0"
        assert "result" in data
        tools = data["result"].get("tools", [])
        assert len(tools) > 0, "tools/list returned no tools"
        tool_names = {t["name"] for t in tools}
        assert "code_agent" in tool_names, f"code_agent not in tool names: {tool_names}"
        assert "read_file" in tool_names, f"read_file not in tool names: {tool_names}"


def test_health_endpoint():
    with TestClient(create_http_app()) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["server"] == "clawcal"
        assert data["status"] == "running"


def test_health_returns_expected_fields():
    with TestClient(create_http_app()) as client:
        data = client.get("/health").json()
        assert "server" in data
        assert "model" in data
        assert "ollama" in data
