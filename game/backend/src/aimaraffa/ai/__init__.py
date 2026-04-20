"""Marafone model-training pipeline.

Run the full iteration with::

    uv run python -m aimaraffa.ai

Tweak constants in ``aimaraffa.ai.config`` — there are no CLI flags.
"""

from .pipeline import run

__all__ = ["run"]
