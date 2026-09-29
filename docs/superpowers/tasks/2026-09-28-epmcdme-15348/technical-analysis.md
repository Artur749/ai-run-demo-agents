# Technical Research

**Task**: agents streaming demo config
**Generated**: 2026-09-28
**Research path**: filesystem

---

## 1. Original Context

Ticket EPMCDME-15348: Revive the demo agents repository and create test agents.

Description:
Restore ai-run-demo-agents to a working state and prepare a small set of agents based on existing examples or simple business use cases. The agents must run independently and produce verifiable results. Include one agent capable of incremental output and one that returns a complete response.

Acceptance criteria:
1. At least two agents can be configured and started using documented commands.
2. Each agent accepts an input, executes its own logic, and returns a meaningful result.
3. One agent supports incremental output; the other returns a complete response.
4. Basic checks demonstrate that both agents work without CodeMie.
5. Configuration examples contain no real credentials.
6. The repository README explains how to run and try each agent.

Scope: No A2A implementation or CodeMie integration in this task.

---

## 2. Codebase Findings

### Existing Implementations

The repo is a `uv` workspace at `python/` with root `pyproject.toml` (project `ai-run-demo-agents`, "Agent2Agent samples for CodeMie", Python `>=3.13`) declaring workspace members `agents/currency_converter`, `agents/fun-with-rick`, `agents/financial-agent`, `agents/research-agent`. Four independent agents exist, each its own package with `__main__.py`, `agent.py`, `task_manager.py`, `Dockerfile`, `pyproject.toml`, `README.md`:

- `python/agents/currency_converter/` — `CurrencyAgent`, LangGraph ReAct agent + Frankfurter FX tool. Port 10000. Fullest README with real JSON-RPC request/response examples (sync, multi-turn, streaming).
- `python/agents/financial-agent/` — `FinancialAgent`, LangGraph ReAct agent with `yfinance`-backed tools (`get_company_info/news/history/financials`). Port 10500. README has no request/response examples.
- `python/agents/fun-with-rick/` — `FunWithRickAgent`, LangGraph ReAct agent, no tools registered (`self.tools = []`) even though its `SYSTEM_INSTRUCTION` tells the model to "Use the 'tavily_search_tool' tool" — that tool is never defined or bound. Port 10600.
- `python/agents/research-agent/` — `ResearchAgent`, a 3-node LangGraph `StateGraph` (topic extraction → research → analysis), richly docstringed, with input validation and session cleanup. Port 10700 (per README `HOST`/`PORT` env vars). Ships its own `test_client.py`.

Shared code lives in `python/common/`:
- `common/server/server.py` — `A2AServer` (Starlette app): POST `/` for JSON-RPC dispatch, GET `/.well-known/agent.json` for the agent card; routes by request type to `TaskManager` methods; SSE via `EventSourceResponse` when the handler returns an `AsyncIterable`.
- `common/server/task_manager.py` — abstract `TaskManager` + `InMemoryTaskManager` (in-memory task/session store, SSE queueing).
- `common/client/client.py`, `common/client/card_resolver.py` — `A2AClient` (send_task, send_task_streaming via `httpx_sse`, get/cancel task) and `A2ACardResolver` for discovering the agent card.
- `common/utils/chat_model_factory.py` — `create_chat_model()`: reads `CHAT_MODEL_PROVIDER` (`azure` uses `AzureChatOpenAI` + `AZURE_OPENAI_ENDPOINT`/`AZURE_OPENAI_API_VERSION`; anything else falls through to `init_chat_model(model=CHAT_MODEL, model_provider=...)`, default `openai`/`gpt-4o`).
- `common/utils/push_notification_auth.py`, `common/utils/in_memory_cache.py` — JWK-based push-notification signing/verification (used for the A2A push-notification feature, out of scope per ticket).
- `common/types.py` — full A2A protocol Pydantic model set (Task/Message/Part/Artifact, JSON-RPC request/response types, `AgentCard`/`AgentSkill`/`AgentCapabilities`).

