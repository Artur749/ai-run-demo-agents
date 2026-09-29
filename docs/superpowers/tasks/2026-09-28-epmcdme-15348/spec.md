# Spec: Revive ai-run-demo-agents — Four Demo Agents (EPMCDME-15348)

## Overview

Bring the repo to a demonstrably working state with four documented demo agents:

1. **`currency_converter`** (existing, hand-rolled `common/` scaffolding, port 10000) —
   complete-response demo.
2. **`research-agent`** (existing, hand-rolled `common/` scaffolding, port 10700) —
   incremental/streaming demo.
3. **`text-insights-agent`** (new, port 10800, built on the official `a2a-sdk` package) — a
   third, self-contained demo agent that exercises a real third-party A2A SDK instead of this
   repo's hand-rolled protocol code; complete-response only.
4. **`howto-guide-agent`** (new, port 10900, built on the same `a2a-sdk` package) — a fourth
   demo agent, the streaming counterpart to agent 3: genuinely incremental output via
   `a2a-sdk`'s own streaming/task-update-event mechanism.

Agents 1 and 2 are documentation/verification-only work — both already implement `invoke()`
(complete) and `stream()` (incremental) in their existing `agent.py`. Agents 3 and 4 are new,
additive scope, each fully standalone: their own business logic, their own LLM credential, no
dependency on the other agents, on each other, or on `common/`.

**CodeMie interop is explicitly out of scope for this ticket, including for agents 3 and 4.**
The agent calling CodeMie, CodeMie calling the agent, and any registration step are fully
deferred to a separate future task — this applies equally to agent 4, matching the decision
already made for agent 3. Nothing in this spec requires a CodeMie credential, a CodeMie API
call, or CodeMie-side registration for any of the four agents. `financial-agent` and
`fun-with-rick` remain untouched and documented as known limitations, as before.

## Decisions

### Agents 1 & 2 (unchanged)

- **Demo pair**: `currency_converter` (port 10000, complete-response) and `research-agent`
  (port 10700, incremental/streaming) — both `uv run` cleanly today.
- **Verification approach**: live smoke-test scripts (extend `research-agent/test_client.py`
  with real assertions; add an equivalent `test_client.py` for `currency_converter`), run
  locally against a running agent using a developer-supplied, non-committed LLM credential.
- **Commands run per-agent-directory**, not workspace-wide, so `financial-agent`'s broken
  dependency cannot block criterion 1 for the chosen pair.

### Agent 3: `text-insights-agent` (unchanged)

- **SDK choice**: builds on the official `a2a-sdk` PyPI package instead of this repo's
  hand-rolled `common/server`/`common/client`/`common/types`, isolated to its own package —
  `common/` and the other agents are untouched. The root README calls out explicitly that the
  repo now has two parallel A2A implementations by design (hand-rolled for the original three,
  `a2a-sdk`-based for agents 3 and 4), so it isn't mistaken for an oversight.
