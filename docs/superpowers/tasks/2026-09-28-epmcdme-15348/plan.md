# Revive ai-run-demo-agents — Four Demo Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify/document `currency_converter` (complete-response demo) and `research-agent`
(streaming demo); add `text-insights-agent` (complete-response, official `a2a-sdk`) and
`howto-guide-agent` (incremental/streaming, official `a2a-sdk`) as third and fourth standalone
demos.

**Architecture:** No new architecture for agents 1/2 — both already implement `invoke()`/`stream()`;
this is verification + docs. Agent 3 is a brand-new, self-contained `uv` workspace member: a
LangGraph ReAct agent with one local credential-free tool, served over `a2a-sdk`'s own server
classes instead of this repo's hand-rolled `common/server`, with zero imports from `common/`.
Agent 4 is agent 3's streaming counterpart: same isolation model, same `a2a-sdk` package, but its
executor emits one discrete `TaskArtifactUpdateEvent` per decomposed step plus a final compiled
guide, instead of a single response.

**Tech Stack:** Python 3.13, `uv` workspaces, LangGraph (`create_react_agent`), `langchain-openai`/
Azure OpenAI, `click`, `python-dotenv`; agents 3 and 4 additionally use the official `a2a-sdk` PyPI
package for their server and client surface. Agent 4 does not use LangGraph — its LLM call is a
single direct `.with_structured_output()` call, no graph/tool needed.

**Spec:** `docs/superpowers/tasks/2026-09-28-epmcdme-15348/spec.md`

Commit per task using the repository's existing convention (imperative subject; scoped
`type(scope): summary` style is common in recent history, e.g. `docs(research-agent): ...`,
`chore(...): ...` — follow whichever fits each task, don't invent a new format).

## Global Constraints

- Dependency versions use floor constraints (`>=x.y.z`), matching every existing `pyproject.toml`
  in this repo — never pin exact/ceiling versions.
- `a2a-sdk`'s version is resolved live via `uv add a2a-sdk`, never hand-typed. Agent 4 (Task 9) may
  reuse agent 3's already-resolved constraint or re-resolve independently — either is acceptable.
- `text-insights-agent` and `howto-guide-agent` each have zero imports from `common/`, zero changes
  to `common/server`/`common/client`/`common/types` or the other four agents, and share no code
  with each other beyond independently importing `a2a-sdk`/LangChain.
- No streaming/incremental path for `text-insights-agent`; no non-streaming path required for
  `howto-guide-agent` — each demonstrates exactly one `a2a-sdk` response mode.
- No CodeMie credential, CodeMie API call, or CodeMie registration step anywhere in this work.
- All `.env`/README credential examples use placeholder values only (e.g. `your_api_key_here`).
- Agent ports: `text-insights-agent` 10800, `howto-guide-agent` 10900 (existing agents occupy
  10000/10500/10600/10700).

## Review Focus

- Empty/whitespace-only text sent to `text-insights-agent` — must return a graceful `error`-status
  result, not a crash or hang. Test added in Task 6.
- A `test_client.py` hitting a down/misconfigured agent (bad credential, agent not running) — must
  exit non-zero, not print-and-pass. Test/fix in Tasks 2, 3, 6, 10.
- `currency_converter`'s live Frankfurter API call failing or returning an unexpected shape — the
  assertion must fail rather than pass on an empty/error string. Test added in Task 3.
- A malformed or incomplete agent card (missing `skills`/`capabilities`) for `text-insights-agent`
  or `howto-guide-agent` — must fail the check explicitly, proving `a2a-sdk` actually exposes a
  valid A2A surface. Test added in Tasks 6 and 10.
- `howto-guide-agent` streaming a single response wrapped as one event (not genuinely incremental)
  — the test must count discrete content-bearing events and fail if there's only one. Test added
  in Task 10.
- `.env.example` drifting from what the READMEs tell developers to set — Task 8's root README cites
  the exact variable names Task 1 puts in `.env.example`, so they can't diverge silently.

## Note on Tasks 9-12

