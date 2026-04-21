"""Uniformly-random Marafone agent — baseline for self-play bootstrapping."""
from __future__ import annotations

import random
from typing import Optional, Tuple

from aimaraffa.engine import Card, Suit, get_valid_cards, get_valid_declarations

from .base import BaseAgent


class RandomAgent(BaseAgent):
    """Picks uniformly at random from all legal moves and declarations."""

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)

    @property
    def name(self) -> str:
        return "random"

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
        return self._rng.choice(list(Suit))

    def select_card(self, ctx: dict, briscola: Suit) -> Tuple[Card, Optional[str]]:
        hand = ctx["hand"]
        table_cards = ctx.get("table_cards", [])
        lead_suit = table_cards[0][1].suit if table_cards else None
        is_lead = not bool(table_cards)
        valid = get_valid_cards(hand, lead_suit)
        card = self._rng.choice(valid)
        if is_lead:
            after = [c for c in hand if c != card]
            decls = get_valid_declarations(after, card.suit)
            return card, self._rng.choice(decls)
        return card, None
