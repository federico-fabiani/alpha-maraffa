"""Unit tests for the game engine: cards, deck, helpers, and game loop."""

from collections import Counter

import pytest

from aimaraffa.engine import (
    GAME_WIN_THRESHOLD,
    KEY_CARD,
    RANK_TO_POINTS,
    RANK_TO_VALUE,
    Card,
    Deck,
    GameRoom,
    PlayerSlot,
    RoomManager,
    Suit,
    bot_select_briscola,
    bot_select_card,
    card_to_dict,
    determine_turn_winner,
    dict_to_card,
    generate_room_code,
    get_valid_cards,
)


# ── Deck ───────────────────────────────────────────────────────────────────────

def test_deck_has_40_unique_cards():
    """A fresh deck must contain exactly 40 distinct cards."""
    deck = Deck()
    assert len(deck.cards) == 40
    assert len(set(deck.cards)) == 40


def test_deck_covers_all_suits_and_ranks():
    """Each suit appears 10 times; each rank appears 4 times."""
    deck = Deck()
    suit_counts = Counter(c.suit for c in deck.cards)
    rank_counts = Counter(c.rank for c in deck.cards)
    for suit in Suit:
        assert suit_counts[suit] == 10
    for rank in range(1, 11):
        assert rank_counts[rank] == 4


def test_deck_deal_removes_correct_count():
    """Dealing n cards reduces the deck by n and returns exactly n cards."""
    deck = Deck()
    hand = deck.deal(10)
    assert len(hand) == 10
    assert len(deck.cards) == 30


def test_deck_shuffle_preserves_all_cards():
    """Shuffling must not add, remove, or duplicate any card."""
    deck = Deck()
    original = set(deck.cards)
    deck.shuffle()
    assert set(deck.cards) == original


def test_key_card_in_fresh_deck():
    """The 4 of Denara (the key card) must be in every fresh deck."""
    assert KEY_CARD in Deck().cards


# ── Card ───────────────────────────────────────────────────────────────────────

def test_card_equality_same_suit_and_rank():
    """Cards with identical suit and rank must be equal."""
    assert Card(Suit.BASTONI, 1) == Card(Suit.BASTONI, 1)


def test_card_inequality_different_suit():
    """Cards that differ in suit must not be equal."""
    assert Card(Suit.BASTONI, 1) != Card(Suit.COPPE, 1)


def test_card_hash_allows_set_dedup():
    """Two equal cards must have the same hash and collapse in a set."""
    c1 = Card(Suit.DENARA, 7)
    c2 = Card(Suit.DENARA, 7)
    assert hash(c1) == hash(c2)
    assert len({c1, c2}) == 1


# ── Serialisation ──────────────────────────────────────────────────────────────

def test_card_serialisation_roundtrip():
    """card_to_dict → dict_to_card must return an equal card."""
    card = Card(Suit.SPADE, 3)
    assert dict_to_card(card_to_dict(card)) == card


def test_dict_to_card_returns_none_on_invalid_input():
    """dict_to_card must return None for missing or unknown fields."""
    assert dict_to_card({}) is None
    assert dict_to_card({"suit": "NONEXISTENT", "rank": 1}) is None


# ── get_valid_cards ────────────────────────────────────────────────────────────

def test_no_lead_suit_all_cards_valid():
    """With no lead suit the entire hand is playable."""
    hand = [Card(Suit.BASTONI, 1), Card(Suit.COPPE, 5)]
    assert get_valid_cards(hand, None) == hand


def test_must_follow_lead_suit_when_possible():
    """If the player holds the lead suit, only those cards are valid."""
    hand = [Card(Suit.BASTONI, 1), Card(Suit.COPPE, 5)]
    assert get_valid_cards(hand, Suit.BASTONI) == [Card(Suit.BASTONI, 1)]


def test_can_play_anything_when_no_lead_suit_match():
    """If the player has no card of the lead suit, the whole hand is valid."""
    hand = [Card(Suit.COPPE, 2), Card(Suit.SPADE, 9)]
    assert set(get_valid_cards(hand, Suit.BASTONI)) == set(hand)


# ── determine_turn_winner ──────────────────────────────────────────────────────

def test_highest_lead_suit_wins_without_briscola():
    """The highest-value card of the lead suit wins when no briscola is played."""
    seat_cards = [
        (0, Card(Suit.BASTONI, 1)),   # value 11
        (1, Card(Suit.BASTONI, 7)),   # value 7
        (2, Card(Suit.BASTONI, 3)),   # value 13 ← wins
        (3, Card(Suit.COPPE, 5)),     # off-suit, power 0
    ]
    assert determine_turn_winner(seat_cards, Suit.SPADE) == 2