Tasks 1-8 were planned and implemented before agent 4 existed. `text-insights-agent`'s real,
working code (built during Task 6) uses `a2a-sdk[http-server]>=1.1.5`'s actual route-based server
API — `create_agent_card_routes`/`create_jsonrpc_routes` composed onto a Starlette app,
`a2a.helpers.new_text_message`/`get_stream_response_text`, `a2a.client.create_client` — which
differs from the `A2AStarletteApplication`/`new_agent_text_message` shape guessed in Task 6's
original code blocks before a real `a2a-sdk` install was available to verify against. Tasks 9-12
below reference the actual files `python/agents/text-insights-agent/{agent.py,__main__.py,
test_client.py}` as the verified pattern for agent 4 to adapt — follow those, not Task 6's
original code blocks.

---

### Task 1: Root `.env.example`

**Files:**
- Create: `python/.env.example`

Test-first: no — static placeholder config, nothing to drive out with a test.

- [ ] **Step 1:** Create `python/.env.example` with placeholder values for the five vars every
  agent already documents (`python/agents/research-agent/README.md:26-29`):

```
CHAT_MODEL_PROVIDER=azure
CHAT_MODEL=gpt-4o
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=your_endpoint_url
AZURE_OPENAI_API_VERSION=2024-12-01-preview
```

- [ ] **Step 2:** Commit.

---

### Task 2: Real assertions in `research-agent/test_client.py`

**Files:**
- Modify: `python/agents/research-agent/test_client.py:33-103`

Test-first: no — the script is itself the check against an already-working agent; there is no
separate implementation to drive out.

- [ ] **Step 1:** In `run_single_turn_test` (`test_client.py:33-60`), after `get_response`, assert
  `isinstance(get_response.result, Task)`, `get_response.result.status.state in ('completed',
  'input_required')`, and that the task's text (join every `TextPart.text` found across
  `result.artifacts[*].parts` and `result.status.message.parts`, if present) is a non-empty
  stripped string.
- [ ] **Step 2:** In `run_streaming_test` (`test_client.py:62-78`), collect chunks into a list,
  assert at least one chunk was received, and assert the final chunk's text content (same
  extraction as Step 1) is non-empty.
- [ ] **Step 3:** In `main` (`test_client.py:81-97`), replace the bare `except Exception` print with
  a re-raise after logging, and wrap the `asyncio.run(main())` call at the bottom
  (`test_client.py:100-103`) in `try/except (AssertionError, Exception): sys.exit(1)` so a failed
  check or connection error produces a non-zero exit, not just console output.
- [ ] **Step 4:** With the agent running locally (`uv run .` from `research-agent/`) and a valid
  `.env`, run `uv run test_client.py` and confirm exit code 0.
- [ ] **Step 5:** Commit.

---

### Task 3: `currency_converter/test_client.py`

**Files:**
- Create: `python/agents/currency_converter/test_client.py`

Test-first: no — new file mirroring Task 2's now-assertion-bearing pattern against an
already-working agent; the script is the verification artifact, not driving new agent code.

- [ ] **Step 1:** Create the file by copying the post-Task-2 `research-agent/test_client.py`
  structure (same `create_send_task_payload`, `A2ACardResolver`/`A2AClient` imports and usage)
  with these deltas:
  - `AGENT_URL = 'http://localhost:10000'`.
  - Drop `run_streaming_test` entirely — `currency_converter` is the complete-response demo, its
    script exercises only `send_task`/`get_task`.
  - Query text: `'How much is 100 USD in EUR?'`.
  - Add an `extract_text(task: Task) -> str` helper that joins every `TextPart.text` found in
    `task.artifacts[*].parts` and `task.status.message.parts` (if present).
  - After the `get_task` call: `assert task.status.state in ('completed', 'input_required')`;
    `text = extract_text(task); assert text` (non-empty); `assert any(ch.isdigit() for ch in
    text)` — proves the response actually contains an exchange-rate figure, not just any text, so
    a Frankfurter-API failure surfaced as an error message still fails the check.
  - Wrap `asyncio.run(main())` the same way Task 2 does: catch `(AssertionError, Exception)`,
    print the error, `sys.exit(1)`.
- [ ] **Step 2:** With the agent running locally (`uv run .` from `currency_converter/`) and a
  valid `.env`, run `uv run test_client.py` and confirm exit code 0.
- [ ] **Step 3:** Commit.

---

