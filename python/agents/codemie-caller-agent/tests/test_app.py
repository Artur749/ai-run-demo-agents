from unittest.mock import AsyncMock, MagicMock
from starlette.testclient import TestClient
from agent import CallResult, TraceStep, CodeMieCallerAgent
from app import create_app

CM_BASE = "http://cm.local:8080"
CM_ID = "asst-abc"


def _sample_trace():
    return [
        TraceStep(1, "UI → codemie-caller-agent", "outbound", "HTTP POST /demo/chat", {"message": "hi"}),
        TraceStep(2, "codemie-caller-agent → CodeMie (A2A SendMessage)", "outbound",
                  "A2A JSON-RPC 1.0", {"jsonrpc": "2.0"}, endpoint=f"{CM_BASE}/v1/a2a/assistants/{CM_ID}"),
        TraceStep(3, "CodeMie → codemie-caller-agent", "inbound",
                  "A2A JSON-RPC 1.0", {"jsonrpc": "2.0", "result": {}}, latency_ms=88),
        TraceStep(4, "codemie-caller-agent → UI", "inbound", "HTTP response",
                  {"ok": True, "response": "Hi!"}),
    ]


def make_mock_agent(ok=True, response="Hi!", error=None):
    agent = MagicMock(spec=CodeMieCallerAgent)
    agent.call = AsyncMock(return_value=CallResult(
        ok=ok, response=response, trace=_sample_trace(), error=error
    ))
    return agent


def test_demo_chat_success():
    app = create_app(make_mock_agent(), "localhost", 11000)
    with TestClient(app) as client:
        resp = client.post("/demo/chat", json={"message": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["response"] == "Hi!"
    assert len(data["trace"]) == 4
    assert data["trace"][2]["latency_ms"] == 88


def test_demo_chat_cors_header():
    app = create_app(make_mock_agent(), "localhost", 11000)
    with TestClient(app) as client:
        resp = client.post("/demo/chat", json={"message": "hi"})
    assert resp.headers.get("access-control-allow-origin") == "*"


def test_demo_chat_options_preflight():
    app = create_app(make_mock_agent(), "localhost", 11000)
    with TestClient(app) as client:
        resp = client.options("/demo/chat", headers={"Origin": "http://localhost:8090"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "*"
    assert "POST" in resp.headers.get("access-control-allow-methods", "")


def test_demo_chat_missing_message_field():
    app = create_app(make_mock_agent(), "localhost", 11000)
    with TestClient(app) as client:
        resp = client.post("/demo/chat", json={})
    assert resp.status_code == 400
    assert resp.json()["ok"] is False


def test_demo_chat_whitespace_only_message():
    app = create_app(make_mock_agent(), "localhost", 11000)
    with TestClient(app) as client:
        resp = client.post("/demo/chat", json={"message": "   "})
    assert resp.status_code == 400
    assert resp.json()["ok"] is False


def test_demo_chat_invalid_json_body():
    app = create_app(make_mock_agent(), "localhost", 11000)
    with TestClient(app) as client:
        resp = client.post("/demo/chat", content=b"not json",
                           headers={"Content-Type": "application/json"})
    assert resp.status_code == 400
    assert resp.json()["ok"] is False


def test_demo_chat_agent_error_propagated():
    app = create_app(
        make_mock_agent(ok=False, error="A2A error -32001: Task not found"),
        "localhost", 11000,
    )
    with TestClient(app) as client:
        resp = client.post("/demo/chat", json={"message": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert "error" in data
    assert "-32001" in data["error"]


def test_agent_card_endpoint():
    app = create_app(make_mock_agent(), "localhost", 11000)
    with TestClient(app) as client:
        resp = client.get("/.well-known/agent-card.json")
    assert resp.status_code == 200
    card = resp.json()
    assert card["name"] == "CodeMie Caller Agent"
    assert card["capabilities"]["streaming"] is False


def test_a2a_sendmessage_returns_jsonrpc():
    """POST / with A2A-Version header returns a JSON-RPC 2.0 response."""
    app = create_app(make_mock_agent(), "localhost", 11000)
    with TestClient(app) as client:
        resp = client.post(
            "/",
            json={
                "jsonrpc": "2.0", "id": "t1", "method": "SendMessage",
                "params": {"message": {"messageId": "m1", "role": "ROLE_USER",
                                        "parts": [{"text": "hello"}]}}
            },
            headers={"A2A-Version": "1.0", "Content-Type": "application/json"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["jsonrpc"] == "2.0"
    assert "result" in data or "error" in data
