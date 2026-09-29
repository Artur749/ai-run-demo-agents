FROM ghcr.io/astral-sh/uv:python3.13-alpine

# Copy the project into the image
COPY --from=ai-run-agents common /app/common
COPY --from=ai-run-agents pyproject.toml /app/pyproject.toml
COPY --from=ai-run-agents README.md /app/README.md
COPY --from=ai-run-agents uv.lock /app/uv.lock
COPY . /app/agents/howto-guide-agent

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Sync the project into a new environment, asserting the lockfile is up to date
WORKDIR /app/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

WORKDIR /app/agents/howto-guide-agent
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

CMD ["uv", "run", ".", "--host", "0.0.0.0", "--port", "10900"]