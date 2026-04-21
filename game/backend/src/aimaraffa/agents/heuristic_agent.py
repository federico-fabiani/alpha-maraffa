"""Rule-based heuristic Marafone agent — stub awaiting rule implementation."""
from __future__ import annotations

from typing import Optional, Tuple

from aimaraffa.engine import Card, Suit

from .base import BaseAgent


class HeuristicAgent(BaseAgent):
    """Plays according to explicit Marafone strategy rules.

    Rules are defined collaboratively with domain experts and cover:
    - Briscola suit selection
    - Declaration logic (busso / striscio / volo)
    - Cooperative card discharge (ace to partner winning)
    - Busso response (high card in bussed suit)
    - Defensive briscola play

    This class is a **placeholder** — all game-decision methods raise
    ``NotImplementedError`` until the rules are agreed upon and implemented.
    """

    @property
    def name(self) -> str:
        return "heuristic"

    def reset_round(self) -> None:
        pass

    def record_card(
        self,
        card: Card,
        seat: int,
        turn_num: int,
        declaration: Optional[str],
    ) -> None:
        pass

    def select_briscola(self, ctx: dict) -> Suit:
        raise NotImplementedError("HeuristicAgent.select_briscola — rules not yet implemented")

    def select_card(self, ctx: dict, briscola: Suit) -> Tuple[Card, Optional[str]]:
        raise NotImplementedError("HeuristicAgent.select_card — rules not yet implemented")