### Task 4: Point agents 1/2 READMEs at the root `.env.example`, add Testing section

**Files:**
- Modify: `python/agents/currency_converter/README.md:65-72,105`
- Modify: `python/agents/research-agent/README.md:23-30`

Test-first: no — documentation only.

- [ ] **Step 1:** In `research-agent/README.md`, replace the `echo "..." > .env` block
  (lines 25-29) with `cp ../../.env.example .env` plus a one-line note to fill in real values —
  points at Task 1's file instead of duplicating placeholders inline.
- [ ] **Step 2:** In `currency_converter/README.md`, replace the equivalent `echo` block
  (lines 68-71) the same way.
- [ ] **Step 3:** In `currency_converter/README.md`, insert a new `## Testing` section before
  `## Limitations` (currently line 105), mirroring `research-agent/README.md:52-68`'s structure:
  prerequisites (agent running, deps installed) and `uv run test_client.py` from the agent
  directory.
- [ ] **Step 4:** Commit.

---

### Task 5: Scaffold `text-insights-agent` package (deps, workspace membership, Docker)

**Files:**
- Create: `python/agents/text-insights-agent/pyproject.toml`
- Create: `python/agents/text-insights-agent/Dockerfile`
- Modify: `python/pyproject.toml:27-32`

Test-first: no — packaging/config, verified by `uv sync` succeeding, not a unit test.

- [ ] **Step 1:** Create `pyproject.toml`:

```toml
[project]
name = "text-insights-agent"
version = "0.1.0"
description = "Sample LangGraph text-insights agent built on the official a2a-sdk"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "click>=8.1.8",
    "langchain-openai>=0.2.14",
    "langgraph>=0.4.1",
    "pydantic>=2.10.6",
    "python-dotenv>=1.1.0",
    "uvicorn>=0.34.0",
]

[tool.hatch.build.targets.wheel]
packages = ["."]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 2:** From `python/agents/text-insights-agent/`, run `uv add a2a-sdk`. This resolves
  the actual current floor version and appends it to `dependencies` — do not hand-type a version.
  Note the resolved constraint for Task 7's README.
- [ ] **Step 3:** Add `"agents/text-insights-agent",` to the `members` list in
  `python/pyproject.toml:27-32`, alongside the existing four.
- [ ] **Step 4:** Create `Dockerfile`, same multi-stage pattern as
  `python/agents/currency_converter/Dockerfile:1-27`, substituting the directory name
  (`text-insights-agent`) and default port (`10800`) in the `COPY . /app/agents/...` and final
  `CMD` lines; keep the `common/`/root-`pyproject.toml`/`uv.lock` copy steps for consistency with
  the sibling Dockerfiles even though this agent doesn't import `common/` — the workspace-level
  `uv sync` still expects them present.
- [ ] **Step 5:** Run `uv sync` from `python/` to confirm the new workspace member resolves.
- [ ] **Step 6:** Commit.

---

### Task 6: Implement `text-insights-agent` agent + server + test client

**Files:**
- Create: `python/agents/text-insights-agent/agent.py`
- Create: `python/agents/text-insights-agent/__main__.py`
- Create: `python/agents/text-insights-agent/test_client.py`

**Interfaces:**
- Produces: `TextInsightsAgent` (`agent.py`) with `SUPPORTED_CONTENT_TYPES: list[str]` and
  `invoke(text: str) -> InsightsResponse`, where `InsightsResponse` has fields `status`
  (`'completed'|'error'`), `sentiment: str`, `key_points: list[str]`, `suggested_next_step: str`.

Test-first: yes — `test_client.py` is written first and asserts (a) the agent card is A2A-schema
valid (`name`, `skills`, `capabilities` present) and (b) a real text input yields a non-empty
result; both fail until `agent.py`/`__main__.py` exist and run.

- [ ] **Step 1: Write `test_client.py` (fails — no server yet)**

```python
import asyncio
import sys

import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import MessageSendParams, SendMessageRequest

AGENT_URL = 'http://localhost:10800'

async def check_agent_card(httpx_client: httpx.AsyncClient):
    card = await A2ACardResolver(httpx_client, AGENT_URL).get_agent_card()
    assert card.name, 'agent card missing name'
    assert card.skills, 'agent card missing skills'
    assert card.capabilities is not None, 'agent card missing capabilities'
    return card