- **Version pin**: this stage has no live PyPI access, so rather than hand-typing an
  unverifiable "latest" version number, `pyproject.toml` declares a floor constraint
  (`a2a-sdk>=<floor>`, matching this repo's existing convention for every other dependency), and
  the implementer resolves the exact version by running `uv add a2a-sdk` during the
  implementation stage, recording the resolved version in the agent's README.
- **Business use case**: a small "text insights" agent — free text in, one local
  credential-free tool computes objective stats (word count, reading time, a simple
  keyword-based sentiment signal), the agent's own LLM reasoning combines that with its own
  judgment into a short structured summary.
- **Response mode**: non-streaming task-submission path only (`a2a-sdk`'s equivalent of
  `message/send`).
- **Credentials**: only the same class of LLM credential agents 1/2 already require, via the
  same root `.env.example`. No CodeMie credential, no other external API key.

### Agent 4: `howto-guide-agent` (new)

- **SDK choice and version pin**: same as agent 3 — built on the same `a2a-sdk` package,
  isolated to its own package, with its own floor-constraint dependency declaration resolved via
  `uv add a2a-sdk` at implementation time (the implementer may reuse whatever exact version was
  already resolved for agent 3, or re-resolve independently; either is acceptable since both are
  floor-constrained, not hand-pinned to a guessed number).
- **Business use case**: a small "how-to guide" agent. Input is a short goal or task
  description (e.g. "set up a home Wi-Fi router", "prepare for a job interview"). The agent's
  LLM reasoning decomposes the goal into an ordered list of concrete steps and emits each step
  as a separate incremental update as it is produced, followed by a final event containing the
  complete, compiled guide. This is a naturally incremental task — each step is genuinely
  new content becoming available over time, not a synthetic progress percentage — and is
  distinct in domain from FX conversion (agent 1), multi-node research (agent 2), and static
  text analysis (agent 3).
- **Response mode**: this agent's entire purpose is to exercise `a2a-sdk`'s streaming path
  (its `stream()`/task-update-event mechanism), producing multiple discrete, content-bearing
  events per request rather than a single final response. A non-streaming path is not required.
- **Credentials**: only the same class of LLM credential the other three agents require, via
  the same root `.env.example`. No CodeMie credential, no other external API key.

## Scope of Changes

### Agents 1 & 2 (unchanged from prior spec version)

1. `python/README.md` (root) — documents `currency_converter` and `research-agent` run/try
   instructions, states which is incremental vs. complete, adds a "Known Limitations" section
   for `financial-agent`/`fun-with-rick`, removes the stale nonexistent-path reference.
   (Extended further below to also cover agents 3 and 4.)
2. `python/.env.example` (new, root) — placeholders for `CHAT_MODEL_PROVIDER`, `CHAT_MODEL`,
   `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION`. Agents 3 and 4
   reuse this same file — no additional vars needed.
3. `python/agents/research-agent/test_client.py` — add real assertions to the existing script.
4. `python/agents/currency_converter/test_client.py` (new) — same shape, new file.
5. `python/agents/currency_converter/README.md`, `python/agents/research-agent/README.md` —
   point at the new root `.env.example`, add a one-line "Testing" pointer.

### Agent 3 (unchanged)

6. `python/agents/text-insights-agent/` (new package, port 10800) — `pyproject.toml` (declares
   `a2a-sdk>=<floor>`, added as a new `[tool.uv.workspace]` member in root `python/pyproject.toml`
   alongside the existing four), `agent.py` (LangGraph agent + the local stats tool),
   `__main__.py` (CLI bootstrap using `a2a-sdk`'s server/application classes instead of
   `common.server.A2AServer`, with `--host`/`--port` options consistent with the other agents),
   `README.md`, `Dockerfile` (same multi-stage `uv sync` pattern as the other agents').
7. `python/agents/text-insights-agent/test_client.py` (new) — connects to a locally running
   instance, asserts the agent card is well-formed, sends one real input, asserts the task
   result is meaningful and non-empty. Requires only the agent's own LLM credential.
8. `python/README.md` — adds agent 3's run/try instructions and documents the two parallel A2A
   implementations (hand-rolled vs. `a2a-sdk`) and why.

### Agent 4 (new)

9. `python/agents/howto-guide-agent/` (new package, port 10900) — `pyproject.toml` (declares
   `a2a-sdk>=<floor>`, added as a new `[tool.uv.workspace]` member alongside the other five),
   `agent.py` (LangGraph agent that decomposes a goal into ordered steps and yields each as a
   distinct incremental unit via `a2a-sdk`'s streaming path), `__main__.py` (CLI bootstrap on
   `a2a-sdk`'s server/application classes, `--host`/`--port` options consistent with the other
   agents), `README.md` (How It Works, Prerequisites, Setup & Running, Testing, Limitations),
   `Dockerfile` (same multi-stage `uv sync` pattern).
10. `python/agents/howto-guide-agent/test_client.py` (new) — connects to a locally running
    instance, asserts the agent card is well-formed, sends one real goal input via the
    streaming path, and asserts that (a) more than one discrete content-bearing event is
    received before completion, and (b) the final compiled guide is meaningful and non-empty.
    Requires only the agent's own LLM credential.
11. `python/README.md` — adds agent 4's run/try instructions, and explicitly documents that
    agent 4 is the streaming counterpart to agent 3 (both on `a2a-sdk`), so the README now
    describes four agents total with a clear "which agent demonstrates what" summary table or
    list covering: complete vs. incremental, hand-rolled vs. `a2a-sdk`.

## Acceptance Criteria

### Agents 1 & 2 (unchanged)

- AC1: Root README documents `uv run` startup for `currency_converter` and `research-agent`,
  runnable from a clean checkout with only a local `.env`.
- AC2: Both `test_client.py` scripts send a real input to a live agent and assert on a
  non-empty, meaningful result field.
- AC3: Root README states `research-agent` = incremental/streaming demo, `currency_converter`
  = complete-response demo; each script's assertions match its assigned mode.
- AC4: Both scripts fail (assertion/non-zero exit) if the agent doesn't return a meaningful
  result, and run purely against the local server — no CodeMie involved.
- AC5: `python/.env.example` and all README snippets contain only placeholder values.
- AC6: Root README gives per-agent prerequisites, `.env` setup, start command, and
  check-script instructions for both chosen agents.

### Agent 3 (unchanged)

- AC7: `text-insights-agent`'s `pyproject.toml` declares `a2a-sdk` as a dependency (floor
  version constraint); its `__main__.py`/`agent.py` are built on that package's classes, not
  `common/`.
- AC8: The agent accepts a text input, runs its own logic (local stats tool + LLM synthesis),
  and returns a meaningful, non-empty result.
- AC9: `test_client.py` runs against a locally running instance using only the agent's own LLM
  credential, and asserts both that the agent card is schema-valid and that a real input
  produces a meaningful, non-empty result.

### Agent 4 (new)

- AC10: `howto-guide-agent`'s `pyproject.toml` declares `a2a-sdk` as a dependency (floor
  version constraint); its `__main__.py`/`agent.py` are built on that package's classes, not
  `common/`, and are isolated from agent 3's package (no shared code between them beyond what
  each independently imports from `a2a-sdk`/LangGraph).