def test_briscola_beats_any_lead_suit_card():
    """A briscola card of any rank beats the highest non-briscola card."""
    seat_cards = [
        (0, Card(Suit.BASTONI, 3)),   # lead, value 13
        (1, Card(Suit.SPADE, 4)),     # briscola, low value ← still wins
    ]
    assert determine_turn_winner(seat_cards, Suit.SPADE) == 1


def test_highest_briscola_wins_when_multiple_played():
    """When multiple briscola cards are played, the highest-value one wins."""
    seat_cards = [
        (0, Card(Suit.BASTONI, 3)),
        (1, Card(Suit.SPADE, 1)),     # briscola value 11+100
        (2, Card(Suit.SPADE, 3)),     # briscola value 13+100 ← wins
    ]
    assert determine_turn_winner(seat_cards, Suit.SPADE) == 2


# ── Bot helpers ────────────────────────────────────────────────────────────────

def test_bot_selects_majority_suit_as_briscola():
    """The bot picks the suit it holds the most cards of."""
    hand = [
        Card(Suit.BASTONI, 1), Card(Suit.BASTONI, 2), Card(Suit.BASTONI, 3),
        Card(Suit.COPPE, 5),
    ]
    assert bot_select_briscola(hand) == Suit.BASTONI


def test_bot_follows_lead_suit():
    """Bot card selection must respect the lead-suit constraint."""
    hand = [Card(Suit.BASTONI, 1), Card(Suit.COPPE, 5)]
    card, _decl = bot_select_card(hand, Suit.BASTONI, Suit.SPADE)
    assert card.suit == Suit.BASTONI


# ── PlayerSlot ────────────────────────────────────────────────────────────────

def test_player_slot_team_assignment():
    """Seats 0 and 2 are team 1; seats 1 and 3 are team 2."""
    assert PlayerSlot(0, "A").team == 1
    assert PlayerSlot(1, "B").team == 2
    assert PlayerSlot(2, "C").team == 1
    assert PlayerSlot(3, "D").team == 2


# ── RoomManager ────────────────────────────────────────────────────────────────

def test_room_manager_creates_and_retrieves_room():
    """A created room must be retrievable by its ID."""
    manager = RoomManager()
    room = manager.create()
    assert manager.get(room.room_id) is room


def test_room_manager_lookup_is_case_insensitive():
    """Room lookup must work regardless of the ID's casing."""
    manager = RoomManager()
    room = manager.create()
    assert manager.get(room.room_id.lower()) is room


def test_room_manager_purge_removes_finished_rooms():
    """purge_finished must remove rooms with status 'game_over'."""
    manager = RoomManager()
    room = manager.create()
    room.status = "game_over"
    manager.purge_finished()
    assert manager.get(room.room_id) is None


def test_room_manager_purge_keeps_active_rooms():
    """purge_finished must not remove rooms still in play."""
    manager = RoomManager()
    room = manager.create()
    room.status = "in_game"
    manager.purge_finished()
    assert manager.get(room.room_id) is room


def test_room_code_format():
    """Generated room codes must follow the ADJECTIVE-ANIMAL-NN pattern."""
    code = generate_room_code()
    parts = code.split("-")
    assert len(parts) == 3
    assert parts[2].isdigit()


# ── Full game loop (engine only, no WebSocket) ─────────────────────────────────

async def test_full_game_all_bots_reaches_game_over():
    """A room with all bots must complete and set status to 'game_over'."""
    room = GameRoom("TEST-SIM")

    async def noop(_msg):
        """No-op broadcast."""

    async def noop_state(_phase=None):
        """No-op broadcast_state."""

    async def noop_send(_seat, _msg):
        """No-op send."""

    room.broadcast = noop
    room.broadcast_state = noop_state
    room._send = noop_send

    await room.run_game_loop()

    assert room.status == "game_over"
    assert max(room.total_scores.values()) > GAME_WIN_THRESHOLD


async def test_round_scores_always_sum_to_11():
    """After each round the two teams' round scores must sum to exactly 11."""
    room = GameRoom("TEST-ROUND")
    round_sums: list[int] = []

    original_round = room._round

    async def patched_round(first_seat):
        """Wrap _round to capture round scores after each round."""
        await original_round(first_seat)
        round_sums.append(room.round_scores[1] + room.round_scores[2])

    async def noop(_msg=None, **_kw):
        """No-op for broadcast methods."""

    room._round = patched_round
    room.broadcast = noop
    room.broadcast_state = noop
    room._send = lambda _s, _m: noop()

    await room.run_game_loop()

    for s in round_sums:
        assert s == 11, f"Round score sum was {s}, expected 11"