async def send_text(client: A2AClient, text: str) -> str:
    request = SendMessageRequest(params=MessageSendParams(
        message={'role': 'user', 'parts': [{'kind': 'text', 'text': text}]}))
    response = await client.send_message(request)
    return response.model_dump_json()

async def main() -> None:
    async with httpx.AsyncClient(timeout=60) as httpx_client:
        card = await check_agent_card(httpx_client)
        client = A2AClient(httpx_client, agent_card=card)
        result = await send_text(
            client, 'Customer says the checkout page keeps freezing on mobile, very frustrating.'
        )
        assert result and result.strip(), 'expected a non-empty result'
        print(f'OK (real input): {result}')
        empty = await send_text(client, '   ')
        assert empty is not None, 'agent did not handle empty input gracefully'
        print(f'OK (empty input handled): {empty}')

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except AssertionError as exc:
        print(f'CHECK FAILED: {exc}')
        sys.exit(1)
```

  Note: `a2a-sdk`'s exact client class/method signatures for this task's resolved version aren't
  verifiable from this planning stage (no live PyPI/docs access) — confirm against the installed
  package's own quickstart/example once `uv add a2a-sdk` has run, and adjust import paths/
  parameter names if this version differs.

- [ ] **Step 2: Run to confirm it fails** — `uv run test_client.py` with nothing listening on
  `:10800` should fail with a connection error.

- [ ] **Step 3: Implement `agent.py`**

```python
import os
import re
from typing import Literal

from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langchain_openai import AzureChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

POSITIVE = {"great", "good", "excellent", "love", "happy", "satisfied", "thanks", "resolved"}
NEGATIVE = {"bad", "terrible", "hate", "angry", "frustrated", "broken", "disappointed", "issue"}

def _create_chat_model():
    """Standalone factory — no dependency on common/."""
    name, provider = os.getenv('CHAT_MODEL', 'gpt-4o'), os.getenv('CHAT_MODEL_PROVIDER', 'openai')
    if provider == 'azure':
        endpoint, version = os.getenv('AZURE_OPENAI_ENDPOINT'), os.getenv('AZURE_OPENAI_API_VERSION')
        if not endpoint or not version:
            raise ValueError('AZURE_OPENAI_ENDPOINT/AZURE_OPENAI_API_VERSION required for azure provider.')
        return AzureChatOpenAI(azure_endpoint=endpoint, azure_deployment=name, openai_api_version=version)
    return init_chat_model(model=name, model_provider=provider)

@tool
def analyze_text_stats(text: str) -> dict:
    """Word count, reading time (min), keyword-based sentiment for a text block."""
    words = text.split()
    if not words:
        return {'word_count': 0, 'reading_time_minutes': 0.0, 'sentiment_signal': 'neutral'}
    lowered = {re.sub(r'[^a-z]', '', w.lower()) for w in words}
    pos, neg = len(lowered & POSITIVE), len(lowered & NEGATIVE)
    signal = 'positive' if pos > neg else 'negative' if neg > pos else 'neutral'
    return {'word_count': len(words), 'reading_time_minutes': round(len(words) / 200, 2), 'sentiment_signal': signal}

class InsightsResponse(BaseModel):
    status: Literal['completed', 'error'] = 'completed'
    sentiment: str
    key_points: list[str]
    suggested_next_step: str

SYSTEM_INSTRUCTION = (
    "Use 'analyze_text_stats' for objective stats, then produce a short structured summary: "
    "sentiment, 2-4 key_points, suggested_next_step. status='error' only for empty/unusable input."
)

class TextInsightsAgent:
    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        self.graph = create_react_agent(
            _create_chat_model(), tools=[analyze_text_stats],
            prompt=SYSTEM_INSTRUCTION, response_format=InsightsResponse,
        )

    def invoke(self, text: str) -> InsightsResponse:
        result = self.graph.invoke({'messages': [('user', text)]})
        return result['structured_response']
```

- [ ] **Step 4: Implement `__main__.py`**

```python
import logging

import click
import uvicorn
from dotenv import load_dotenv

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message

