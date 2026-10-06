import pytest
import httpx
import respx
from agent import CodeMieCallerAgent, _extract_text

CM_BASE = "http://cm.local:8080"
CM_ID = "asst-abc"
CM_TOKEN = "tok-test"
ENDPOINT = f"{CM_BASE}/v1/a2a/assistants/{CM_ID}"


@respx.mock
async def test_call_success_task_variant():
    """Task-variant A2A response (result.task.artifacts) is handled."""
    respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json={
        "jsonrpc": "2.0", "id": "r1",
        "result": {"task": {"id": "t1", "contextId": "c1",
                             "artifacts": [{"artifactId": "a1", "parts": [{"text": "Hello from CodeMie!"}]}]}}
    }))
    agent = CodeMieCallerAgent(CM_BASE, CM_ID, CM_TOKEN)
    result = await agent.call("Say hello")
    assert result.ok is True
    assert result.response == "Hello from CodeMie!"
    assert len(result.trace) == 4
    assert result.trace[1].endpoint == ENDPOINT
    assert result.trace[1].direction == "outbound"
    assert result.trace[2].direction == "inbound"
    assert result.trace[2].latency_ms is not None


@respx.mock
async def test_call_success_message_variant():
    """Message-variant A2A response (result.message.parts) is handled."""
    respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json={
        "jsonrpc": "2.0", "id": "r1",
        "result": {"message": {"messageId": "m1", "role": "ROLE_AGENT",
                                "parts": [{"text": "Hi there!"}]}}
    }))
    agent = CodeMieCallerAgent(CM_BASE, CM_ID, CM_TOKEN)
    result = await agent.call("Say hello")
    assert result.ok is True
    assert result.response == "Hi there!"


@respx.mock
async def test_call_a2a_error_response():
    """A2A JSON-RPC error body produces ok=False with code in error string."""
    respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json={
        "jsonrpc": "2.0", "id": "r1",
        "error": {"code": -32001, "message": "Task not found"}
    }))
    agent = CodeMieCallerAgent(CM_BASE, CM_ID, CM_TOKEN)
    result = await agent.call("any message")
    assert result.ok is False
    assert "-32001" in result.error
    assert len(result.trace) == 4


@respx.mock
async def test_call_http_401():
    """HTTP 401 from CodeMie produces ok=False; does not raise."""
    respx.post(ENDPOINT).mock(return_value=httpx.Response(401, text="Unauthorized"))
    agent = CodeMieCallerAgent(CM_BASE, CM_ID, CM_TOKEN)
    result = await agent.call("any message")
    assert result.ok is False
    assert result.error is not None
    assert len(result.trace) == 4


@respx.mock
async def test_call_network_error():
    """Connection refused produces ok=False with error message; does not raise."""
    respx.post(ENDPOINT).mock(side_effect=httpx.ConnectError("connection refused"))
    agent = CodeMieCallerAgent(CM_BASE, CM_ID, CM_TOKEN)
    result = await agent.call("any message")
    assert result.ok is False
    assert "connection" in result.error.lower()
    assert len(result.trace) == 4


@respx.mock
async def test_a2a_version_header_sent():
    """A2A-Version: 1.0 and Authorization headers are present on the request."""
    route = respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json={
        "jsonrpc": "2.0", "id": "r1",
        "result": {"message": {"parts": [{"text": "ok"}]}}
    }))
    agent = CodeMieCallerAgent(CM_BASE, CM_ID, CM_TOKEN)
    await agent.call("test")
    req = route.calls[0].request
    assert req.headers["A2A-Version"] == "1.0"
    assert req.headers["Authorization"] == f"Bearer {CM_TOKEN}"


@respx.mock
async def test_trace_step2_payload_is_real_jsonrpc():
    """Step 2 payload contains the actual A2A JSON-RPC request body."""
    respx.post(ENDPOINT).mock(return_value=httpx.Response(200, json={
        "jsonrpc": "2.0", "id": "r1",
        "result": {"message": {"parts": [{"text": "ok"}]}}
    }))
    agent = CodeMieCallerAgent(CM_BASE, CM_ID, CM_TOKEN)
    result = await agent.call("hello")
    step2 = result.trace[1]
    assert step2.payload["jsonrpc"] == "2.0"
    assert step2.payload["method"] == "SendMessage"
    assert step2.payload["params"]["message"]["parts"][0]["text"] == "hello"


def test_extract_text_task_variant():
    response = {"result": {"task": {"artifacts": [{"parts": [{"text": "hello"}]}]}}}
    assert _extract_text(response) == "hello"


def test_extract_text_message_variant():
    response = {"result": {"message": {"parts": [{"text": "world"}]}}}
    assert _extract_text(response) == "world"


def test_extract_text_empty_falls_back_to_str():
    """Empty result returns a non-empty string (the serialised dict) rather than crashing."""
    response = {"result": {}}
    text = _extract_text(response)
    assert isinstance(text, str)
    assert len(text) > 0
