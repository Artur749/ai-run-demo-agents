# How-To Guide Agent with A2A Protocol

This sample demonstrates a how-to-guide agent exposed through the A2A protocol using the **official
[`a2a-sdk`](https://pypi.org/project/a2a-sdk/) PyPI package** instead of this repository's hand-rolled
`common/server`/`common/client`/`common/types`. It is the **streaming counterpart** to
[`text-insights-agent`](../text-insights-agent/README.md) on that same SDK — both are self-contained,
standalone workspace members with zero imports from `common/`.

## How It Works

The agent makes a single structured-output LLM call (`.with_structured_output()`, no LangGraph
graph or tool) that decomposes the user's goal into 3-8 ordered, concrete steps plus a one-sentence
summary. Unlike `text-insights-agent`'s single complete response, that result is then **streamed** to
the client as a sequence of discrete `a2a-sdk` events: one `TaskArtifactUpdateEvent` per step, a final
`guide` artifact holding only the one-sentence summary (the steps are not repeated), and a
`TaskState.TASK_STATE_COMPLETED` status event. The step list itself is produced by one LLM call and
then emitted incrementally — it is not generated one step at a time live.

The agent is served over `a2a-sdk`'s own route-based server API (`create_agent_card_routes` +
`create_jsonrpc_routes`, composed onto a Starlette app and wired to a `DefaultRequestHandler`) rather
than this repo's `common/server`. See the root [`python/README.md`](../../README.md) for why both
`common/`-based and `a2a-sdk`-based patterns coexist in this repository.

An empty or unusable goal, and any failure while calling the underlying LLM, are both handled
gracefully: the agent returns a structured response with `status: 'error'` instead of crashing or
hanging.

## Prerequisites

- Python 3.13 or higher
- [UV](https://docs.astral.sh/uv/)
- Access to an LLM and API Key (same credential shape as the other agents in this repo)

## Setup & Running

1. Navigate to the agent directory:

   ```bash
   cd ai-run-demo-agents/python/agents/howto-guide-agent
   ```

2. Create an environment file from the shared example, then fill in real values:

   ```bash
   cp ../../.env.example .env
   ```

   Edit `.env` and replace the placeholder values with your actual credentials.

3. Run the agent:

   ```bash
   # Basic run on default port 10900
   uv run .

   # On custom host/port
   uv run . --host 127.0.0.1 --port 8080
   ```

4. With Docker:

   ```bash
   # Build docker image
   docker buildx build --build-context ai-run-agents=/path/to/ai-run-demo-agents/python/ -t howto-guide-agent:latest .

   # Run docker container on the same Docker network as CodeMie.
   # --host is advertised in the Agent Card, so it must be the name CodeMie can reach this container by.
   docker run -it --name howto-guide-agent --network <codemie-network> -p 10900:10900 \
     -v ./.env:/app/agents/howto-guide-agent/.env \
     howto-guide-agent:latest --host howto-guide-agent --port 10900
   ```

   Do not use `--host 0.0.0.0`: the Agent Card would advertise `http://0.0.0.0:10900/`, which CodeMie cannot call.

## Testing

The test client provides a way to verify the agent's A2A protocol implementation against a real,
running server: it checks that the resolved agent card is schema-valid and advertises
`capabilities.streaming`, and that sending one real goal via the streaming path yields **more than one
discrete content-bearing event** before completion — proving the response is genuinely incremental,
not a single message dressed up as a stream — with a non-empty final compiled guide.

### Prerequisites

- The agent server must be running (see Setup & Running section above)
- Python 3.13+ installed
- Required dependencies installed (see Setup section)

### Running Tests

   ```bash
   # From the howto-guide-agent directory
   uv run test_client.py
   ```

## Technical Implementation

- **Single structured-output LLM call**: `.with_structured_output(GuideResponse)` — no LangGraph
  graph or tool, unlike `text-insights-agent`
- **Official `a2a-sdk`**: Uses `a2a-sdk[http-server]>=1.1.5` (reusing `text-insights-agent`'s
  already-resolved floor constraint, per spec) for both the agent-card and JSON-RPC routes, instead of
  this repo's own `common/server`
- **Streaming only**: `capabilities.streaming=True`; every response is emitted incrementally via
  `new_task_from_user_message`, `new_text_artifact_update_event`, and `new_text_status_update_event`
- **Graceful error handling**: An empty/unusable goal and LLM-call failures both return a
  `status: 'error'` structured response rather than crashing or hanging

## Limitations

- Streaming only (no non-streaming path — that is `text-insights-agent`'s role)
- The step list is produced by one LLM call and then emitted incrementally, not generated one step at
  a time live
- Only supports text-based input/output (no multi-modal support)

## Learn More

- [A2A Protocol Documentation](https://a2a-protocol.org/)
- [`a2a-sdk` on PyPI](https://pypi.org/project/a2a-sdk/)