from agent import TextInsightsAgent

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TextInsightsExecutor(AgentExecutor):
    def __init__(self):
        self.agent = TextInsightsAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        result = self.agent.invoke(context.get_user_input())
        summary = (f'Sentiment: {result.sentiment}\n'
                   f"Key points: {'; '.join(result.key_points)}\n"
                   f'Suggested next step: {result.suggested_next_step}')
        await event_queue.enqueue_event(new_agent_text_message(summary))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError('Cancellation is not supported.')

@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=10800)
def main(host, port):
    skill = AgentSkill(
        id='analyze_text_insights', name='Text Insights Tool',
        description='Summarizes sentiment, key points, and a suggested next step for a block of free text.',
        tags=['text analysis', 'sentiment'],
        examples=['Customer says the checkout page keeps freezing on mobile.'],
    )
    agent_card = AgentCard(
        name='Text Insights Agent',
        description='Turns free text (e.g. feedback or a support ticket) into a structured insight summary.',
        url=f'http://{host}:{port}/', version='1.0.0',
        defaultInputModes=TextInsightsAgent.SUPPORTED_CONTENT_TYPES,
        defaultOutputModes=TextInsightsAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=AgentCapabilities(streaming=False), skills=[skill],
    )
    handler = DefaultRequestHandler(agent_executor=TextInsightsExecutor(), task_store=InMemoryTaskStore())
    app = A2AStarletteApplication(agent_card=agent_card, http_handler=handler)
    logger.info(f'Starting text-insights-agent on {host}:{port}')
    uvicorn.run(app.build(), host=host, port=port)

if __name__ == '__main__':
    main()
```

  Note: same caveat as Step 1 — confirm `a2a.server.*`/`a2a.types` import paths and
  `AgentExecutor`/`RequestContext`/`EventQueue` signatures against the resolved package version;
  this is the standard `a2a-sdk` executor pattern as of this plan's authoring, adjust if changed.

- [ ] **Step 5: Run to confirm it passes** — start the agent (`uv run .` from
  `text-insights-agent/`, valid `.env` present), then `uv run test_client.py`; confirm exit 0 and
  both the real-input and empty-input checks print `OK`.

- [ ] **Step 6:** Commit.

---

### Task 7: `text-insights-agent/README.md`

**Files:**
- Create: `python/agents/text-insights-agent/README.md`

Test-first: no — documentation.

- [ ] **Step 1:** Write the README with sections **How It Works** (LangGraph ReAct agent + local
  `analyze_text_stats` tool, served via the official `a2a-sdk` package instead of this repo's
  hand-rolled `common/server`), **Prerequisites** (Python 3.13+, `uv`, LLM credential — same as
  other agents), **Setup & Running** (`cp ../../.env.example .env` then fill in real values,
  `uv run .` on default port 10800, `--host`/`--port` options), **Testing** (`uv run
  test_client.py` from this directory, requires only the agent's own LLM credential), and
  **Limitations** (non-streaming only; sentiment signal is a simple keyword heuristic, not a
  trained classifier). State the exact `a2a-sdk` version resolved in Task 5, Step 2.
- [ ] **Step 2:** Commit.

---

### Task 8: Root `python/README.md`

**Files:**
- Modify: `python/README.md`

Test-first: no — documentation.

- [ ] **Step 1:** Rewrite the `## Agents` section (currently only documents the currency agent,
  `python/README.md:5-23`) to list all three demo agents: `currency_converter` (port 10000,
  **complete-response** demo), `research-agent` (port 10700, **incremental/streaming** demo), and
  `text-insights-agent` (port 10800, non-streaming). For each: one-line description, `.env` setup
  pointing at `python/.env.example`, start command (`uv run .` from the agent directory), and
  check-script command (`uv run test_client.py`).
- [ ] **Step 2:** Fix `## Getting Started` (`python/README.md:25-31`) — remove the nonexistent
  `python/agents/langgraph` path reference.
- [ ] **Step 3:** Add a **Known Limitations** section listing `financial-agent` (fails to install:
  `yfinance`→`curl_cffi` has no prebuilt wheel for this platform, requires a C++ build toolchain)
  and `fun-with-rick` (system prompt references a `tavily_search_tool` that is never registered —
  no live Tavily integration exists) as untouched, known-broken/incomplete by this task.
  Fixing either is out of scope.
