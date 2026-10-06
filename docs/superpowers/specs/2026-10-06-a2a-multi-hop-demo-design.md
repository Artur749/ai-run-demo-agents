# Design: A2A Multi-Hop Demo

**Date:** 2026-10-06
**Status:** Approved
**Scope:** New `codemie-caller-agent` in `ai-run-demo-agents` + chat UI in `ui-demo-agents`

## Goal

Provide a live, interactive demo of the full A2A multi-hop communication flow:

```
External Client (Browser UI) → codemie-caller-agent → CodeMie assistant → codemie-caller-agent → Browser UI
```

The demo must show the protocol payloads at each hop so a presenter can walk through them during a live demo session.

## Components

### 1. `codemie-caller-agent`

**Location:** `ai-run-demo-agents/python/agents/codemie-caller-agent/`
**Port:** 11000 (default)
**Role:** "The Test Assistant" — a real A2A server that, upon receiving a message, calls a configured CodeMie assistant via the A2A v1.0 protocol and returns the response.

#### A2A interface (standard, works with any A2A client)

- Agent card: `GET /.well-known/agent-card.json`
  - `name`: "CodeMie Caller Agent"
  - `capabilities.streaming`: false
  - One skill: "Forward to CodeMie assistant and return the answer"
- JSON-RPC endpoint: `POST /`
  - Supports `SendMessage`, `GetTask`, `CancelTask`
  - On `SendMessage`: calls CodeMie's `POST /v1/a2a/assistants/<id>` using `a2a-sdk` client with `SendMessage`, waits for the response, and returns CodeMie's answer as its own `message` result.

#### Demo REST endpoint (for the chat UI)

`POST /demo/chat`
- Request body: `{"message": "<user text>"}`
- Returns a structured trace + final response (see Trace structure below)
- CORS header `Access-Control-Allow-Origin: *` is set on this route only (demo only; never used in A2A calls)

#### Trace structure

```json
{
  "ok": true,
  "response": "<final text from CodeMie>",
  "trace": [
    {
      "step": 1,
      "label": "UI → codemie-caller-agent",
      "direction": "outbound",
      "protocol": "HTTP POST /demo/chat",
      "payload": {"message": "..."},
      "latency_ms": null
    },
    {
      "step": 2,
      "label": "codemie-caller-agent → CodeMie (A2A SendMessage)",
      "direction": "outbound",
      "protocol": "A2A JSON-RPC 1.0",
      "endpoint": "<CM_BASE_URL>/v1/a2a/assistants/<CM_ASSISTANT_ID>",
      "payload": {"jsonrpc": "2.0", "id": "...", "method": "SendMessage", "params": {...}},
      "latency_ms": null
    },
    {
      "step": 3,
      "label": "CodeMie → codemie-caller-agent",
      "direction": "inbound",
      "protocol": "A2A JSON-RPC 1.0",
      "payload": {"jsonrpc": "2.0", "id": "...", "result": {...}},
      "latency_ms": 142
    },
    {
      "step": 4,
      "label": "codemie-caller-agent → UI",
      "direction": "inbound",
      "protocol": "HTTP response",
      "payload": {"response": "...", "trace": ["..."]},
      "latency_ms": null
    }
  ]
}
```

Steps 2 and 3 carry the real JSON-RPC payloads captured during the call. Step 3 `latency_ms` is the measured round-trip time for the CodeMie call.

On error the response is `{"ok": false, "error": "<message>", "trace": [...]}` with whatever trace steps completed before the failure.

#### Configuration (env vars)

| Variable | Default | Description |
|---|---|---|
| `CM_BASE_URL` | `http://localhost:8080` | CodeMie base URL |
| `CM_ASSISTANT_ID` | (required) | UUID of the CodeMie assistant to call |
| `CM_AUTH_TOKEN` | (required) | Bearer JWT for CodeMie authentication |
| Port | 11000 | `--port` CLI arg |
| Host | `localhost` | `--host` CLI arg |

#### File layout

```
ai-run-demo-agents/python/agents/codemie-caller-agent/
  __init__.py
  __main__.py      # click CLI, Starlette app, routes
  agent.py         # CodeMieCallerAgent: calls CodeMie, captures trace
  pyproject.toml   # a2a-sdk[http-server], httpx, click, starlette, uvicorn, python-dotenv
  Dockerfile       # mirrors other agents: base from ai-run-agents build-context
```

`pyproject.toml` is a standalone uv workspace member (same pattern as `text-insights-agent`). It does **not** need `langchain-*` dependencies because there is no local LLM call.

`ai-run-demo-agents/python/pyproject.toml` `[tool.uv.workspace].members` gains `"agents/codemie-caller-agent"`.

#### Implementation notes

