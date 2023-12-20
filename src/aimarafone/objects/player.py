import logging
import random
import uuid
from typing import List, Optional, Union

from aimarafone.objects.card import Card
from aimarafone.objects.suit import Suit
from aimarafone.simulation.strategy import RandomStrategy, Strategy
from aimarafone.utils.names import Genre, pick_a_name

logger = logging.getLogger(__name__)


class Player:
    """Class representing a player."""

    def __init__(
        self, name: Optional[str] = None, strategy: Optional[Strategy] = None
    ) -> None:
        self.id = hash(uuid.uuid4())
        self.hand = []
        if name is None:
            genre = random.choice(list(Genre))
            suffix = "o" if genre == Genre.MASCULINE else "a"
            name = f"Nonn{suffix} " + pick_a_name(genre)
        self.name = name

        if strategy is None:
            strategy = RandomStrategy()
        self.strategy = strategy

    def add_to_hand(self, cards: Union[List[Card], Card]):
        if isinstance(cards, list):
            self.hand += cards
        else:
            self.hand.append(cards)

    def play_card_from_hand(self, card: Card):
        if card in self.hand:
            self.hand.remove(card)
            return card
        else:
            raise ValueError(f"{card} not in hand.")

    def play_card(
        self,
        briscola: Suit,
        cards_on_table: List[Union[Card, None]],
        history: List[List[Union[Card, None]]],
    ):
        best_choice = self.strategy.select_card(
            briscola, self.hand, cards_on_table, history
        )
        action = "gioca"
        try:
            if best_choice.suit == briscola and cards_on_table[0].suit != briscola:
                action = "taglia con"
        except IndexError:
            pass
        logger.info(f"{self.name} {action} {best_choice}")
        return self.play_card_from_hand(best_choice)

    def select_briscola(self) -> Suit:
        return self.strategy.select_briscola(self.hand)

    def __str__(self):
        if len(self.hand) > 0:
            return f"{self.name} gioca con strategia {self.strategy}. Ha {len(self.hand)} carte in mano: {[str(card) for card in self.hand]}."
        else:
            return f"{self.name} gioca con strategia {self.strategy}. Non ha carte in mano."


if __name__ == "__main__":
    player = Player()
    player.add_to_hand(Card.generate_cards(5))
    print(player)
