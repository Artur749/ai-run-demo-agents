# A2A Multi-Hop Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `codemie-caller-agent` (a real A2A agent that calls CodeMie) and a browser chat UI that shows the 4-hop wire trace, demonstrating `UI → agent → CodeMie → agent → UI`.

**Architecture:** A new uv workspace member `codemie-caller-agent` (port 11000) exposes both a standard A2A endpoint (`POST /`) and a demo REST endpoint (`POST /demo/chat`). The demo endpoint calls CodeMie via raw `httpx` (capturing verbatim JSON-RPC payloads for the trace) and returns structured trace data. A pure HTML/JS/CSS chat UI served by `python -m http.server` calls `/demo/chat` and renders the 4-hop trace alongside the chat reply.

**Tech Stack:** Python 3.13, uv, a2a-sdk ≥ 1.1.5, httpx, starlette, uvicorn, click, python-dotenv; pytest + pytest-asyncio + respx for tests; vanilla HTML/CSS/JS (no npm).

**Spec:** `docs/superpowers/specs/2026-10-06-a2a-multi-hop-demo-design.md`

## Global Constraints

- Python ≥ 3.13 (matches workspace `.python-version`)
- `a2a-sdk[http-server] ≥ 1.1.5` — same constraint as other agents
- No `langchain-*` dependencies — agent makes no local LLM calls
- CORS (`Access-Control-Allow-Origin: *`) on `/demo/chat` and its `OPTIONS` preflight only — not on the A2A endpoint
- `A2A-Version: 1.0` and `Authorization: Bearer <token>` headers sent on every CodeMie call
- Agent card `name` must be exactly `"CodeMie Caller Agent"`, `capabilities.streaming` must be `false`
- Trace always has exactly 4 steps in the order: UI→agent, agent→CodeMie, CodeMie→agent, agent→UI
- On any error, `ok: false` and `error` key present; trace contains all steps that completed before the failure plus a step for the failure itself
- Port default: 11000; host default: `localhost`
- Dockerfile mirrors `text-insights-agent` pattern exactly (build-context `ai-run-agents`)

## Review Focus

- **HTTP 401/403 from CodeMie** — `ok: false` with a useful error message (not a Python stack trace); trace has 4 steps including the failed step 3
- **A2A error response** (`{"jsonrpc":"2.0","error":{"code":-32001,...}}`) — treated as `ok: false`; `error` field contains the code and message
- **Network timeout/connection refused** — `ok: false`; agent does not crash; step 3 records the exception string
- **`/demo/chat` with empty or missing `message` field** — returns HTTP 400 with `{"ok": false, "error": "..."}` before calling CodeMie
- **CodeMie response with no extractable text** (empty artifacts, empty parts) — `_extract_text` returns the raw `result` dict as a string rather than crashing

---

## File Map

```
ai-run-demo-agents/python/
  pyproject.toml                                    MODIFY  add workspace member
  agents/
    codemie-caller-agent/
      __init__.py                                   CREATE  empty marker
      agent.py                                      CREATE  CodeMieCallerAgent, TraceStep, CallResult, _extract_text
      app.py                                        CREATE  create_app(), CodeMieCallerExecutor, demo_chat handler
      __main__.py                                   CREATE  click CLI, _build_agent()
      pyproject.toml                                CREATE  deps + pytest config
      Dockerfile                                    CREATE  mirrors text-insights-agent
      tests/
        __init__.py                                 CREATE  empty marker
        test_agent.py                               CREATE  unit tests for agent.py
        test_app.py                                 CREATE  endpoint tests for app.py

ui-demo-agents/
  chat-ui/
    index.html                                      CREATE  two-panel layout
    style.css                                       CREATE  dark theme, trace cards
    app.js                                          CREATE  fetch, trace rendering, presets
  demo.env.example                                  CREATE  CM_BASE_URL, CM_ASSISTANT_ID, CM_AUTH_TOKEN
  README.md                                         CREATE  demo guide (8 sections)
```

---

## Task 1: Scaffold agent project

**Files:**
- Create: `ai-run-demo-agents/python/agents/codemie-caller-agent/pyproject.toml`
- Create: `ai-run-demo-agents/python/agents/codemie-caller-agent/__init__.py`
- Create: `ai-run-demo-agents/python/agents/codemie-caller-agent/tests/__init__.py`
- Modify: `ai-run-demo-agents/python/pyproject.toml:41` (add workspace member)

**Interfaces:**
- Produces: uv workspace member resolvable by `uv sync` from the `python/` root

- [ ] **Step 1: Create `codemie-caller-agent/pyproject.toml`**

