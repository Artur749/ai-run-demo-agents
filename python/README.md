# AI Run Demo Agents

This repository contains a collection of AI agents built with different frameworks and architectures, designed to demonstrate various capabilities and integration patterns of the [A2A protocol](https://a2a-protocol.org/).

## Agents

Four agents are actively maintained as working demos, each showcasing a different A2A interaction pattern.

| Agent                    | Response mode          | Implementation       |
|--------------------------|------------------------|----------------------|
| `currency_converter`     | Complete-response      | Hand-rolled `common/` |
| `research-agent`         | Incremental/streaming  | Hand-rolled `common/` |
| `text-insights-agent`    | Complete-response      | Official `a2a-sdk`   |
| `howto-guide-agent`      | Incremental/streaming  | Official `a2a-sdk`   |
| `codemie-caller-agent`   | Complete-response      | Official `a2a-sdk`   |

### 1. LangGraph Currency Agent (`currency_converter`) — complete-response demo

**Location:** `/python/agents/currency_converter` · **Port:** 10000

A currency conversion agent built with LangGraph that provides real-time exchange rate information
via the Frankfurter API. Demonstrates the **complete-response** (`tasks/send`/`tasks/get`) pattern,
plus multi-turn conversations and an optional streaming path.

- **Prerequisites:** Python 3.13+, [UV](https://docs.astral.sh/uv/), and an LLM credential (Azure
  OpenAI or OpenAI — see `python/.env.example`).
- **Setup:** `cp ../../.env.example .env` from the agent directory, then fill in real credentials.
- **Run:** `uv run .` from `python/agents/currency_converter` (default port 10000).
- **Check:** `uv run test_client.py` from the same directory.

### 2. Research Agent (`research-agent`) — incremental/streaming demo

**Location:** `/python/agents/research-agent` · **Port:** 10700

A research agent built with LangGraph, showcasing the **incremental/streaming**
(`tasks/sendSubscribe`) A2A pattern with real-time status updates as the agent works.

- **Prerequisites:** Python 3.13+, [UV](https://docs.astral.sh/uv/), and an LLM credential (Azure
  OpenAI or OpenAI — see `python/.env.example`).
- **Setup:** `cp ../../.env.example .env` from the agent directory, then fill in real credentials.
- **Run:** `uv run .` from `python/agents/research-agent` (default port 10700).
- **Check:** `uv run test_client.py` from the same directory.

### 3. Text Insights Agent (`text-insights-agent`) — non-streaming, official `a2a-sdk`

**Location:** `/python/agents/text-insights-agent` · **Port:** 10800

A LangGraph ReAct agent with one local, credential-free tool that summarizes sentiment, key points,
and a suggested next step for a block of free text (e.g. customer feedback or a support ticket).
Non-streaming only. Unlike the other agents here, it is served using the **official `a2a-sdk` PyPI
package** rather than this repository's own `common/server`. See [Two A2A
Implementations](#two-a2a-implementations-by-design) below.

- **Prerequisites:** Python 3.13+, [UV](https://docs.astral.sh/uv/), and an LLM credential (Azure
  OpenAI or OpenAI — see `python/.env.example`).
- **Setup:** `cp ../../.env.example .env` from the agent directory, then fill in real credentials.
- **Run:** `uv run .` from `python/agents/text-insights-agent` (default port 10800).
- **Check:** `uv run test_client.py` from the same directory.

### 5. CodeMie Caller Agent (`codemie-caller-agent`) — multi-hop demo, official `a2a-sdk`

**Location:** `/python/agents/codemie-caller-agent` · **Port:** 11000

A proxy agent with no LLM of its own. It accepts a user message via A2A `SendMessage` (or via a
plain HTTP `/demo/chat` endpoint for demo UIs), forwards it to a configured CodeMie assistant via
**A2A v1.0**, and returns the response together with a 4-step wire trace that makes every protocol
hop visible. Designed for the multi-hop demo scenario: external client → this agent → CodeMie (via
A2A) → CodeMie assistant.

Unlike the other agents, no LLM credentials are needed — only CodeMie instance credentials
(`CM_BASE_URL`, `CM_ASSISTANT_ID`, `CM_AUTH_TOKEN`).

- **Prerequisites:** Python 3.13+, [UV](https://docs.astral.sh/uv/), and a running CodeMie instance.
- **Setup:** `cp .env.example .env` from the agent directory, then fill in real credentials.
- **Run:** `uv run .` from `python/agents/codemie-caller-agent` (default port 11000).
- **Check:** `curl -s -X POST http://localhost:11000/demo/chat -H "Content-Type: application/json" -d '{"message":"hello"}' | python3 -m json.tool`

### 4. How-To Guide Agent (`howto-guide-agent`) — incremental/streaming, official `a2a-sdk`

**Location:** `/python/agents/howto-guide-agent` · **Port:** 10900

Decomposes a free-text goal into an ordered, concrete step-by-step guide, streaming one event per
step followed by a compiled guide and a completion status. This is `text-insights-agent`'s
**streaming counterpart** on the same official `a2a-sdk` package. See [Two A2A
Implementations](#two-a2a-implementations-by-design) below.

- **Prerequisites:** Python 3.13+, [UV](https://docs.astral.sh/uv/), and an LLM credential (Azure
  OpenAI or OpenAI — see `python/.env.example`).
- **Setup:** `cp ../../.env.example .env` from the agent directory, then fill in real credentials.
- **Run:** `uv run .` from `python/agents/howto-guide-agent` (default port 10900).
- **Check:** `uv run test_client.py` from the same directory.

## Getting Started

Each agent directory contains its own README with specific setup instructions and examples. To run an
agent:

1. Navigate to the agent directory (e.g., `cd python/agents/research-agent`)
2. Follow the setup instructions in the agent's README — in short, `cp ../../.env.example .env` and
   fill in real credentials
3. Run the agent using `uv run .`
4. Verify it works with `uv run test_client.py`

## Two A2A Implementations, By Design

This repository intentionally contains two parallel ways of implementing an A2A agent:

- `currency_converter`, `research-agent`, `financial-agent`, and `fun-with-rick` use this repository's
  own hand-rolled `common/server`, `common/client`, and `common/types` modules.
- `text-insights-agent` and `howto-guide-agent` use the **official `a2a-sdk` PyPI package** directly,
  each isolated entirely to its own package (zero imports from `common/`, zero changes to it).

This split is deliberate, not drift: it lets the repository demonstrate both "build your own A2A
plumbing" and "use the official SDK" side by side.

## Known Limitations

Two existing agents are untouched and known-broken/incomplete as of this revival work. Fixing either
was out of scope here.

- **`financial-agent`** (port 10500) fails to install in most environments: it depends on `yfinance`,
  which pulls in `curl_cffi`, which has no prebuilt wheel for many Python/platform combinations and
  requires a C++ build toolchain to compile from source.
- **`fun-with-rick`** (port 10600) has a dead tool reference: its system prompt instructs the model to
  use a `'tavily_search_tool'` tool, but no such tool is ever registered (`self.tools = []`), and no
  live Tavily integration exists in the codebase.

## Contributing

To add a new agent to this collection:
1. Create a new directory under `/python/agents/` or `/<you_language>/agents`
2. Include a comprehensive README.md with capabilities and examples
3. Ensure the agent follows the established patterns for integration

## License

MIT License