- `agent.py` uses `httpx.AsyncClient` directly rather than the `a2a-sdk` high-level client so the raw JSON-RPC request and response can be captured verbatim for the trace.
- The `A2A-Version: 1.0` and `Authorization: Bearer <token>` headers are sent on every CodeMie call.
- Message ID and context ID are generated fresh per `/demo/chat` call (no session continuity across UI messages — keeping the demo stateless).
- The A2A JSON-RPC endpoint at `POST /` uses the standard `a2a-sdk` server machinery (`DefaultRequestHandler`, `InMemoryTaskStore`) so it works as a genuine A2A server callable by the SDK's test clients.

---

### 2. Chat UI

**Location:** `ui-demo-agents/chat-ui/`
**Technology:** Plain HTML + CSS + vanilla JS. No npm, no build step.
**Served by:** `python -m http.server 8090` run from `ui-demo-agents/chat-ui/` (one command).

#### Layout

Two-column layout (single HTML page):

```
┌─────────────────────────────────────────────────────┐
│  [Agent URL: http://localhost:11000]   ● Connected   │   ← config bar
├────────────────────────┬────────────────────────────┤
│                        │  Wire Trace                 │
│  Chat                  │  ─────────────────────────  │
│                        │  ① UI → caller-agent        │
│  [User message]        │    POST /demo/chat          │
│                        │    {"message": "..."}       │
│  [Agent response]      │  ② caller-agent → CodeMie   │
│                        │    A2A SendMessage          │
│                        │    ▶ expand JSON            │
│                        │  ③ CodeMie → caller-agent   │
│                        │    A2A result (142 ms)      │
│                        │    ▶ expand JSON            │
│                        │  ④ caller-agent → UI        │
│                        │    HTTP response             │
│  ─────────────────     │                             │
│  [Type a message...]  [Send]                         │
└────────────────────────┴────────────────────────────┘
```

- **Left panel (60%)**: Chat bubbles. User messages right-aligned, agent responses left-aligned.
- **Right panel (40%)**: Wire trace. Each of the 4 steps is a card with:
  - Step number + label
  - Direction indicator (arrow icon; blue = outbound, green = inbound)
  - Protocol + endpoint line
  - Collapsible JSON block (collapsed by default; click to expand)
  - Latency badge on steps 3 and 4
- **Config bar**: Agent URL text input + live status dot (green = reachable, red = unreachable, checked on page load and after each request). The dot does a `GET /.well-known/agent-card.json` to verify reachability.

#### Preset messages (demo convenience)

A small "Quick prompts" row below the input with two preset buttons:
- "Analyze customer feedback" → fills in the text-insights demo message from DEMO-GUIDE.md
- "Set up Wi-Fi router" → fills in the howto-guide demo message

These help the presenter run the demo without typing.

#### Files

```
ui-demo-agents/
  chat-ui/
    index.html   # full single-page app markup
    app.js       # fetch, render trace, manage state
    style.css    # layout + color tokens
  demo.env.example
  README.md      # demo guide (see section 3)
```

`app.js` builds the `SendMessage` JSON-RPC request body itself so the trace shows the real wire payload — it does not use the a2a-sdk (no npm). The `/demo/chat` REST wrapper is what `app.js` actually calls; the real A2A JSON-RPC payload is embedded in the `trace[1].payload` field returned by the agent.

---

### 3. Demo Guide (`ui-demo-agents/README.md`)

Sections:

1. **Overview** — diagram of the 4-hop flow and what each component is
2. **Prerequisites** — CodeMie running at `:8080`, Python 3.13 + uv, a CodeMie assistant ID + JWT
3. **Configuration** — how to obtain `CM_ASSISTANT_ID` (UI URL), how to get `CM_AUTH_TOKEN` (login curl), what `demo.env.example` looks like
4. **Start codemie-caller-agent** — local (`uv run . --host localhost`) and Docker commands
5. **Start the chat UI** — `python -m http.server 8090` from `chat-ui/`, open `http://localhost:8090`
6. **Using the demo** — step-by-step walkthrough matching the 4-hop flow
7. **Verifying the flow** — what evidence proves the call was real:
   - Browser Network tab: one `POST /demo/chat` request with 200 response
   - Wire Trace panel in the UI: steps 2 and 3 show real A2A JSON-RPC payloads
   - Agent terminal: `INFO codemie-caller-agent: calling CodeMie ...` log lines
   - CodeMie logs: `POST /v1/a2a/assistants/<id>` request visible in `docker compose logs codemie`
8. **Troubleshooting** — CORS, auth failures, timeout issues

---

## Integration with `ai-run-demo-agents`

The new agent fits the existing workspace with these changes:
- Add `"agents/codemie-caller-agent"` to `[tool.uv.workspace].members` in `python/pyproject.toml`
- Docker build command follows the existing section 3.3 pattern with `--build-context ai-run-agents=<python dir>`
- No changes to existing agents

## Out of scope

- Session continuity (multi-turn conversation in the UI)
- Streaming from CodeMie (blocking `SendMessage` is sufficient for demo)
- Selecting different "test assistants" (the `codemie-caller-agent` is the test assistant)
- Auth UI (token is provided via env var)
- Changes to `DEMO-GUIDE.md`