```toml
[project]
name = "codemie-caller-agent"
version = "0.1.0"
description = "Demo A2A agent that forwards messages to a CodeMie assistant and returns a wire trace"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "a2a-sdk[http-server]>=1.1.5",
    "click>=8.1.8",
    "httpx>=0.28.1",
    "python-dotenv>=1.1.0",
    "starlette>=0.46.1",
    "uvicorn>=0.34.0",
]

[tool.hatch.build.targets.wheel]
packages = ["."]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
    "respx>=0.22",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create empty `__init__.py` and `tests/__init__.py`**

Both files are empty. Create them so Python treats the directories as packages and pytest can collect `tests/`.

- [ ] **Step 3: Add workspace member in `python/pyproject.toml`**

In the existing `[tool.uv.workspace]` section, add `"agents/codemie-caller-agent"` to the `members` list. The section after the change:

```toml
[tool.uv.workspace]
members = [
    "agents/currency_converter",
    "agents/fun-with-rick",
    "agents/financial-agent",
    "agents/research-agent",
    "agents/text-insights-agent",
    "agents/howto-guide-agent",
    "agents/codemie-caller-agent",
]
```

- [ ] **Step 4: Sync and lock**

Run from `ai-run-demo-agents/python/`:
```bash
uv sync
```

Expected: resolves without errors and updates `uv.lock`.

- [ ] **Step 5: Commit**

```bash
git add ai-run-demo-agents/python/pyproject.toml \
        ai-run-demo-agents/python/uv.lock \
        ai-run-demo-agents/python/agents/codemie-caller-agent/
git commit -m "feat(codemie-caller-agent): scaffold uv workspace member"
```

---

## Task 2: Implement `agent.py` — core CodeMie caller

**Files:**
- Create: `ai-run-demo-agents/python/agents/codemie-caller-agent/agent.py`
- Create: `ai-run-demo-agents/python/agents/codemie-caller-agent/tests/test_agent.py`

**Interfaces:**
- Produces:
  - `TraceStep(step, label, direction, protocol, payload, endpoint=None, latency_ms=None)` — dataclass
  - `CallResult(ok, response, trace, error=None)` — dataclass
  - `CodeMieCallerAgent(cm_base_url, cm_assistant_id, cm_auth_token)` — class
  - `async CodeMieCallerAgent.call(message: str) -> CallResult`
  - `_extract_text(response_json: dict) -> str` — module-level helper

- [ ] **Step 1: Write failing tests in `tests/test_agent.py`**

```python
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
```

- [ ] **Step 2: Run tests — confirm they all fail**

From `ai-run-demo-agents/python/agents/codemie-caller-agent/`:
```bash
uv run pytest tests/test_agent.py -v
```
Expected: `ModuleNotFoundError: No module named 'agent'`

- [ ] **Step 3: Implement `agent.py`**

```python
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class TraceStep:
    step: int
    label: str
    direction: str
    protocol: str
    payload: dict[str, Any]
    endpoint: str | None = None
    latency_ms: int | None = None


@dataclass
class CallResult:
    ok: bool
    response: str
    trace: list[TraceStep]
    error: str | None = None


