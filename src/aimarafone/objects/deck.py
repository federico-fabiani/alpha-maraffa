import logging
import random
from typing import List

from aimarafone.objects.card import CARD_MAX_RANK, CARD_MIN_RANK, Card
from aimarafone.objects.suit import Suit

logger = logging.getLogger(__name__)


class Deck:
    """Class representing a deck of playing cards."""

    def __init__(self) -> None:
        self.restore()

    def restore(self):
        """Restore all cards into the deck"""
        suits = list(Suit)
        ranks = list(range(CARD_MIN_RANK, CARD_MAX_RANK + 1))
        self.cards = [Card(suit, rank) for suit in suits for rank in ranks]

    def shuffle(self) -> None:
        """Shuffle the cards in the deck."""
        logger.info("Shuffling the deck")
        random.shuffle(self.cards)

    def deal(self, num_cards: int) -> List[Card]:
        """Deal a specified number of cards from the deck.

        Args:
            num_cards (int): The number of cards to deal.

        Returns:
            List[Card]: A list of dealt cards.
        """
        if num_cards > len(self.cards):
            logger.warning("Not enough cards in the deck to deal.")
            return []
        else:
            dealt_cards = self.cards[:num_cards]
            self.cards = self.cards[num_cards:]
            logger.info(f"Dealing {num_cards} cards.")
            return dealt_cards

    def __len__(self) -> int:
        return len(self.cards)

    def __str__(self) -> str:
        _cards_left = len(self)
        if _cards_left == 0:
            return "Un mazzo vuoto"
        elif _cards_left == 40:
            return "Un mazzo nuovo con 40 carte"
        else:
            return f"Un mazzo incominciato con {_cards_left} carte rimanenti"


if __name__ == "__main__":
    deck = Deck()
    print(deck)
    [print("  -", card) for card in deck.deal(5)]
    print(deck)
