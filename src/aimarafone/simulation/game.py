import logging
import uuid
from math import floor
from typing import List, Optional, Tuple, Union

from aimarafone import constants
from aimarafone.objects.card import CARD_MAX_RANK, CARD_MIN_RANK, Card
from aimarafone.objects.deck import Deck
from aimarafone.objects.player import Player
from aimarafone.objects.suit import Suit

logger = logging.getLogger(__name__)

_key_card = Card(Suit.DENARA, 4)

_rank_to_value = {
    1: 11,
    2: 12,
    3: 13,
    4: 4,
    5: 5,
    6: 6,
    7: 7,
    8: 8,
    9: 9,
    10: 10,
}

_rank_to_points = {
    1: 1,
    2: 0.34,
    3: 0.34,
    4: 0,
    5: 0,
    6: 0,
    7: 0,
    8: 0.34,
    9: 0.34,
    10: 0.34,
}


def rotate(l, n):
    return l[n:] + l[:n]


def argmax(l):
    return l.index(max(l))


suit_index = {Suit.BASTONI: 0, Suit.DENARA: 10, Suit.SPADE: 20, Suit.COPPE: 30}


def hand_to_vector(hand):
    vector = [0] * 40
    for card in hand:
        vector[suit_index[card.suit] + card.rank - 1] = 1
    return vector


def turn_to_vector(turn):
    vector = [0] * 40
    for card in turn:
        vector[suit_index[card.suit] + card.rank - 1] = 1
    return vector


class Round:
    """Class representing a round of the game"""

    def __init__(
        self,
        players: Tuple[Player, Player, Player, Player],
        player_id_to_team: dict,
        first_player: Optional[Player] = None,
    ) -> None:
        self.id = hash(uuid.uuid4())
        self.players = players
        self.player_id_to_team = player_id_to_team
        self.teams_scores = {
            1: 0,
            2: 0,
        }
        self.first_player = first_player
        self.last_winner = None
        self.history = []
        self.game_summary = []
        if first_player is not None:
            logger.info(f"Nuovo round: inizia {first_player.name}")
        else:
            logger.info(
                f"Primo round della partita tra {[p.name for p in self.players]}"
            )

    def deal_cards(self):
        deck = Deck()
        deck.shuffle()
        for player in self.players:
            player.add_to_hand(deck.deal(constants["INITIAL_HAND"]))

    def set_briscola(self):
        if self.first_player is None:
            for player in self.players:
                if _key_card in player.hand:
                    self.first_player = player
                    logger.info(f"{self.first_player.name} ha il {_key_card}")
                    break

        self.briscola = self.first_player.select_briscola()

    def play_turn(self):
        owner = self.last_winner if self.last_winner is not None else self.first_player
        cards_on_table = []
        playing_order = rotate(self.players, self.players.index(owner))
        for player in playing_order:
            cards_on_table.append(
                player.play_card(self.briscola, cards_on_table, self.history)
            )
            self.game_summary.append(
                ([player.id] + hand_to_vector(player.hand) + [cards_on_table[-1]])
            )

        dominant_suit = cards_on_table[0].suit
        highest_card = argmax(
            [
                (
                    _rank_to_value[card.rank] + 100
                    if card.suit == self.briscola
                    else _rank_to_value[card.rank] if card.suit == dominant_suit else 0
                )
                for card in cards_on_table
            ]
        )

        self.last_winner = playing_order[highest_card]
        earned_points = sum([_rank_to_points[card.rank] for card in cards_on_table])

        logger.info(
            f"Prende {self.last_winner.name} con {cards_on_table[highest_card]} [+ {round(earned_points, 2)} punti]"
        )

        self.teams_scores[self.player_id_to_team[self.last_winner.id]] += earned_points

        self.history.append((playing_order, cards_on_table))

    def play_round(self):
        self.deal_cards()
        self.set_briscola()

        for i in range(10):
            self.play_turn()

        self.teams_scores[self.player_id_to_team[self.last_winner.id]] += 1

        self.teams_scores[1] = floor(self.teams_scores[1])
        self.teams_scores[2] = floor(self.teams_scores[2])

        if sum(self.teams_scores.values()) != 11:
            raise ValueError

        logger.info(f"Round finito {self.teams_scores[1]} a {self.teams_scores[2]}")


class Game:
    """Class representing a game of 4 players."""

    def __init__(self) -> None:
        self.id = hash(uuid.uuid4())
        self.players = [Player() for i in range(constants["NUMBER_OF_PLAYERS"])]
        self.player_id_to_team = {
            self.players[0].id: 1,
            self.players[1].id: 2,
            self.players[2].id: 1,
            self.players[3].id: 2,
        }
        self.teams_scores = {
            1: 0,
            2: 0,
        }
        self.last_first_player = None
        self.winning_team = None

    def _check_winner(self):
        if any([v > 41 for v in self.teams_scores.values()]):
            self.winning_team = argmax(list(self.teams_scores.values())) + 1

    def play_round(self) -> None:
        if self.last_first_player is None:
            first_player = None
        else:
            first_player_index = self.players.index(self.last_first_player) + 1
            if first_player_index > 3:
                first_player_index -= 4
            first_player = self.players[first_player_index]

        round = Round(self.players, self.player_id_to_team, first_player)
        round.play_round()
        self.last_first_player = round.first_player
        for i in self.teams_scores.keys():
            self.teams_scores[i] += round.teams_scores[i]

        logger.info(
            f"Punteggio attuale {self.teams_scores[1]} a {self.teams_scores[2]}"
        )

    def play_game(self):
        while self.winning_team is None:
            self.play_round()
            self._check_winner()
        logger.info(f"Vince il team {self.winning_team}")


if __name__ == "__main__":
    test_game = Game()
    test_game.play_game()
