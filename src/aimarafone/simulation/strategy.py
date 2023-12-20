import random
from abc import ABC
from typing import List, Optional, Union

from aimarafone.objects.card import Card
from aimarafone.objects.suit import Suit


class Strategy(ABC):
    def __init__(self):
        self.name = "abstract"

    def select_briscola(self, hand) -> Suit:
        raise NotImplementedError("Abstract method not implemented.")

    def select_card(
        self,
        briscola: Suit,
        hand: List[Card],
        cards_on_table: List[Union[Card, None]],
        history: List[List[Union[Card, None]]],
    ) -> Card:
        raise NotImplementedError("Abstract method not implemented.")

    def __str__(self):
        return self.name.capitalize()


class RandomStrategy(Strategy):
    def __init__(self):
        self.name = "random"

    def select_briscola(self, hand) -> Suit:
        return random.choice(list(Suit))

    def select_card(
        self,
        briscola: Suit,
        hand: List[Card],
        cards_on_table: List[Union[Card, None]],
        history: List[List[Union[Card, None]]],
    ) -> Card:
        possible_actions = []
        if any(cards_on_table):
            dominant_suit = cards_on_table[0].suit
            possible_actions = [
                card for card in hand if card.suit in (dominant_suit, briscola)
            ]
        if not any(possible_actions):
            possible_actions = hand
        return random.choice(possible_actions)


# TODO: implement RLStrategy (with exploration:float[0-1] parameter) and CustomStrategy
if __name__ == "__main__":
    print(RandomStrategy())
