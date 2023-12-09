import logging
import random
from typing import List, Optional, Union

from aimarafone.objects.card import Card
from aimarafone.utils.names import Genre, pick_a_name

logging.basicConfig(level=logging.INFO)


class Player:
    """Class representing a player."""

    def __init__(self, name: Optional[str] = None) -> None:
        self.hand = []
        if name is None:
            genre = random.choice(list(Genre))
            suffix = "o" if genre == Genre.MASCULINE else "a"
            name = f"Nonn{suffix} " + pick_a_name(genre)

        self.name = name

    def add_to_hand(self, cards: Union[List[Card], Card]):
        if isinstance(cards, list):
            self.hand += cards
        else:
            self.hand.append(cards)

    def remove_from_hand(self, card: Card):
        if card in self.hand:
            self.hand.remove(card)
            return card
        else:
            raise ValueError(f"{card} not in hand.")

    def __str__(self):
        if len(self.hand) > 0:
            return f"{self.name} ha {len(self.hand)} carte in mano: {[str(card) for card in self.hand]}"
        else:
            return f"{self.name} non ha carte in mano."


if __name__ == "__main__":
    player = Player()
    player.add_to_hand(Card.generate_cards(5))
    print(player)