- AC11: The agent accepts a goal/task description as input, decomposes it into an ordered
  sequence of steps via its own LLM reasoning, and returns a meaningful, non-empty compiled
  guide as its final result — the same functional bar as AC2/AC8 for the other agents.
- AC12: `test_client.py` runs against a locally running instance using only the agent's own
  LLM credential, invokes it via `a2a-sdk`'s streaming path, and asserts that more than one
  discrete content-bearing event is received before the final event, demonstrating genuinely
  incremental output (not a single response wrapped in a stream).

## Non-goals

### Agents 1 & 2 (unchanged)

- Fixing `financial-agent`'s or `fun-with-rick`'s existing defects.
- Any change to `financial-agent`'s or `fun-with-rick`'s own `pyproject.toml`/`Dockerfile`, or
  to the root workspace member list *for those two agents*.
- Introducing a pytest suite, CI workflow, or a mocked/stubbed LLM path for agents 1/2.
- Docker-based run instructions beyond what already exists per-agent.

### Agent 3 (unchanged)

- CodeMie interop of any kind for agent 3 — deferred to a separate future ticket.
- Migrating `currency_converter`, `financial-agent`, `fun-with-rick`, or `research-agent` onto
  `a2a-sdk`, or changing `common/server`/`common/client`/`common/types` in any way.
- Streaming/incremental support for agent 3 — that's agent 4's role.
- Production-grade credential/secrets management.
- Confirming the exact current-latest `a2a-sdk` version number from this spec — an
  implementation-stage action (see Decisions above), not a silently-invented number.

### Agent 4 (new)

- **CodeMie interop of any kind for agent 4 either** — same deferral as agent 3: no agent
  calling CodeMie, no CodeMie calling the agent, no registration, no CodeMie env vars. Fully
  deferred to a separate future ticket.
- Non-streaming/complete-response support for agent 4 — agent 3 already covers the
  complete-response side of `a2a-sdk` usage; agent 4 exists specifically to exercise the
  streaming path and is not required to also implement `invoke()`-style single-shot responses.
- Sharing code or a common base package between agent 3 and agent 4 — each is independently
  isolated, consistent with how the original four agents each duplicate their own boilerplate
  rather than sharing beyond `common/` (which neither agent 3 nor 4 uses).
- Any persistence of guide history across requests — each request is independent, in-memory
  only, consistent with the rest of the repo's session handling.
- Production-grade credential/secrets management.
- Confirming the exact current-latest `a2a-sdk` version number from this spec — same
  implementation-stage action as agent 3; the implementer may reuse agent 3's resolved version
  or re-resolve independently.

## Testing

**Agents 1 & 2**: manual/local — developer supplies an LLM credential in `.env`, starts the
agent with `uv run .`, runs `uv run test_client.py` from the agent's own directory. A passing
run (no assertion errors, exit 0) is the basic check.

**Agent 3**: same shape — developer supplies the same class of LLM credential in `.env`, starts
the agent with `uv run .`, runs `uv run test_client.py` from the agent's own directory. A
passing run asserts both agent-card correctness and a meaningful task result; no CodeMie
credential is ever required.

**Agent 4**: same shape as agent 3, with streaming-specific assertions — developer supplies the
same class of LLM credential in `.env`, starts the agent with `uv run .`, runs
`uv run test_client.py` from the agent's own directory. A passing run asserts agent-card
correctness, that more than one discrete incremental event is received, and that the final
compiled guide is meaningful and non-empty; no CodeMie credential is ever required.