class CodeMieCallerAgent:
    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self, cm_base_url: str, cm_assistant_id: str, cm_auth_token: str) -> None:
        self._endpoint = f"{cm_base_url.rstrip('/')}/v1/a2a/assistants/{cm_assistant_id}"
        self._auth_token = cm_auth_token

    async def call(self, message: str) -> CallResult:
        rpc_id = uuid.uuid4().hex
        message_id = uuid.uuid4().hex
        request_payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": "SendMessage",
            "params": {
                "message": {
                    "messageId": message_id,
                    "role": "ROLE_USER",
                    "parts": [{"text": message}],
                }
            },
        }
        trace: list[TraceStep] = [
            TraceStep(
                step=1,
                label="UI → codemie-caller-agent",
                direction="outbound",
                protocol="HTTP POST /demo/chat",
                payload={"message": message},
            ),
            TraceStep(
                step=2,
                label="codemie-caller-agent → CodeMie (A2A SendMessage)",
                direction="outbound",
                protocol="A2A JSON-RPC 1.0",
                endpoint=self._endpoint,
                payload=request_payload,
            ),
        ]

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    self._endpoint,
                    json=request_payload,
                    headers={
                        "A2A-Version": "1.0",
                        "Authorization": f"Bearer {self._auth_token}",
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                response_json: dict[str, Any] = resp.json()
        except Exception as exc:
            latency_ms = int((time.monotonic() - t0) * 1000)
            error_str = str(exc)
            trace.append(TraceStep(
                step=3,
                label="CodeMie → codemie-caller-agent",
                direction="inbound",
                protocol="A2A JSON-RPC 1.0",
                payload={"error": error_str},
                latency_ms=latency_ms,
            ))
            trace.append(TraceStep(
                step=4,
                label="codemie-caller-agent → UI",
                direction="inbound",
                protocol="HTTP response",
                payload={"ok": False, "error": error_str},
            ))
            return CallResult(ok=False, response="", trace=trace, error=error_str)

        latency_ms = int((time.monotonic() - t0) * 1000)
        trace.append(TraceStep(
            step=3,
            label="CodeMie → codemie-caller-agent",
            direction="inbound",
            protocol="A2A JSON-RPC 1.0",
            payload=response_json,
            latency_ms=latency_ms,
        ))

        if "error" in response_json:
            err = response_json["error"]
            error_msg = f"A2A error {err.get('code')}: {err.get('message', 'unknown')}"
            trace.append(TraceStep(
                step=4,
                label="codemie-caller-agent → UI",
                direction="inbound",
                protocol="HTTP response",
                payload={"ok": False, "error": error_msg},
            ))
            return CallResult(ok=False, response="", trace=trace, error=error_msg)

        response_text = _extract_text(response_json)
        trace.append(TraceStep(
            step=4,
            label="codemie-caller-agent → UI",
            direction="inbound",
            protocol="HTTP response",
            payload={"ok": True, "response": response_text},
        ))
        return CallResult(ok=True, response=response_text, trace=trace)


def _extract_text(response_json: dict[str, Any]) -> str:
    result = response_json.get("result", {})
    task = result.get("task", {})
    artifacts = task.get("artifacts", [])
    if artifacts:
        parts = artifacts[0].get("parts", [])
        if parts:
            return parts[0].get("text", "")
    message = result.get("message", {})
    parts = message.get("parts", [])
    if parts:
        return parts[0].get("text", "")
    return str(result)
```

- [ ] **Step 4: Run tests — confirm they all pass**

```bash
uv run pytest tests/test_agent.py -v
```
Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ai-run-demo-agents/python/agents/codemie-caller-agent/agent.py \
        ai-run-demo-agents/python/agents/codemie-caller-agent/tests/test_agent.py
git commit -m "feat(codemie-caller-agent): implement CodeMieCallerAgent with trace capture"
```

---

## Task 3: Implement `app.py` — Starlette app and `/demo/chat` endpoint

**Files:**
- Create: `ai-run-demo-agents/python/agents/codemie-caller-agent/app.py`
- Create: `ai-run-demo-agents/python/agents/codemie-caller-agent/tests/test_app.py`

**Interfaces:**
- Consumes: `CodeMieCallerAgent`, `TraceStep`, `CallResult` from `agent.py`
- Produces:
  - `create_app(agent: CodeMieCallerAgent, host: str = "localhost", port: int = 11000) -> Starlette`

- [ ] **Step 1: Write failing tests in `tests/test_app.py`**

```python
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
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
uv run pytest tests/test_app.py -v
```
Expected: `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Implement `app.py`**

```python
import logging
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from a2a.helpers import new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from a2a.utils.errors import UnsupportedOperationError

from agent import CodeMieCallerAgent

logger = logging.getLogger(__name__)

_CORS_HEADERS: dict[str, str] = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


class CodeMieCallerExecutor(AgentExecutor):
    def __init__(self, agent: CodeMieCallerAgent) -> None:
        self._agent = agent

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        result = await self._agent.call(context.get_user_input())
        text = result.response if result.ok else (result.error or "Unknown error")
        await event_queue.enqueue_event(new_text_message(text))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise UnsupportedOperationError(message="Cancellation is not supported.")


async def demo_chat(request: Request) -> JSONResponse:
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON body"},
                            status_code=400, headers=_CORS_HEADERS)
    message: str = body.get("message", "")
    if not isinstance(message, str) or not message.strip():
        return JSONResponse({"ok": False, "error": "message field is required and must be non-empty"},
                            status_code=400, headers=_CORS_HEADERS)

    agent: CodeMieCallerAgent = request.app.state.agent
    logger.info("demo/chat: calling CodeMie via codemie-caller-agent")
    result = await agent.call(message.strip())

    trace_list = [
        {
            "step": s.step,
            "label": s.label,
            "direction": s.direction,
            "protocol": s.protocol,
            "payload": s.payload,
            **({"endpoint": s.endpoint} if s.endpoint is not None else {}),
            **({"latency_ms": s.latency_ms} if s.latency_ms is not None else {}),
        }
        for s in result.trace
    ]
    payload: dict[str, Any] = {"ok": result.ok, "response": result.response, "trace": trace_list}
    if not result.ok:
        payload["error"] = result.error
    return JSONResponse(payload, headers=_CORS_HEADERS)


async def demo_chat_preflight(request: Request) -> JSONResponse:
    return JSONResponse({}, headers=_CORS_HEADERS)


def create_app(
    agent: CodeMieCallerAgent,
    host: str = "localhost",
    port: int = 11000,
) -> Starlette:
    base_url = f"http://{host}:{port}"
    skill = AgentSkill(
        id="forward_to_codemie",
        name="Forward to CodeMie",
        description=(
            "Forwards the user message to a configured CodeMie assistant via A2A v1.0 "
            "and returns the response with a full wire trace."
        ),
        tags=["proxy", "codemie", "demo"],
        examples=[
            'Customer says: "The app keeps crashing after the last update."',
            "Set up a home Wi-Fi router.",
        ],
    )
    agent_card = AgentCard(
        name="CodeMie Caller Agent",
        description=(
            "Demo agent that calls a CodeMie assistant via A2A v1.0 "
            "and exposes the full wire trace for demonstration purposes."
        ),
        supported_interfaces=[
            AgentInterface(url=f"{base_url}/", protocol_binding="JSONRPC"),
        ],
        version="1.0.0",
        default_input_modes=CodeMieCallerAgent.SUPPORTED_CONTENT_TYPES,
        default_output_modes=CodeMieCallerAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )
    handler = DefaultRequestHandler(
        agent_executor=CodeMieCallerExecutor(agent),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )
    routes = [
        Route("/demo/chat", demo_chat, methods=["POST"]),
        Route("/demo/chat", demo_chat_preflight, methods=["OPTIONS"]),
        *create_agent_card_routes(agent_card),
        *create_jsonrpc_routes(handler, rpc_url="/"),
    ]
    app = Starlette(routes=routes)
    app.state.agent = agent
    return app
