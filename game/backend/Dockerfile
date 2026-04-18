FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --group ml --no-install-project

COPY src ./src

RUN uv sync --frozen --no-dev --group ml

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app/src
EXPOSE 8080

CMD ["sh", "-c", "uv run uvicorn aimaraffa.api:app --host 0.0.0.0 --port ${PORT:-8080}"]