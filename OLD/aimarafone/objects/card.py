import logging
import random
from typing import Optional

from aimarafone.objects.suit import Suit

logger = logging.getLogger(__name__)

CARD_MIN_RANK = 1
CARD_MAX_RANK = 10

_rank_to_name = {
    1: "Asso 1️⃣ ",
    2: "Due 2️⃣ ",
    3: "Tre 3️⃣ ",
    4: "Quattro 4️⃣ ",
    5: "Cinque 5️⃣ ",
    6: "Sei 6️⃣ ",
    7: "Sette 7️⃣ ",
    8: "Fante 🛡️ ",
    9: "Cavallo 🐎",
    10: "Re 👑",
}


def _select_suit():
    return random.choice(list(Suit))


def _select_rank():
    return random.choice(list(_rank_to_name.keys()))


class Card:
    """Class representing a playing card.

    Attributes:
        suit (Suit): The suit of the card.
        rank (int): The rank of the card.
    """

    def __init__(self, suit: Optional[Suit] = None, rank: Optional[int] = None):
        self.suit = suit if suit is not None else _select_suit()
        self.rank = self._validate_rank(rank if rank is not None else _select_rank())
        logger.debug(f"Created a new card: {self}")

    def _validate_rank(self, rank: int) -> None:
        if rank not in _rank_to_name.keys():
            raise ValueError(
                f"Invalid rank. Rank must be between {CARD_MIN_RANK} and {CARD_MAX_RANK}."
            )
        return rank

    def get_name(self) -> str:
        return f"{_rank_to_name[self.rank]} di {self.suit.value}"

    def __str__(self) -> str:
        return self.get_name()

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
    [print(c) for c in Card.generate_cards(5)]