```

- [ ] **Step 4: Run all tests — confirm all pass**

```bash
uv run pytest tests/ -v
```
Expected: all tests in `test_agent.py` and `test_app.py` PASS.

- [ ] **Step 5: Commit**

```bash
git add ai-run-demo-agents/python/agents/codemie-caller-agent/app.py \
        ai-run-demo-agents/python/agents/codemie-caller-agent/tests/test_app.py
git commit -m "feat(codemie-caller-agent): add Starlette app with /demo/chat endpoint and A2A routes"
```

---

## Task 4: Implement `__main__.py` — CLI entry point

**Files:**
- Create: `ai-run-demo-agents/python/agents/codemie-caller-agent/__main__.py`

**Interfaces:**
- Consumes: `CodeMieCallerAgent` from `agent.py`; `create_app` from `app.py`
- Produces: runnable `uv run .` entry point; reads `CM_BASE_URL`, `CM_ASSISTANT_ID`, `CM_AUTH_TOKEN` from env

- [ ] **Step 1: Implement `__main__.py`**

```python
import logging
import os

import click
import uvicorn
from dotenv import load_dotenv

from agent import CodeMieCallerAgent
from app import create_app

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _build_agent() -> CodeMieCallerAgent:
    cm_base_url = os.environ.get("CM_BASE_URL", "http://localhost:8080")
    cm_assistant_id = os.environ["CM_ASSISTANT_ID"]
    cm_auth_token = os.environ["CM_AUTH_TOKEN"]
    return CodeMieCallerAgent(cm_base_url, cm_assistant_id, cm_auth_token)


