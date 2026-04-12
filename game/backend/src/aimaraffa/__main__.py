"""Entry point: run with `python -m aimaraffa` or `uv run python -m aimaraffa`."""

import uvicorn

from aimaraffa.api import app
from aimaraffa.config import settings

if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())
