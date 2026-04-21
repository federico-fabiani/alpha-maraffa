"""Abstract base class for all Marafone playing agents."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Tuple

from aimaraffa.engine import Card, Suit


class BaseAgent(ABC):
    """Common interface every Marafone agent must implement.

    Both single-game (live API) and batch simulation use this interface.

    Context dict (``ctx``) keys available to all methods:

      seat                    int               — playing seat (0–3)
      round_num               int
      turn_num                int
      briscola_selector_seat  int | None
      briscola                Suit | None       — None during select_briscola
      table_cards             list[(int, Card)] — (seat, card) pairs on the table
      round_scores            dict[int, float]  — {1: pts, 2: pts}
      total_scores            dict[int, int]
      hand                    list[Card]
      round_history           dict[str, tuple]  — "suit_rank" → (seat, turn_num, decl)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier used in logs and dataset metadata."""

    @abstractmethod
    def reset_round(self) -> None:
        """Called at the start of every new round."""

    @abstractmethod
    def record_card(
        self,
        card: Card,
        seat: int,
        turn_num: int,
        declaration: Optional[str],
    ) -> None:
        """Notified after every card play (all seats, including opponents)."""

    @abstractmethod
    def select_briscola(self, ctx: dict) -> Suit:
        """Choose the briscola suit at round start (``ctx["briscola"]`` is None here)."""

    @abstractmethod
    def select_card(self, ctx: dict, briscola: Suit) -> Tuple[Card, Optional[str]]:
        """Choose card + optional declaration to play.

        Returns ``(card, declaration)`` where declaration is one of
        ``"busso"``, ``"striscio"``, ``"volo"``, or ``None``.
        Non-lead plays must return ``None`` for the declaration.
        """