- [ ] **Step 4:** Add a short note explaining the repo now has two parallel A2A implementations by
  design: `currency_converter`/`research-agent`/`financial-agent`/`fun-with-rick` use this repo's
  hand-rolled `common/server`/`common/client`/`common/types`, while `text-insights-agent` uses the
  official `a2a-sdk` package directly, isolated to its own package — so a reader doesn't mistake
  the split for drift.
- [ ] **Step 5:** Commit.

---

### Task 9: Scaffold `howto-guide-agent` package (deps, workspace membership, Docker)

**Files:**
- Create: `python/agents/howto-guide-agent/pyproject.toml`
- Create: `python/agents/howto-guide-agent/Dockerfile`
- Modify: `python/pyproject.toml:38-45`

Test-first: no — packaging/config, verified by `uv sync` succeeding, not a unit test.

- [ ] **Step 1:** Create `pyproject.toml` mirroring
  `python/agents/text-insights-agent/pyproject.toml:1-22`, with these deltas:
  `name = "howto-guide-agent"`, an updated `description`, and drop `langgraph` from
  `dependencies` — this agent calls its chat model directly via `.with_structured_output()` (see
  Task 10), no LangGraph graph/tool. Keep `a2a-sdk[http-server]>=1.1.5` (text-insights-agent's
  already-resolved constraint, `python/agents/text-insights-agent/pyproject.toml:8`); reusing it
  is acceptable per spec, or run `uv add a2a-sdk` in this new directory to independently
  re-resolve/confirm.
- [ ] **Step 2:** Add `"agents/howto-guide-agent",` to the `members` list in
  `python/pyproject.toml:38-45`, alongside the existing five.
- [ ] **Step 3:** Create `Dockerfile` by copying
  `python/agents/text-insights-agent/Dockerfile:1-28` verbatim except: substitute
  `text-insights-agent` → `howto-guide-agent` in the `COPY . /app/agents/...` and `WORKDIR`
  lines, and `10800` → `10900` in the final `CMD`.
- [ ] **Step 4:** Run `uv sync` from `python/` to confirm the new workspace member resolves.
- [ ] **Step 5:** Commit.

---

### Task 10: Implement `howto-guide-agent` agent + streaming server + test client

**Files:**
- Create: `python/agents/howto-guide-agent/agent.py`
- Create: `python/agents/howto-guide-agent/__main__.py`
- Create: `python/agents/howto-guide-agent/test_client.py`

**Interfaces:**
- Produces: `HowToGuideAgent` (`agent.py`) with `SUPPORTED_CONTENT_TYPES: list[str]` and
  `invoke(goal: str) -> GuideResponse`, where `GuideResponse` has fields `status`
  (`'completed'|'error'`), `steps: list[str]` (3-8 ordered items when `status='completed'`),
  `summary: str`.

Test-first: yes — `test_client.py` is written first and asserts (a) the agent card is schema-valid
and advertises `capabilities.streaming`, (b) sending one real goal via the streaming path yields
more than one discrete content-bearing event before completion, and (c) the final event's compiled
guide text is non-empty; all three fail until `agent.py`/`__main__.py` exist and actually stream.

Reference implementation: `python/agents/text-insights-agent/{agent.py,__main__.py,
test_client.py}` — real, working code against the installed `a2a-sdk[http-server]>=1.1.5`. Adapt
it; do not reintroduce Task 6's original (pre-install, guessed-API) code shape.

- [ ] **Step 1: Write `test_client.py` (fails — no server yet).** Copy
  `python/agents/text-insights-agent/test_client.py:1-11,29-33,47-62` verbatim (imports,
  `httpx.AsyncClient`/`A2ACardResolver`/`create_client` setup, the `try/finally: await
  client.close()` shape, the top-level `AssertionError`/`Exception` → `sys.exit(1)` wrapper).
  Replace the rest with:

