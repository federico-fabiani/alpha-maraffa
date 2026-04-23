"""Factory helpers for constructing Marafone agents by policy name."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .base import BaseAgent


def create_agent(policy: str, *, model_path: str = "", seed: Optional[int] = None) -> BaseAgent:
    """Build the requested agent implementation.

    The live engine uses this as the single authority for policy selection.
    """
    normalized = (policy or "heuristic").strip().lower()

    if normalized == "heuristic":
        from .heuristic_agent import HeuristicAgent

        return HeuristicAgent()

    if normalized == "random":
        from .random_agent import RandomAgent

        return RandomAgent(seed=seed)

    if normalized == "ml":
        if not model_path:
            raise ValueError("ML bot policy requires a model path")
        from .ml_agent import MLAgent

        return MLAgent(Path(model_path), seed=seed)

    raise ValueError(f"Unknown bot policy: {policy}")