@click.command()
@click.option("--host", default="localhost", show_default=True)
@click.option("--port", default=11000, show_default=True)
def main(host: str, port: int) -> None:
    agent = _build_agent()
    app = create_app(agent, host, port)
    logger.info("Starting codemie-caller-agent on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-test the entry point (requires env vars)**

Set env vars and start the agent in a terminal:
```bash
# From ai-run-demo-agents/python/agents/codemie-caller-agent/
export CM_ASSISTANT_ID=test-id
export CM_AUTH_TOKEN=test-token
uv run . --host localhost --port 11000
```
Expected: server starts, logs `Starting codemie-caller-agent on localhost:11000`, `Application startup complete`.

In a second terminal:
```bash
curl -s localhost:11000/.well-known/agent-card.json | python3 -m json.tool
```
Expected: JSON with `"name": "CodeMie Caller Agent"`.

- [ ] **Step 3: Confirm missing env var raises a clear error**

```bash
unset CM_ASSISTANT_ID
uv run . --host localhost --port 11000
```
Expected: `KeyError: 'CM_ASSISTANT_ID'` — confirms the required-variable guard works.

- [ ] **Step 4: Commit**

```bash
git add ai-run-demo-agents/python/agents/codemie-caller-agent/__main__.py
git commit -m "feat(codemie-caller-agent): add click CLI entry point"
```

---

## Task 5: Dockerfile

**Files:**
- Create: `ai-run-demo-agents/python/agents/codemie-caller-agent/Dockerfile`

**Interfaces:**
- Produces: Docker image `demo-codemie-caller-agent` runnable via `docker run`

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.13-alpine

# Copy the workspace root into the image
COPY --from=ai-run-agents common /app/common
COPY --from=ai-run-agents pyproject.toml /app/pyproject.toml
COPY --from=ai-run-agents README.md /app/README.md
COPY --from=ai-run-agents uv.lock /app/uv.lock
COPY . /app/agents/codemie-caller-agent

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

WORKDIR /app/agents/codemie-caller-agent
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH"

CMD ["uv", "run", ".", "--host", "0.0.0.0", "--port", "11000"]
```

- [ ] **Step 2: Build the image (from `ai-run-demo-agents/python/`)**

```bash
# Run from ai-run-demo-agents/python/
docker build \
  --build-context ai-run-agents=. \
  -t demo-codemie-caller-agent \
  agents/codemie-caller-agent
```
Expected: build succeeds with no errors.

- [ ] **Step 3: Verify the container starts**

```bash
docker run --rm \
  -e CM_ASSISTANT_ID=test-id \
  -e CM_AUTH_TOKEN=test-token \
  -p 11000:11000 \
  demo-codemie-caller-agent
```
Expected: logs `Starting codemie-caller-agent on 0.0.0.0:11000`. Ctrl+C to stop.

- [ ] **Step 4: Commit**

```bash
git add ai-run-demo-agents/python/agents/codemie-caller-agent/Dockerfile
git commit -m "feat(codemie-caller-agent): add Dockerfile mirroring text-insights-agent pattern"
```

---

## Task 6: Chat UI — `index.html` and `style.css`

**Files:**
- Create: `ui-demo-agents/chat-ui/index.html`
- Create: `ui-demo-agents/chat-ui/style.css`

**Interfaces:**
- Produces: static HTML page renderable by any browser; uses `app.js` (Task 7)

- [ ] **Step 1: Create `index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>A2A Multi-Hop Demo</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header class="config-bar">
    <div class="config-left">
      <label for="agentUrl">Agent URL</label>
      <input id="agentUrl" type="text" value="http://localhost:11000" spellcheck="false">
    </div>
    <div class="config-right">
      <span id="statusDot" class="dot dot-unknown" title="Agent reachability"></span>
      <span id="statusLabel">Checking…</span>
    </div>
  </header>

  <main class="layout">
    <section class="chat-panel">
      <div id="messages" class="messages" aria-live="polite"></div>

      <div class="quick-prompts">
        <span class="prompts-label">Quick prompts:</span>
        <button onclick="fillPreset('analyze')">Analyze customer feedback</button>
        <button onclick="fillPreset('wifi')">Set up Wi-Fi router</button>
      </div>

      <div class="input-row">
        <textarea id="msgInput"
          placeholder="Type a message… (Enter to send, Shift+Enter for new line)"
          rows="3"></textarea>
        <button id="sendBtn" onclick="sendMessage()">Send</button>
      </div>
    </section>

    <section class="trace-panel">
      <h2>Wire Trace</h2>
      <div id="traceSteps" class="trace-steps">
        <p class="trace-empty">Send a message to see the A2A call trace.</p>
      </div>
    </section>
  </main>

  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create `style.css`**

```css
:root {
  --bg: #0f1117;
  --surface: #1a1d2e;
  --surface-alt: #222536;
  --border: #2e3147;
  --text: #e2e8f0;
  --text-muted: #8892a4;
  --blue: #4a9eff;
  --green: #34d399;
  --red: #f87171;
  --yellow: #fbbf24;
  --radius: 8px;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: system-ui, -apple-system, sans-serif;
  font-size: 14px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Config bar ──────────────────────────────────── */
.config-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.config-left { display: flex; align-items: center; gap: 8px; }
.config-left label { color: var(--text-muted); white-space: nowrap; }
.config-left input {
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: var(--radius);
  padding: 4px 10px;
  width: 280px;
  font-size: 13px;
}
.config-right { display: flex; align-items: center; gap: 6px; color: var(--text-muted); font-size: 13px; }

.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.dot-unknown { background: var(--text-muted); }
.dot-ok      { background: var(--green); box-shadow: 0 0 6px var(--green); }
.dot-error   { background: var(--red); }

/* ── Main two-column layout ──────────────────────── */
.layout {
  display: grid;
  grid-template-columns: 60fr 40fr;
  flex: 1;
  min-height: 0;
}

/* ── Chat panel ──────────────────────────────────── */
.chat-panel {
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  min-height: 0;
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.message {
  max-width: 80%;
  padding: 10px 14px;
  border-radius: var(--radius);
  line-height: 1.55;
  word-break: break-word;
}
.message-user     { background: var(--blue);       color: #fff;           align-self: flex-end;  }
.message-agent    { background: var(--surface-alt);                        align-self: flex-start; white-space: pre-wrap; }
.message-error    { background: #3f1515;            color: var(--red);     align-self: flex-start; font-style: italic; }
.message-thinking { background: var(--surface-alt); color: var(--text-muted); align-self: flex-start; font-style: italic; }

.quick-prompts {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-top: 1px solid var(--border);
  flex-wrap: wrap;
}
.prompts-label { color: var(--text-muted); font-size: 12px; }
.quick-prompts button {
  background: var(--surface-alt);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 20px;
  padding: 4px 12px;
  cursor: pointer;
  font-size: 12px;
}
.quick-prompts button:hover { background: var(--border); }

.input-row {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  align-items: flex-end;
}
.input-row textarea {
  flex: 1;
  background: var(--surface-alt);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: var(--radius);
  padding: 8px 12px;
  font: inherit;
  resize: none;
}
.input-row textarea:focus { outline: none; border-color: var(--blue); }
.input-row button {
  background: var(--blue);
  border: none;
  color: #fff;
  border-radius: var(--radius);
  padding: 8px 20px;
  cursor: pointer;
  font-weight: 600;
  align-self: flex-end;
}
.input-row button:disabled { opacity: 0.5; cursor: not-allowed; }
.input-row button:not(:disabled):hover { opacity: 0.85; }

/* ── Trace panel ─────────────────────────────────── */
.trace-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.trace-panel h2 {
  padding: 14px 16px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.trace-steps {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.trace-empty   { color: var(--text-muted); font-style: italic; padding: 4px; }
.trace-loading { color: var(--yellow);     font-style: italic; padding: 4px; }

.trace-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
.trace-card.trace-outbound { border-left: 3px solid var(--blue); }
.trace-card.trace-inbound  { border-left: 3px solid var(--green); }

.trace-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
}
.step-num {
  background: var(--surface-alt);
  border-radius: 50%;
  width: 22px; height: 22px;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}
.step-label  { flex: 1; font-size: 12px; font-weight: 600; }
.latency {
  background: var(--surface-alt);
  border-radius: 4px;
  padding: 2px 6px;
  font-size: 11px;
  color: var(--yellow);
  white-space: nowrap;
}

.trace-meta {
  padding: 0 12px 6px;
  font-size: 11px;
  color: var(--text-muted);
  font-family: monospace;
  word-break: break-all;
}

.expand-btn {
  background: none;
  border: none;
  color: var(--blue);
  cursor: pointer;
  font-size: 11px;
  padding: 2px 12px 8px;
  text-align: left;
}
.expand-btn:hover { text-decoration: underline; }

.trace-payload {
  background: var(--bg);
  border-top: 1px solid var(--border);
  padding: 10px 12px;
  font-family: monospace;
  font-size: 11px;
  overflow-x: auto;
  white-space: pre;
  max-height: 200px;
  overflow-y: auto;
  color: #a5f3c0;
}
.hidden { display: none; }
```

- [ ] **Step 3: Open in browser and verify layout**

```bash
cd ui-demo-agents/chat-ui
python -m http.server 8090
```
Open `http://localhost:8090`. Verify:
- Config bar at top with URL input and status dot (should show red "Unreachable" if agent is not running)
- Left 60%: empty messages area, quick-prompt buttons, textarea, Send button
- Right 40%: "Wire Trace" header, "Send a message…" placeholder text

- [ ] **Step 4: Commit**

```bash
git add ui-demo-agents/chat-ui/index.html ui-demo-agents/chat-ui/style.css
git commit -m "feat(ui-demo-agents): add chat UI HTML layout and dark-theme CSS"
```

---

## Task 7: Chat UI — `app.js`

**Files:**
- Create: `ui-demo-agents/chat-ui/app.js`

**Interfaces:**
- Consumes: DOM elements `agentUrl`, `statusDot`, `statusLabel`, `messages`, `msgInput`, `sendBtn`, `traceSteps`
- Consumes: `POST /demo/chat` response: `{ok, response, trace[], error?}`

- [ ] **Step 1: Create `app.js`**

```javascript
const PRESETS = {
  analyze: 'Customer says: "The app keeps crashing after the last update and support has not answered my ticket for 3 days. I am really disappointed."',
  wifi: 'Set up a home Wi-Fi router.'
};

function fillPreset(key) {
  document.getElementById('msgInput').value = PRESETS[key];
  document.getElementById('msgInput').focus();
}

function agentBaseUrl() {
  return document.getElementById('agentUrl').value.trim().replace(/\/$/, '');
}

async function checkStatus() {
  const dot = document.getElementById('statusDot');
  const label = document.getElementById('statusLabel');
  try {
    const resp = await fetch(
      `${agentBaseUrl()}/.well-known/agent-card.json`,
      { signal: AbortSignal.timeout(3000) }
    );
    if (resp.ok) {
      const card = await resp.json();
      dot.className = 'dot dot-ok';
      label.textContent = card.name || 'Connected';
    } else {
      dot.className = 'dot dot-error';
      label.textContent = `HTTP ${resp.status}`;
    }
  } catch {
    dot.className = 'dot dot-error';
    label.textContent = 'Unreachable';
  }
}

function appendMessage(role, text) {
  const el = document.createElement('div');
  el.className = `message message-${role}`;
  el.textContent = text;
  const msgs = document.getElementById('messages');
  msgs.appendChild(el);
  msgs.scrollTop = msgs.scrollHeight;
  return el;
}

function renderTrace(trace) {
  const container = document.getElementById('traceSteps');
  container.innerHTML = '';
  for (const step of trace) {
    const card = document.createElement('div');
    card.className = `trace-card trace-${step.direction}`;

    const header = document.createElement('div');
    header.className = 'trace-header';

    const num = document.createElement('span');
    num.className = 'step-num';
    num.textContent = step.step;
    header.appendChild(num);

    const lbl = document.createElement('span');
    lbl.className = 'step-label';
    lbl.textContent = step.label;
    header.appendChild(lbl);

    if (step.latency_ms != null) {
      const lat = document.createElement('span');
      lat.className = 'latency';
      lat.textContent = `${step.latency_ms} ms`;
      header.appendChild(lat);
    }

    const meta = document.createElement('div');
    meta.className = 'trace-meta';
    meta.textContent = step.endpoint
      ? `${step.protocol} → ${step.endpoint}`
      : step.protocol;

    const toggle = document.createElement('button');
    toggle.className = 'expand-btn';
    toggle.textContent = '▶ Show payload';

    const pre = document.createElement('pre');
    pre.className = 'trace-payload hidden';
    pre.textContent = JSON.stringify(step.payload, null, 2);

    toggle.addEventListener('click', () => {
      const hidden = pre.classList.toggle('hidden');
      toggle.textContent = hidden ? '▶ Show payload' : '▼ Hide payload';
    });

    card.appendChild(header);
    card.appendChild(meta);
    card.appendChild(toggle);
    card.appendChild(pre);
    container.appendChild(card);
  }
}

async function sendMessage() {
  const input = document.getElementById('msgInput');
  const sendBtn = document.getElementById('sendBtn');
  const message = input.value.trim();
  if (!message) return;

  input.value = '';
  sendBtn.disabled = true;
  appendMessage('user', message);
  const thinking = appendMessage('thinking', 'Calling codemie-caller-agent…');

  document.getElementById('traceSteps').innerHTML =
    '<div class="trace-loading">Calling codemie-caller-agent…</div>';

  try {
    const resp = await fetch(`${agentBaseUrl()}/demo/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    });
    const data = await resp.json();
    thinking.remove();

    if (data.trace) renderTrace(data.trace);

    if (data.ok) {
      appendMessage('agent', data.response);
    } else {
      appendMessage('error', `Error: ${data.error || 'Unknown error'}`);
    }
  } catch (err) {
    thinking.remove();
    document.getElementById('traceSteps').innerHTML =
      `<div class="trace-empty">Request failed: ${err.message}</div>`;
    appendMessage('error', `Request failed: ${err.message}`);
  } finally {
    sendBtn.disabled = false;
    await checkStatus();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  checkStatus();
  document.getElementById('agentUrl').addEventListener('change', checkStatus);
  document.getElementById('msgInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
});
```

- [ ] **Step 2: Verify the UI end-to-end with a running agent**

With `codemie-caller-agent` running on port 11000 (env vars set):
1. `python -m http.server 8090` from `ui-demo-agents/chat-ui/`
2. Open `http://localhost:8090`
3. Status dot should turn green and show "CodeMie Caller Agent"
4. Click "Analyze customer feedback" — textarea fills with the preset message
5. Press Enter — thinking indicator appears, trace panel shows "Calling…"
6. After the response: four trace cards appear (steps 1–4), agent response appears in left panel
7. Click "▶ Show payload" on step 2 — JSON-RPC SendMessage payload expands
8. Click "▶ Show payload" on step 3 — CodeMie response JSON expands with latency badge

