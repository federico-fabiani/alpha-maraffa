"""Entry point: ``python -m aimaraffa.ai``."""

import logging

from .pipeline import run

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    run()