Each agent's `agent.py` exposes the same shape: `invoke(query, sessionId) -> dict` (blocking, full response) and `async stream(query, sessionId) -> AsyncIterable[dict]` (yields `working` progress messages, then a final dict) — i.e. every existing agent already implements both a complete-response path and an incremental/streaming path at the agent layer; the task manager exposes `invoke` via `tasks/send` (JSON response) and `stream` via `tasks/sendSubscribe` (SSE).

### Architecture and Layers Affected

- **Agent/reasoning layer**: `agents/*/agent.py` (LangGraph `create_react_agent` or custom `StateGraph`).
- **Protocol/task layer**: `agents/*/task_manager.py` (`AgentTaskManager(InMemoryTaskManager)`), `common/server/task_manager.py`.
- **Transport/server layer**: `agents/*/__main__.py` (click CLI, builds `AgentCard`, starts `A2AServer`), `common/server/server.py` (Starlette/uvicorn, SSE).
- **Client/verification layer**: `common/client/*`, and `agents/research-agent/test_client.py` as the only existing example of a standalone check script.
- **Documentation layer**: root `README.md` (stale) and four per-agent `README.md` files (each self-contained and largely accurate for its own agent).
- **Packaging/deployment**: root + per-agent `pyproject.toml` (uv workspace, `[tool.uv.sources] ai-run-demo-agents = { workspace = true }`), per-agent `Dockerfile` (multi-stage `uv sync` using `--build-context` against the workspace root).

### Integration Points

- All four agents call out to a live LLM via `create_chat_model()` — Azure OpenAI (documented in every README) or, if `CHAT_MODEL_PROVIDER` is unset/other, `init_chat_model` (OpenAI by default) — no README documents the non-Azure path.
- `currency_converter` additionally calls the public Frankfurter FX API (`https://api.frankfurter.app`) via `httpx`, no key required.
- `financial-agent` additionally calls Yahoo Finance via the `yfinance` package (network + native dependency, see Risk Indicators).
- `fun-with-rick`'s prompt references a Tavily search tool that is not wired up — no live Tavily integration exists despite the prompt text.
- No database, no persistent storage; task/session state is process-memory only (`InMemoryTaskManager`, LangGraph `MemorySaver`).

### Patterns and Conventions

- Every agent implements the same `invoke`/`stream`/`get_agent_response` trio and a `ResponseFormat(BaseModel)` with `status: Literal['input_required','completed','error']` — a de facto base contract, though there is no shared base class (each agent duplicates the pattern rather than inheriting one).
- `AgentTaskManager` subclasses `common.server.task_manager.InMemoryTaskManager` and is otherwise near-identical across `currency_converter`/`financial-agent`/`fun-with-rick` (line-for-line boilerplate); `research-agent`'s task manager was not diffed but follows the same server bootstrap in `__main__.py`.
- CLI bootstrap pattern: `click` options `--host`/`--port`/`--ngrok_enabled` (`pyngrok.ngrok.connect`), build `AgentCapabilities`/`AgentSkill`/`AgentCard`, wire `PushNotificationSenderAuth`, start `A2AServer`.

---

## 3. Documentation Findings

### Guides and Architecture Docs

No `.ai-run/guides/` directory exists (only `.ai-run/sdlc-factory/`). No `docs/` content beyond the current superpowers task run. No ADR files, no CHANGELOG/HISTORY. Conventions below are derived from code.

### Architectural Decisions

None recorded. The root `pyproject.toml` description ("Agent2Agent samples for CodeMie") and per-agent Dockerfiles/`README`s frame this as a Google A2A-protocol sample collection; the ticket explicitly excludes A2A/CodeMie work, so existing protocol machinery is context, not something this task should extend.

### Derived Conventions