> If CodeMie is not running, step 3 will show an error card and the chat shows an error message — this is the correct error-display behavior to verify.

- [ ] **Step 3: Commit**

```bash
git add ui-demo-agents/chat-ui/app.js
git commit -m "feat(ui-demo-agents): add chat UI JavaScript with trace rendering and preset messages"
```

---

## Task 8: Demo guide and env example

**Files:**
- Create: `ui-demo-agents/demo.env.example`
- Create: `ui-demo-agents/README.md`

- [ ] **Step 1: Create `demo.env.example`**

```bash
# CodeMie base URL — default works for local Docker compose
CM_BASE_URL=http://localhost:8080

# UUID of the CodeMie assistant to call.
# Find it in the URL after navigating to the assistant:
#   http://localhost:5173/assistants/<CM_ASSISTANT_ID>
CM_ASSISTANT_ID=<paste-assistant-id-here>

# Bearer JWT from CodeMie local login (lasts 24 hours).
# Obtain with (run in WSL/bash, not PowerShell — read -s hides the password):
#
#   read -p "email: " EMAIL; read -s -p "password: " PASS; echo
#   export CM_AUTH_TOKEN=$(curl -s -X POST http://localhost:8080/v1/local-auth/login \
#     -H "Content-Type: application/json" \
#     -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" \
#     | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
CM_AUTH_TOKEN=<paste-jwt-here>
```

