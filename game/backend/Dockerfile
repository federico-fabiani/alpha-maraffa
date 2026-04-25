FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
# Install dependencies only (cached layer — rebuilds only when pyproject.toml/uv.lock change).
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
# Install the project itself (fast — deps already in place).
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8080

# Use uvicorn directly — avoids uv run auto-sync which re-downloads dev deps.
CMD ["sh", "-c", ".venv/bin/uvicorn aimaraffa.api:app --host 0.0.0.0 --port ${PORT:-8080}"]