- Port convention: each agent picks a distinct default port (10000, 10500, 10600, 10700) via `click.option`.
- `.env` is the expected local secrets file (git-ignored: `.gitignore` lists `.env`, `.venv`); no agent ships a committed `.env.example` — README setup steps use `echo "KEY=value" >> .env` with placeholder values (`your_api_key_here`), so no real credentials currently exist in any tracked file.
- README structure convention (title, How It Works, Prerequisites, Setup & Running with `uv run .`/Docker, Limitations) is consistent across all four agent READMEs; `research-agent`'s README additionally has a "Testing" and "Environment Variables" section — the strongest existing template for satisfying acceptance criteria 4 and 6.

---

## 4. Testing Landscape

### Existing Coverage

Only `python/agents/research-agent/test_client.py` exists as a check script: connects to a running agent via `A2ACardResolver`/`A2AClient`, runs one non-streaming `send_task` + `get_task` round trip, then one `send_task_streaming` round trip, printing JSON responses for manual inspection. Run via `uv run test_client.py` from the agent directory. No assertions — it is a smoke/demo script, not a pytest suite.

No test files exist for `common/`, `currency_converter`, `financial-agent`, or `fun-with-rick` (repo-wide `test_*.py` search only surfaces `research-agent/test_client.py` and vendored `.venv` library tests, which are irrelevant).

### Testing Framework and Patterns

No `pytest`/`unittest` framework is declared as a dependency anywhere in the workspace. The one existing "test" is a manual async script using the real `A2AClient` against a live server — no mocking, no fixtures, no CI wiring (`.github/` does not exist).

### Coverage Gaps

- `currency_converter`, `financial-agent`, `fun-with-rick` have no equivalent of `test_client.py` — nothing currently demonstrates acceptance criterion 4 for them.
- No coverage anywhere for `common/server`, `common/client`, `common/utils` in isolation.
- No coverage validating that `uv sync`/`uv run` actually succeeds per agent (see Risk Indicators — this is exactly how `financial-agent` broke silently).

---

## 5. Configuration and Environment

### Environment Variables