- [ ] **Step 2: Create `README.md`**

````markdown
# A2A Multi-Hop Demo

Demonstrates the full A2A v1.0 communication flow:

```
Browser UI  →  codemie-caller-agent (port 11000)  →  CodeMie assistant (port 8080)
                        ↑                                        ↓
                Browser UI  ←  codemie-caller-agent  ←  CodeMie assistant
```

The chat UI sends a message to `codemie-caller-agent`, which calls a CodeMie assistant via
A2A JSON-RPC 1.0. Every request and response payload is captured and shown in the **Wire
Trace** panel so a presenter can walk through each hop of the protocol.

---

## 1. Prerequisites

- CodeMie running at `http://localhost:8080` (see `DEMO-GUIDE.md` section 3.2).
- Python 3.13 + [uv](https://docs.astral.sh/uv/) installed in WSL.
- A CodeMie assistant already created (any model, any system prompt).
- Ports 11000 (agent) and 8090 (UI server) free.

---

## 2. Configuration

### 2.1 Get the assistant ID

Open the CodeMie UI at `http://localhost:5173`, navigate to your assistant, and copy the UUID from the URL:
```
http://localhost:5173/assistants/<CM_ASSISTANT_ID>
```

### 2.2 Get a JWT

Run in WSL bash (the `read -s` flag hides the password from the terminal):
```bash
read -p "email: " EMAIL; read -s -p "password: " PASS; echo
export CM_AUTH_TOKEN=$(curl -s -X POST http://localhost:8080/v1/local-auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "${CM_AUTH_TOKEN:0:20}..."   # verify it is non-empty
```
The token lasts 24 hours.

### 2.3 Create the env file for the agent

```bash
cp ui-demo-agents/demo.env.example ai-run-demo-agents/python/agents/codemie-caller-agent/.env
# Then edit the .env file and replace the placeholder values:
#   CM_ASSISTANT_ID=<your assistant id>
#   CM_AUTH_TOKEN=<your jwt>
```

---

## 3. Start `codemie-caller-agent`

### Option A — local (uv)

```bash
cd ai-run-demo-agents/python/agents/codemie-caller-agent
uv run . --host localhost --port 11000
```

### Option B — Docker (on the CodeMie compose network)

```bash
NET=codemie-dev_codemie-network
cd ai-run-demo-agents/python

docker build \
  --build-context ai-run-agents=. \
  -t demo-codemie-caller-agent \
  agents/codemie-caller-agent

docker run -d --name codemie-caller-agent --network $NET -p 11000:11000 \
  -e CM_BASE_URL=http://codemie:8080 \
  -e CM_ASSISTANT_ID=<your-assistant-id> \
  -e CM_AUTH_TOKEN=<your-jwt> \
  demo-codemie-caller-agent
```

> When running in Docker on the compose network, use `CM_BASE_URL=http://codemie:8080`
> (the container name), not `http://localhost:8080`.

Verify the agent is healthy:
```bash
curl -s localhost:11000/.well-known/agent-card.json | python3 -m json.tool
```
Expected: JSON with `"name": "CodeMie Caller Agent"`.

---

## 4. Start the chat UI

```bash
cd ui-demo-agents/chat-ui
python -m http.server 8090
```
Open `http://localhost:8090` in your browser.

The status dot in the top-right turns **green** when `codemie-caller-agent` is reachable.

---

## 5. Demo walkthrough

1. In the **Agent URL** input (top-left), confirm the URL is `http://localhost:11000`.
2. Click **Analyze customer feedback** to fill in the preset message, or type your own.
3. Press **Enter** (or click **Send**).
4. Watch the **Wire Trace** panel on the right fill in 4 steps:
   - **Step 1** — your message leaves the browser to `codemie-caller-agent`
   - **Step 2** — `codemie-caller-agent` calls CodeMie via `A2A JSON-RPC 1.0`; click **▶ Show payload** to see the real `SendMessage` request
   - **Step 3** — CodeMie responds; click **▶ Show payload** to see the `result.task.artifacts` body and the round-trip latency
   - **Step 4** — `codemie-caller-agent` forwards the answer back to the browser
5. The assistant's reply appears in the left chat panel.

---

## 6. Verifying the communication was real

| Evidence | Where to look | What it shows |
|---|---|---|
| **Wire Trace step 2** | Right panel, expand payload | Exact JSON-RPC `SendMessage` body sent to CodeMie, including `A2A-Version: 1.0` |
| **Wire Trace step 3** | Right panel, expand payload | Exact JSON-RPC response from CodeMie, including `result.task.artifacts` |
| **Agent terminal** | WSL terminal running `uv run .` | `INFO ... calling CodeMie via codemie-caller-agent` log line |
| **CodeMie logs** | `docker compose logs codemie \| grep a2a` | `POST /v1/a2a/assistants/<id>` request line with HTTP 200 |
| **Browser Network tab** | DevTools → Network → filter `demo/chat` | One `POST http://localhost:11000/demo/chat` request, 200 response, full JSON body |

---

## 7. Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| Status dot stays red | Agent not running, or wrong URL in the input. Check `curl localhost:11000/.well-known/agent-card.json`. |
| `Error: A2A error -32009: VERSION_NOT_SUPPORTED` | `A2A-Version: 1.0` header missing — this should not happen in normal use; check the agent logs for the raw request. |
| `Error: A2A error -32001: Task not found` | The `CM_ASSISTANT_ID` in your `.env` does not exist. Create/check the assistant in the CodeMie UI. |
| HTTP 401 from CodeMie | JWT expired (24-hour lifetime). Re-run the login command in section 2.2. |
| CORS error in browser console | The `codemie-caller-agent` is not running or is on a different port than configured. |
| Docker: `codemie:8080` not reachable | Container not on the compose network. Add `--network codemie-dev_codemie-network` to the `docker run` command. |

---

## 8. Cleanup

```bash
# Stop the UI server: Ctrl+C in its terminal
# Stop the local agent: Ctrl+C in its terminal
# OR remove the Docker container:
docker rm -f codemie-caller-agent
```
````

- [ ] **Step 3: Verify the README is complete**

Read through all 8 sections and confirm:
- Every command is copy-pasteable and references real paths
- The JWT login command matches section 6.1 of `DEMO-GUIDE.md`
- The Docker `CM_BASE_URL` note uses the container name, not `localhost`
- The troubleshooting table covers the 5 most likely failure modes

- [ ] **Step 4: Commit**

```bash
git add ui-demo-agents/demo.env.example ui-demo-agents/README.md
git commit -m "feat(ui-demo-agents): add demo guide and env example"
```

---

## Final verification

- [ ] Run the full test suite from the agent directory:
  ```bash
  cd ai-run-demo-agents/python/agents/codemie-caller-agent
  uv run pytest tests/ -v
  ```
  Expected: all tests PASS, no warnings.

- [ ] Confirm the Docker image builds clean:
  ```bash
  cd ai-run-demo-agents/python
  docker build --build-context ai-run-agents=. -t demo-codemie-caller-agent agents/codemie-caller-agent
  ```
  Expected: no errors.

- [ ] With CodeMie running: do a live end-to-end test following the walkthrough in `ui-demo-agents/README.md` section 5. Confirm all 4 trace steps appear and the JSON payloads contain real A2A content.
````