```python
AGENT_URL = 'http://localhost:10900'


async def check_agent_card(httpx_client: httpx.AsyncClient):
    card = await A2ACardResolver(httpx_client, AGENT_URL).get_agent_card()
    assert card.name, 'agent card missing name'
    assert card.skills, 'agent card missing skills'
    assert card.capabilities is not None, 'agent card missing capabilities'
    assert card.capabilities.streaming, 'agent card must advertise streaming capability'
    return card


async def send_goal(client, goal: str) -> list:
    request = SendMessageRequest(message=new_text_message(goal))
    chunks = [chunk async for chunk in client.send_message(request)]
    assert chunks, 'expected at least one response chunk'
    return chunks
```

  and, inside `main()`'s `try` block (in place of `text-insights-agent/test_client.py:34-46`'s
  body):

```python
        chunks = await send_goal(client, 'Set up a home Wi-Fi router.')
        content_chunks = [c for c in chunks if get_stream_response_text(c).strip()]
        assert len(content_chunks) > 1, (
            f'expected genuinely incremental output (>1 content-bearing event), '
            f'got {len(content_chunks)}'
        )
        final_text = get_stream_response_text(content_chunks[-1]).strip()
        assert final_text, 'expected a non-empty final compiled guide'
        print(f'OK ({len(content_chunks)} incremental events): {final_text}')
```

- [ ] **Step 2: Run to confirm it fails** — `uv run test_client.py` with nothing listening on
  `:10900` should fail with a connection error.

- [ ] **Step 3: Implement `agent.py`.** Copy the `_create_chat_model()` factory verbatim from
  `python/agents/text-insights-agent/agent.py:19-40` (same env-var contract; duplicated, not
  imported — agents 3 and 4 share no code per spec), plus the `logging`/`logger =
  logging.getLogger(__name__)` lines from `text-insights-agent/agent.py:1,11`. Drop the
  `langgraph`/`langchain_core.tools` imports and the `@tool`-decorated function entirely — this
  agent has no local tool. Add (needs `Field`, `model_validator` in the `pydantic` import):

```python
class GuideResponse(BaseModel):
    status: Literal['completed', 'error'] = 'completed'
    steps: list[str] = Field(
        default_factory=list,
        description="3-8 ordered, concrete steps when status is 'completed'; empty when 'error'.",
    )
    summary: str

    @model_validator(mode='after')
    def _enforce_steps_range(self) -> 'GuideResponse':
        if self.status == 'completed' and not (3 <= len(self.steps) <= 8):
            raise ValueError(f'steps must contain 3-8 items when status is completed, got {len(self.steps)}')
        return self


SYSTEM_INSTRUCTION = (
    "Decompose the user's goal into 3-8 ordered, concrete steps, then write a one-sentence "
    "summary of the resulting guide. status='error' only for an empty/unusable goal."
)


class HowToGuideAgent:
    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        self.model = _create_chat_model().with_structured_output(GuideResponse)

    def invoke(self, goal: str) -> GuideResponse:
        if not goal or not goal.strip():
            return GuideResponse(status='error', steps=[], summary='Provide a non-empty goal to plan.')
        try:
            return self.model.invoke([('system', SYSTEM_INSTRUCTION), ('user', goal)])
        except Exception:
            logger.exception('Failed to generate how-to guide with the LLM')
            return GuideResponse(status='error', steps=[], summary='Unable to generate a guide right now; please try again later.')
```