- `CHAT_MODEL_PROVIDER` (`azure` or other; default `openai` per `chat_model_factory.py`), `CHAT_MODEL` (default `gpt-4o`).
- Azure path: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION` (all required together; `create_chat_model` raises `ValueError` if endpoint/version missing).
- `research-agent` README also documents `HOST`, `PORT`, `LOG_LEVEL`, `ENABLE_NGROK` — these are the only agent-level env vars documented anywhere; not confirmed as actually read by `research-agent/__main__.py` (not opened in this pass).
- No env vars for Tavily despite the `fun-with-rick` prompt referencing a search tool.

### Configuration Files

- No committed `.env.example` anywhere in the repo (`Glob **/.env*` found nothing tracked).
- Root `python/pyproject.toml` (workspace + shared deps) and one `pyproject.toml` per agent (agent-specific deps, each declaring `ai-run-demo-agents = { workspace = true }` under `[tool.uv.sources]`).
- `requires-python` is inconsistent: root `>=3.13`, `currency_converter` `>=3.12,<4.0`, `financial-agent`/`fun-with-rick` `>=3.12`, `research-agent` `>=3.13`. Not currently causing failures under this workspace/`uv` version, but worth flagging.

### Feature Flags and Deployment Concerns

- `--ngrok_enabled` CLI flag (via `pyngrok`) on `currency_converter`, `financial-agent`, `fun-with-rick` for exposing the local server publicly; not present in `research-agent/__main__.py`'s documented options (README only shows `--host`/`--port`).
- Each agent has its own `Dockerfile`; pattern (from `currency_converter/Dockerfile`) copies `common/`, root `pyproject.toml`/`uv.lock`/`README.md` in via `--build-context ai-run-agents=...`, then runs `uv sync --no-dev` at both the workspace root and the agent directory before `CMD ["uv","run",".","--host","0.0.0.0"]`.
- No CI/CD (`.github/workflows` absent) — nothing currently verifies these agents install or run on any commit, which is consistent with the repo having silently drifted into a broken state for at least one agent.

---

## 6. Risk Indicators

- **`financial-agent` fails to install in this environment today.** Reproduced directly: `uv run python -c "import agent"` inside `python/agents/financial-agent` fails during dependency resolution/build because `yfinance` pulls in `curl_cffi`, which has no prebuilt wheel for this Python/platform combination and requires compiling a C extension ("Microsoft Visual C++ 14.0 or greater is required"). `currency_converter`, `fun-with-rick`, and `research-agent` all import cleanly via `uv run` from their own directories. This is the concrete "not working" symptom the ticket's "revive" language points at, and it affects the one agent most likely to be picked as a demo candidate if the choice is content-driven rather than reliability-driven.
- **Root `python/README.md` is stale.** It documents only the currency agent, links to a nonexistent `python/agents/langgraph` path, and omits `financial-agent`, `fun-with-rick`, and `research-agent` entirely — directly blocks acceptance criterion 6 as written today.
- **`fun-with-rick` has a dead tool reference.** Its system prompt instructs the model to use `'tavily_search_tool'`, but `self.tools = []` — no such tool is registered, and no `TAVILY_API_KEY` is documented. Picking this agent as a demo would either need the dead reference removed/fixed or accepted as a known limitation.
- **No automated "it works" check exists for 3 of 4 agents.** Only `research-agent/test_client.py` demonstrates acceptance criterion 4 today, and even it has no assertions (manual/visual verification only).
- **No CI enforces installability.** Nothing currently would have caught the `financial-agent` build break before it shipped; reviving the repo without some minimal automated check risks the same regression recurring.
- **Every agent requires a live LLM credential to produce a verifiable result** (Azure OpenAI, or OpenAI via `init_chat_model`'s default). `currency_converter` additionally needs outbound network access to a public FX API. "Basic checks without CodeMie" will still need *some* real (test-tier) LLM credential unless a stub/fake model path is introduced — how to satisfy that without embedding real secrets is a design question for spec/plan, not something resolved in code today.
- **No `.env.example` file is committed anywhere** — onboarding currently relies on copy/pasting `echo` commands from each README. This already avoids leaking real credentials (placeholders only) but leaves nothing for a doc to point to as a canonical template.

---

## 7. Summary for Complexity Assessment

This task touches five layers of a small, already-scaffolded multi-agent sample repo: the LangGraph agent layer (`agents/*/agent.py`), the A2A task/transport layer (`task_manager.py` + shared `common/server`), CLI bootstrap (`__main__.py`), documentation (root + per-agent `README.md`), and packaging/env config (per-agent `pyproject.toml`, absent `.env.example`). Three of four candidate agents already satisfy the "one streaming, one complete" requirement at the code level — every agent's `agent.py` implements both `invoke()` (complete) and `stream()` (incremental) — so the core mechanics the ticket asks for already exist; the work is more about verification, repair, and documentation than new architecture.

Technical novelty is low (no new patterns needed — the task manager/streaming pattern is fully established and can be copied), but there is one concrete blocking defect: `financial-agent` cannot currently be installed/imported in this environment due to a native-build dependency (`yfinance`→`curl_cffi`) lacking a prebuilt wheel. Test coverage posture is thin — only `research-agent` has any check script, and it is assertion-free — so satisfying "basic checks demonstrate both agents work without CodeMie" (criterion 4) has essentially no reusable scaffolding beyond that one example. There is no CI, no `.env.example`, and the root README is stale and misleading about what agents exist.

Key risk factors for planning: (1) deciding which two agents to designate as the demo pair, given one candidate (`financial-agent`) is currently broken and another (`fun-with-rick`) has a dead tool reference; (2) how "verifiable results ... without CodeMie" is satisfied given every agent needs a real LLM credential; (3) whether to fix the native-dependency break or simply route around it by choosing other agents; (4) bringing the root README and possibly per-agent READMEs in line with acceptance criterion 6 without duplicating already-accurate per-agent docs (`currency_converter` and `research-agent` READMEs are largely fine as-is).

---

## 8. External References

None named by the task. `task_context` describes the ticket inline and does not point at any external file, directory, or URL as a source of truth.
