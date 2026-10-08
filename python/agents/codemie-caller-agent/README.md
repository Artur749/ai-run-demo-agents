# CodeMie Caller Agent

Demo A2A agent that forwards messages to a CodeMie assistant via the A2A protocol (v1.0) and
returns a full 4-step wire trace, making the call path visible for demonstration and debugging.

## How It Works

The agent itself has no LLM. When it receives a message, it:

1. Accepts an incoming user message (either via `/demo/chat` HTTP or as a regular A2A `SendMessage` call)
2. Forwards the message to a configured CodeMie assistant using `A2A SendMessage` over JSON-RPC 1.0
3. Extracts the text response from the CodeMie reply
4. Returns both the response text and a 4-step wire trace that shows every hop: UI → this agent → CodeMie → back

This makes the agent useful as the outer hop in a **multi-hop A2A demo**: an external client calls
this agent (via its own A2A interface), and this agent calls CodeMie via A2A, so the full protocol
stack is exercised end-to-end.

The `/demo/chat` endpoint is a plain HTTP `POST` intended for browser-based demo UIs that want the
wire trace without needing to speak A2A themselves.

## Prerequisites

- Python 3.13 or higher
- [UV](https://docs.astral.sh/uv/)
- A running CodeMie instance with a known assistant ID and a valid API token

Unlike the other agents in this repository, no LLM credentials are required — all inference
happens inside CodeMie.

## Setup & Running

1. Navigate to the agent directory:

   ```bash
   cd ai-run-demo-agents/python/agents/codemie-caller-agent
   ```

2. Create an environment file and fill in your CodeMie credentials:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set:

   | Variable | Required | Description |
   |---|---|---|
   | `CM_BASE_URL` | No (default: `http://localhost:8080`) | Base URL of the CodeMie instance |
   | `CM_ASSISTANT_ID` | **Yes** | ID of the CodeMie assistant to call |
   | `CM_AUTH_TOKEN` | **Yes** | Bearer token for the CodeMie API |

   To obtain a token from a local CodeMie instance:

   ```bash
   export CM_AUTH_TOKEN=$(curl -s -X POST http://localhost:8080/v1/local-auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"admin@codemie.ai","password":"password"}' \
     | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
   ```

3. Run the agent:

   ```bash
   # Default: localhost:11000
   uv run .

   # Custom host/port (needed when running alongside CodeMie in Docker)
   uv run . --host 0.0.0.0 --port 11000
   ```

4. With Docker (requires the `ai-run-agents` build context pointing at `python/`):

   ```bash
   docker buildx build \
     --build-context ai-run-agents=/path/to/ai-run-demo-agents/python/ \
     -t codemie-caller-agent:latest .

   docker run -it -p 11000:11000 \
     -e CM_BASE_URL=http://codemie:8080 \
     -e CM_ASSISTANT_ID=<your-assistant-id> \
     -e CM_AUTH_TOKEN=<your-token> \
     codemie-caller-agent:latest
   ```

   When CodeMie runs in Docker, pass the CodeMie container name as `CM_BASE_URL` and start this
   agent on the same Docker network so the two containers can reach each other.

## Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/.well-known/agent-card.json` | `GET` | A2A Agent Card |
| `/` | `POST` | A2A JSON-RPC 1.0 endpoint (`SendMessage`) |
| `/demo/chat` | `POST` | Plain HTTP helper for demo UIs (see below) |

### `/demo/chat` — plain HTTP demo endpoint

Accepts `{"message": "<text>"}` and returns:

```json
{
  "ok": true,
  "response": "<text from CodeMie>",
  "trace": [
    {"step": 1, "label": "UI → codemie-caller-agent", "direction": "outbound", "protocol": "HTTP POST /demo/chat", "payload": {...}},
    {"step": 2, "label": "codemie-caller-agent → CodeMie (A2A SendMessage)", "direction": "outbound", "protocol": "A2A JSON-RPC 1.0", "endpoint": "...", "payload": {...}},
    {"step": 3, "label": "CodeMie → codemie-caller-agent", "direction": "inbound", "protocol": "A2A JSON-RPC 1.0", "latency_ms": 342, "payload": {...}},
    {"step": 4, "label": "codemie-caller-agent → UI", "direction": "inbound", "protocol": "HTTP response", "payload": {...}}
  ]
}
```

Quick test once the agent is running:

```bash
curl -s -X POST http://localhost:11000/demo/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What can you help me with?"}' | python3 -m json.tool
```

## Testing

Unit tests run without a live CodeMie instance:

```bash
uv run pytest
```

To exercise the full stack manually, run the agent with real credentials and call `/demo/chat`:

```bash
curl -s -X POST http://localhost:11000/demo/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Summarise the A2A protocol in one sentence."}' | python3 -m json.tool
```

## Learn More

- [A2A Protocol Documentation](https://a2a-protocol.org/)
- [`a2a-sdk` on PyPI](https://pypi.org/project/a2a-sdk/)
- [CodeMie A2A Integration Guide](https://github.com/epam-gen-ai-run/codemie/blob/main/docs/a2a-integration.md)