- [ ] **Step 4: Implement `__main__.py`.** Copy
  `python/agents/text-insights-agent/__main__.py:1-21` (imports, `load_dotenv()`/logging setup)
  and the `@click.command()` options / `AgentSkill`/`AgentCard`/`DefaultRequestHandler`/
  route-composition/`uvicorn.run` shape in `main()` (`__main__.py:45-84`), with these deltas: port
  default `10900`; `capabilities=AgentCapabilities(streaming=True)`; a new `AgentSkill`/`AgentCard`
  id/name/description for the how-to-guide use case; swap the `TextInsightsAgent` import/class
  name for `HowToGuideAgent`. Add `TaskState` to the `a2a.types` import, and
  `new_task_from_user_message`, `new_text_artifact_update_event`, `new_text_status_update_event`
  to an `a2a.helpers` import (in place of `__main__.py:8`'s single `new_text_message` import).
  Replace the executor's `execute()` body (`__main__.py:28-36`) with:

```python
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = new_task_from_user_message(context.message)
        await event_queue.enqueue_event(task)

        result = self.agent.invoke(context.get_user_input())
        if result.status == 'error':
            await event_queue.enqueue_event(new_text_status_update_event(
                task.id, task.context_id, TaskState.TASK_STATE_FAILED, result.summary,
            ))
            return

        for i, step in enumerate(result.steps, start=1):
            await event_queue.enqueue_event(new_text_artifact_update_event(
                task.id, task.context_id, name=f'step-{i}', text=f'{i}. {step}',
                artifact_id=f'step-{i}', append=False, last_chunk=True,
            ))

        numbered = '\n'.join(f'{i}. {s}' for i, s in enumerate(result.steps, start=1))
        await event_queue.enqueue_event(new_text_artifact_update_event(
            task.id, task.context_id, name='guide', text=f'{result.summary}\n\n{numbered}',
            artifact_id='guide', append=False, last_chunk=True,
        ))
        await event_queue.enqueue_event(new_text_status_update_event(
            task.id, task.context_id, TaskState.TASK_STATE_COMPLETED, 'Guide complete.',
        ))
```

  Keep `cancel()` unchanged from `__main__.py:38-42` (same `UnsupportedOperationError` pattern).

- [ ] **Step 5: Run to confirm it passes** — start the agent (`uv run .` from
  `howto-guide-agent/`, valid `.env` present), then `uv run test_client.py`; confirm exit 0 and
  the printed incremental-event count is greater than 1.

- [ ] **Step 6:** Commit.

---

### Task 11: `howto-guide-agent/README.md`

**Files:**
- Create: `python/agents/howto-guide-agent/README.md`

Test-first: no — documentation.

- [ ] **Step 1:** Write the README mirroring `python/agents/text-insights-agent/README.md`'s
  structure and tone, with these content deltas: **How It Works** describes goal decomposition
  (one structured-output LLM call produces 3-8 ordered steps) streamed to the client as one
  discrete `TaskArtifactUpdateEvent` per step, followed by a final compiled-guide artifact and a
  `TASK_STATE_COMPLETED` status event — note explicitly that this is agent 3's streaming
  counterpart on the same `a2a-sdk`. **Prerequisites**/**Setup & Running** identical shape, port
  10900. **Testing** describes the incremental-event assertion (more than one discrete
  content-bearing event before completion, non-empty final guide). **Limitations**:
  streaming-only (no non-streaming path — that's agent 3's role); the step list is produced by one
  LLM call and then emitted incrementally, not generated one step at a time live. State the
  `a2a-sdk` version in use (reused or re-resolved per Task 9, Step 1).
- [ ] **Step 2:** Commit.

---

### Task 12: Root `python/README.md` — add the fourth agent

**Files:**
- Modify: `python/README.md:7`
- Modify: `python/README.md:36-51` (insert after the existing entry 3)
- Modify: `python/README.md:69-70`

Test-first: no — documentation.

- [ ] **Step 1:** At `python/README.md:7`, change "Three agents are actively maintained..." to
  "Four agents are actively maintained...".
- [ ] **Step 2:** Immediately after the existing entry 3 (`text-insights-agent`, ending at
  `python/README.md:50`), insert a new entry `### 4. How-To Guide Agent (\`howto-guide-agent\`) —
  incremental/streaming, official \`a2a-sdk\`` (port 10900), matching entries 1-3's
  Prerequisites/Setup/Run/Check bullet structure, stating it is the streaming counterpart to
  `text-insights-agent` on the same `a2a-sdk` package.
- [ ] **Step 3:** In `## Two A2A Implementations, By Design`, update the `a2a-sdk` bullet
  (`python/README.md:69-70`) to list both `text-insights-agent` and `howto-guide-agent`.
- [ ] **Step 4:** Add a short summary table right after the "Four agents..." sentence from Step 1,
  covering all four agents' response mode and implementation:

```markdown
| Agent                  | Response mode          | Implementation        |
|------------------------|-------------------------|------------------------|
| `currency_converter`   | Complete-response       | Hand-rolled `common/`  |
| `research-agent`       | Incremental/streaming   | Hand-rolled `common/`  |
| `text-insights-agent`  | Complete-response        | Official `a2a-sdk`     |
| `howto-guide-agent`    | Incremental/streaming    | Official `a2a-sdk`     |
```

- [ ] **Step 5:** Commit.
