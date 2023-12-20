import logging
from math import floor

from aimarafone.objects.card import CARD_MAX_RANK, CARD_MIN_RANK, Card
from aimarafone.objects.deck import Deck
from aimarafone.objects.player import Player
from aimarafone.objects.suit import Suit

logger = logging.getLogger(__name__)

N_PLAYERS = 4


def rotate(l, n):
    return l[n:] + l[:n]


def argmax(l):
    return l.index(max(l))


marafone_values = {
    i: i + CARD_MAX_RANK if i in [1, 2, 3] else i
    for i in range(CARD_MIN_RANK, CARD_MAX_RANK + 1)
}
marafone_points = {
    i: 1 if i == 1 else 0.34 if i in [2, 3, 8, 9, 10] else 0
    for i in range(CARD_MIN_RANK, CARD_MAX_RANK + 1)
}

# Setup players
players = [Player() for i in range(N_PLAYERS)]
teams = {
    1: (players[0], players[2]),
    2: (players[1], players[3]),
}
playerid2team = {players[0].id: 1, players[2].id: 1, players[1].id: 2, players[3].id: 2}
scores = {1: 0, 2: 0}
print([[t.name for t in team] for team in teams.values()])

# Setup deck
logger.info("Unboxing new deck of carte da briscola")
deck = Deck()
deck.shuffle()

# Start game
logger.info("Starting game")
key_card = Card(Suit.DENARA, 4)
first_player_id = None

logger.info("Dealing cards")
for i, player in enumerate(players):
    player.add_to_hand(deck.deal(10))
    if first_player_id is None and key_card in player.hand:
        first_player_id = i

briscola = players[first_player_id].select_briscola()
logger.info(f"{players[first_player_id].name} sceglie le briscole: {briscola.name}")

history = []
training_dataset = []
for turn in range(10):
    logger.info(f"### TURN {turn+1}")
    players = rotate(players, first_player_id)
    cards_on_table = []
    for playing_order, player in enumerate(players):
        log = [turn, playing_order, players.index(player), briscola.name]
        log += [card.name for card in cards_on_table]
        log += [card.name for card in player.hand]
        # log += history
        cards_on_table.append(player.play_card(briscola, cards_on_table, history))
        log.append(cards_on_table[-1].name)

        training_dataset.append(log)
    dominant_suit = cards_on_table[0].suit

    cards_on_table_values = []
    for card in cards_on_table:
        if card.suit == briscola:
            cards_on_table_values.append(marafone_values[card.rank] + 100)
            continue
        if card.suit == dominant_suit:
            cards_on_table_values.append(marafone_values[card.rank])
            continue
        cards_on_table_values.append(-1)

    first_player_id = argmax(cards_on_table_values)

    winning_team = playerid2team[players[first_player_id].id]
    scores[winning_team] += sum([marafone_points[card.rank] for card in cards_on_table])
    history.append(list(zip(players, cards_on_table)))
    print(
        f"\t {[([p.name for p in teams[team_id]], round(score, 2)) for team_id, score in scores.items()]}"
    )

print("\nFine partita!")
scores[winning_team] += 1
_ = [
    print(
        f"Team {team_id} {[p.name for p in teams[team_id]]}: {floor(team_score)} punti"
    )
    for team_id, team_score in scores.items()
]

# print(history)
