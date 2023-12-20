import logging
import random
from typing import Optional

from aimarafone.objects.suit import Suit

logger = logging.getLogger(__name__)

CARD_MIN_RANK = 1
CARD_MAX_RANK = 10

_rank_to_name = {
    1: "Asso",
    2: "Due",
    3: "Tre",
    4: "Quattro",
    5: "Cinque",
    6: "Sei",
    7: "Sette",
    8: "Fante",
    9: "Cavallo",
    10: "Re",
}


class Card:
    """Class representing a playing card.

    Attributes:
        suit (Suit): The suit of the card.
        rank (int): The rank of the card.
    """

    def __init__(self, suit: Optional[Suit] = None, rank: Optional[int] = None) -> None:
        if suit is None:
            self.suit = random.choice(list(Suit))
        else:
            self.suit = suit

        if rank is None:
            self.rank = random.randint(CARD_MIN_RANK, CARD_MAX_RANK)
        else:
            self._validate_rank(rank)
            self.rank = rank

        self.name = f"{_rank_to_name[self.rank]} di {self.suit.value}"
        logger.debug(f"Created a new card: {self}")

    def _validate_rank(self, rank: int) -> None:
        if not CARD_MIN_RANK <= rank <= CARD_MAX_RANK:
            raise ValueError(
                f"Invalid rank. Rank must be between {CARD_MIN_RANK} and {CARD_MAX_RANK}."
            )

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other) -> bool:
        if self.suit == other.suit and self.rank == other.rank:
            return True
        else:
            return False

    @staticmethod
    def generate_cards(n: Optional[int]):
        if n == 0:
            raise ValueError("Generate at least one card")
        elif n == 1:
            return Card()
        else:
            return [Card() for i in range(n)]


if __name__ == "__main__":
    print(Card())
