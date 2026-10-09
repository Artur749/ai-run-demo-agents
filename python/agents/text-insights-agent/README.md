# Text Insights Agent with A2A Protocol

This sample demonstrates a text-insights agent built with [LangGraph](https://langchain-ai.github.io/langgraph/)
and exposed through the A2A protocol using the **official [`a2a-sdk`](https://pypi.org/project/a2a-sdk/)
PyPI package** instead of this repository's hand-rolled `common/server`/`common/client`/`common/types`.
It is a self-contained, standalone workspace member with zero imports from `common/`.

## How It Works

The agent is a LangGraph ReAct agent (`create_react_agent`) with a single local, credential-free tool,
`analyze_text_stats`, which computes word count, estimated reading time, and a keyword-based sentiment
signal for the input text. The model uses that tool's output to produce a short structured summary:
overall sentiment, 2-4 key points, and a suggested next step.

The agent is served over `a2a-sdk`'s own route-based server API
(`create_agent_card_routes` + `create_jsonrpc_routes`, composed onto a Starlette app and wired to a
`DefaultRequestHandler`) rather than this repo's `common/server`. This is deliberate: it demonstrates
the official SDK's own integration surface as an alternative to the repo's original A2A implementation.
See the root [`python/README.md`](../../README.md) for why both patterns coexist in this repository.

Empty or whitespace-only input, and any failure while calling the underlying LLM, are both handled
gracefully: the agent returns a structured response with `status: 'error'` instead of crashing or
hanging.

## Prerequisites

- Python 3.13 or higher
- [UV](https://docs.astral.sh/uv/)
- Access to an LLM and API Key (same credential shape as the other agents in this repo)

## Setup & Running

1. Navigate to the agent directory:

   ```bash
   cd ai-run-demo-agents/python/agents/text-insights-agent
   ```

2. Create an environment file from the shared example, then fill in real values:

   ```bash
   cp ../../.env.example .env
   ```

   Edit `.env` and replace the placeholder values with your actual credentials.

3. Run the agent:

   ```bash
   # Basic run on default port 10800
   uv run .

   # On custom host/port
   uv run . --host 127.0.0.1 --port 8080
   ```

4. With Docker:

   ```bash
   # Build docker image
   docker buildx build --build-context ai-run-agents=/path/to/ai-run-demo-agents/python/ -t text-insights-agent:latest .

   # Run docker container on the same Docker network as CodeMie.
   # --host is advertised in the Agent Card, so it must be the name CodeMie can reach this container by.
   docker run -it --name text-insights-agent --network <codemie-network> -p 10800:10800 \
     -v ./.env:/app/agents/text-insights-agent/.env \
     text-insights-agent:latest --host text-insights-agent --port 10800
   ```

   Do not use `--host 0.0.0.0`: the Agent Card would advertise `http://0.0.0.0:10800/`, which CodeMie cannot call.

## Testing

The test client provides a way to verify the agent's A2A protocol implementation against a real,
running server: it checks that the resolved agent card exposes a valid A2A surface (`name`, `skills`,
`capabilities`), that a real text input yields a non-empty structured result, and that
whitespace-only input is handled gracefully (`status: 'error'`, not a crash or hang).

### Prerequisites

- The agent server must be running (see Setup & Running section above)
- Python 3.13+ installed
- Required dependencies installed (see Setup section)

### Running Tests

   ```bash
   # From the text-insights-agent directory
   uv run test_client.py
   ```

## Technical Implementation

- **LangGraph ReAct Agent**: Uses the ReAct pattern with one local tool (`analyze_text_stats`)
- **Official `a2a-sdk`**: Uses `a2a-sdk[http-server]>=1.1.5` (the floor version resolved live via
  `uv add` at the time this agent was built) for both the agent-card and JSON-RPC routes, instead of
  this repo's own `common/server`
- **Non-streaming only**: No incremental/streaming response path — a single structured response per
  request
- **Graceful error handling**: Empty/whitespace input and LLM-call failures both return a
  `status: 'error'` structured response rather than crashing or hanging

## Limitations

- Non-streaming only (no incremental updates during processing)
- The sentiment signal produced by `analyze_text_stats` is a simple keyword heuristic, not a trained
  classifier — the model's own summary is the primary signal, the tool output is supporting context
- Only supports text-based input/output (no multi-modal support)

## Learn More

- [A2A Protocol Documentation](https://a2a-protocol.org/)
- [`a2a-sdk` on PyPI](https://pypi.org/project/a2a-sdk/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
