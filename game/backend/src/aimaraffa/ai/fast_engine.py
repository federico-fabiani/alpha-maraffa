"""Fast Marafone game engine for ISMCTS rollouts and self-play.

Encoding
--------
A card is a single integer in [0, 39]:
    card_id = suit * 10 + (rank - 1)
    suit    = card_id // 10        # 0=BASTONI 1=DENARA 2=SPADE 3=COPPE
    rank    = (card_id % 10) + 1   # 1..10

Trick-strength power table — same as engine.RANK_TO_VALUE but pre-baked
into a [40] array so card_power(c) is one indirect lookup.

Game state is a flat dataclass holding numpy arrays.  All hot mutations
are O(1) numpy ops.  No Python objects per-card, no dict allocations.

This module is intentionally framework-agnostic: it only depends on numpy
so it can run inside multiprocessing workers with negligible startup cost.

Public API
----------
- ``CARD_TO_SUIT``, ``CARD_TO_RANK``, ``CARD_POINTS``, ``CARD_VALUE``: lookup tables.
- ``GameState``: flat-array round state.
- ``deal_round`` / ``copy_state``.
- ``legal_actions``: tuple ``(card_ids ndarray, count)``.
- ``apply_action``: mutates state, returns ``(trick_done, points, winner_seat)``.
- ``round_terminal_scores``: returns ``(team1_pts_floor, team2_pts_floor)``.

Design notes
------------
* Score is tracked as **thirds**: integer ``raw_score[2]`` where
  raw_score[0] = team1 thirds, [1] = team2 thirds.  Floor scoring at end
  is just ``raw_score // 3``.  Last-trick bonus is +3 thirds.
* ``hands`` stored as ``int8[4, 10]`` of card_ids; ``-1`` marks empty
  slot.  ``n_cards[4]`` tracks live count.
* ``table_cards`` and ``table_seats`` are int8[4] populated as the trick
  unfolds.  Lead suit = ``CARD_TO_SUIT[table_cards[0]]``.
* Declarations: leading player can declare ``busso/striscio/volo/None``
  at the moment of leading.  Encoded as int8 ``-1`` (None), ``0`` busso,
  ``1`` striscio, ``2`` volo.  Recorded per turn, then propagated to
  belief trackers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

# ── Constants ──────────────────────────────────────────────────────────────────

NUM_CARDS = 40
NUM_SEATS = 4
HAND_SIZE = 10

# Suit codes — must match engine.Suit enum order if we round-trip with the slow engine.
SUIT_BASTONI = 0
SUIT_DENARA  = 1
SUIT_SPADE   = 2
SUIT_COPPE   = 3
SUIT_NAMES   = ("bastoni", "denara", "spade", "coppe")

# Declarations.
DECL_NONE     = -1
DECL_BUSSO    = 0
DECL_STRISCIO = 1
DECL_VOLO     = 2
DECL_NAMES    = {DECL_NONE: None, DECL_BUSSO: "busso", DECL_STRISCIO: "striscio", DECL_VOLO: "volo"}

# Team for each seat (0,2 → team 0; 1,3 → team 1).  Team-index 0/1 for clean
# numpy indexing; downstream API still uses 1/2.
SEAT_TO_TEAM = np.array([0, 1, 0, 1], dtype=np.int8)


def _build_lookups() -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build per-card lookup tables: suit, rank, value (strength), points (thirds)."""
    suit  = np.empty(NUM_CARDS, dtype=np.int8)
    rank  = np.empty(NUM_CARDS, dtype=np.int8)
    value = np.empty(NUM_CARDS, dtype=np.int8)
    pts3  = np.empty(NUM_CARDS, dtype=np.int8)  # points × 3 (so 1/3 → 1, 1.0 → 3)

    # RANK_TO_VALUE: 1→11, 2→12, 3→13, 4..10→4..10
    rank_value = {1: 11, 2: 12, 3: 13, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9, 10: 10}
    rank_pts3  = {1: 3,  2: 1,  3: 1,  4: 0, 5: 0, 6: 0, 7: 0, 8: 1, 9: 1, 10: 1}

    for c in range(NUM_CARDS):
        s = c // 10
        r = (c % 10) + 1
        suit[c]  = s
        rank[c]  = r
        value[c] = rank_value[r]
        pts3[c]  = rank_pts3[r]
    return suit, rank, value, pts3


CARD_TO_SUIT, CARD_TO_RANK, CARD_VALUE, CARD_POINTS3 = _build_lookups()
# Per suit: rank1=3 thirds + (rank2,3,8,9,10)*1 = 8 thirds → 4 suits × 8 = 32.
# Last-trick bonus adds +3 thirds → max round total = 35 thirds.
TOTAL_TRICK_POINTS3   = int(CARD_POINTS3.sum())   # 32
LAST_TRICK_BONUS3     = 3
ROUND_TOTAL_POINTS3   = TOTAL_TRICK_POINTS3 + LAST_TRICK_BONUS3   # 35


# ── Power calculation ──────────────────────────────────────────────────────────

def card_power(card: int, lead_suit: int, briscola: int) -> int:
    """Strength of a card within the current trick context (briscola wins; lead wins; off-suit loses)."""
    s = CARD_TO_SUIT[card]
    if s == briscola:
        return CARD_VALUE[card] + 100
    if s == lead_suit:
        return CARD_VALUE[card]
    return 0


# ── State ──────────────────────────────────────────────────────────────────────

@dataclass
class GameState:
    """Single round state — flat numpy arrays.

    ``round_complete`` is True once 10 tricks have been played.
    """
    # Hands: int8[4, 10] of card_ids; -1 = empty slot.
    hands:    np.ndarray = field(default_factory=lambda: np.full((NUM_SEATS, HAND_SIZE), -1, dtype=np.int8))
    n_cards:  np.ndarray = field(default_factory=lambda: np.full(NUM_SEATS, HAND_SIZE, dtype=np.int8))

    # Briscola suit (0..3) and selector seat.
    briscola:           int = -1
    briscola_selector:  int = 0

    # Trick state.
    first_of_turn: int = 0     # seat that leads the upcoming trick
    table_cards:   np.ndarray = field(default_factory=lambda: np.full(NUM_SEATS, -1, dtype=np.int8))
    table_seats:   np.ndarray = field(default_factory=lambda: np.full(NUM_SEATS, -1, dtype=np.int8))
    table_pos:     int = 0     # how many cards in the current trick (0..4)

    # Declaration of the lead seat for the current/last trick.
    last_declaration: int = DECL_NONE

    # Score in thirds (so final floor() is integer division by 3).
    raw_scores:  np.ndarray = field(default_factory=lambda: np.zeros(2, dtype=np.int32))
    turn_num:    int = 0       # tricks completed so far
    round_complete: bool = False

    # ── History (for feature encoding / belief).  Populated after each trick. ──
    # played_mask: 40-bit per-card mask (in two int64 because numba prefers int64).
    played_mask: int = 0
    # For each of 40 cards: -1 if not played; else the seat that played it.
    card_owner: np.ndarray = field(default_factory=lambda: np.full(NUM_CARDS, -1, dtype=np.int8))
    # turn at which each card was played (-1 if not played).
    card_turn:  np.ndarray = field(default_factory=lambda: np.full(NUM_CARDS, -1, dtype=np.int8))
    # declaration paired with the card if it was the leading card of its trick.
    card_decl:  np.ndarray = field(default_factory=lambda: np.full(NUM_CARDS, DECL_NONE, dtype=np.int8))
    # whether each played card was the leading card of its trick.
    card_is_lead: np.ndarray = field(default_factory=lambda: np.zeros(NUM_CARDS, dtype=bool))
    # seat that led each trick (indexed by 0-based turn_num, populated as tricks complete).
    turn_lead_seat: np.ndarray = field(default_factory=lambda: np.full(HAND_SIZE, -1, dtype=np.int8))

    # Maraffa (cricca) marker — selector must lead 1 of briscola if forced.
    maraffa_forced: bool = False


# ── Construction ───────────────────────────────────────────────────────────────

def new_state() -> GameState:
    """Empty state."""
    return GameState()


def deal_round(
    rng:               np.random.Generator,
    briscola_selector: int = 0,
) -> GameState:
    """Shuffle a deck and deal 10 cards to each seat.

    The caller is responsible for setting ``briscola`` afterward (via
    selector decision) and calling ``apply_maraffa_bonus`` if the
    selector holds the cricca.
    """
    s = new_state()
    deck = rng.permutation(NUM_CARDS).astype(np.int8)
    for seat in range(NUM_SEATS):
        s.hands[seat] = deck[seat * 10:(seat + 1) * 10]
    s.n_cards[:] = HAND_SIZE
    s.briscola_selector = briscola_selector
    s.first_of_turn     = briscola_selector
    return s


def copy_state(s: GameState) -> GameState:
    """Deep copy — used for MCTS branching and determinization rollouts."""
    return GameState(
        hands             = s.hands.copy(),
        n_cards           = s.n_cards.copy(),
        briscola          = s.briscola,
        briscola_selector = s.briscola_selector,
        first_of_turn     = s.first_of_turn,
        table_cards       = s.table_cards.copy(),
        table_seats       = s.table_seats.copy(),
        table_pos         = s.table_pos,
        last_declaration  = s.last_declaration,
        raw_scores        = s.raw_scores.copy(),
        turn_num          = s.turn_num,
        round_complete    = s.round_complete,
        played_mask       = s.played_mask,
        card_owner        = s.card_owner.copy(),
        card_turn         = s.card_turn.copy(),
        card_decl         = s.card_decl.copy(),
        card_is_lead      = s.card_is_lead.copy(),
        turn_lead_seat    = s.turn_lead_seat.copy(),
        maraffa_forced    = s.maraffa_forced,
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def hand_view(s: GameState, seat: int) -> np.ndarray:
    """Return live (non-empty) cards for ``seat`` as a 1-D int8 array."""
    h = s.hands[seat]
    return h[h >= 0]


def seat_to_play(s: GameState) -> int:
    """Whose turn is it to play next."""
    return (s.first_of_turn + s.table_pos) % NUM_SEATS


def lead_suit(s: GameState) -> int:
    """Suit of the leading card of the current trick, or -1 if none played."""
    if s.table_pos == 0:
        return -1
    return int(CARD_TO_SUIT[s.table_cards[0]])


# ── Legal-action generation ────────────────────────────────────────────────────

def legal_card_actions(s: GameState, seat: int) -> np.ndarray:
    """Return the int8 array of cards ``seat`` may legally play right now."""
    hand = hand_view(s, seat)
    if s.maraffa_forced and seat == s.briscola_selector and s.table_pos == 0:
        # Forced to lead with the briscola ace (rank 1).
        ace = s.briscola * 10 + 0   # rank 1 → index 0
        # Must be in hand by precondition; return as a 1-element array.
        return np.array([ace], dtype=np.int8)

    if s.table_pos == 0:
        return hand
    led = lead_suit(s)
    same_suit = hand[CARD_TO_SUIT[hand] == led]
    return same_suit if same_suit.size > 0 else hand


def valid_declarations(s: GameState, seat: int, played_card: int) -> np.ndarray:
    """For a leading play: returns the array of valid declarations.

    Always includes ``DECL_NONE`` and ``DECL_BUSSO``.  ``DECL_VOLO`` if
    seat will have no cards left in the played suit; ``DECL_STRISCIO``
    otherwise.
    """
    suit = CARD_TO_SUIT[played_card]
    h    = hand_view(s, seat)
    # After removing played_card, count cards still in hand of same suit.
    remaining = np.sum((CARD_TO_SUIT[h] == suit)) - 1   # subtract the played one
    if remaining > 0:
        return np.array([DECL_NONE, DECL_BUSSO, DECL_STRISCIO], dtype=np.int8)
    return np.array([DECL_NONE, DECL_BUSSO, DECL_VOLO], dtype=np.int8)


# ── Apply / step ───────────────────────────────────────────────────────────────

def _remove_from_hand(s: GameState, seat: int, card: int) -> None:
    """Remove ``card`` from ``seat``'s hand; compact the array (move -1 to end)."""
    h = s.hands[seat]
    # Find first index where h == card.
    for i in range(HAND_SIZE):
        if h[i] == card:
            # Compact: shift everything after i one slot left.
            for j in range(i, HAND_SIZE - 1):
                h[j] = h[j + 1]
            h[HAND_SIZE - 1] = -1
            break
    s.n_cards[seat] -= 1


def determine_trick_winner(table_cards: np.ndarray, table_seats: np.ndarray, briscola: int) -> int:
    """Seat that wins the trick given 4 cards already on the table."""
    led = int(CARD_TO_SUIT[table_cards[0]])
    best_pow  = -1
    best_seat = int(table_seats[0])
    for i in range(NUM_SEATS):
        c = int(table_cards[i])
        s = int(CARD_TO_SUIT[c])
        if s == briscola:
            p = int(CARD_VALUE[c]) + 100
        elif s == led:
            p = int(CARD_VALUE[c])
        else:
            p = 0
        if p > best_pow:
            best_pow  = p
            best_seat = int(table_seats[i])
    return best_seat


def apply_card(
    s:           GameState,
    seat:        int,
    card:        int,
    declaration: int = DECL_NONE,
) -> Tuple[bool, int, int]:
    """Play ``card`` from ``seat`` into the current trick.

    Returns ``(trick_complete, trick_points3, winner_seat)``.
    When the trick is mid-resolution ``(False, 0, -1)`` is returned.
    """
    pos = s.table_pos
    s.table_cards[pos] = card
    s.table_seats[pos] = seat
    if pos == 0:
        s.last_declaration = declaration
        s.turn_lead_seat[s.turn_num] = seat

    s.card_owner[card]   = seat
    s.card_turn[card]    = s.turn_num + 1   # 1-based turn index used by trackers
    s.card_decl[card]    = declaration if pos == 0 else DECL_NONE
    s.card_is_lead[card] = (pos == 0)
    s.played_mask |= (1 << card)

    _remove_from_hand(s, seat, card)
    s.table_pos += 1
    s.maraffa_forced = False   # consumed once (forced lead happens once max per round)

    if s.table_pos < NUM_SEATS:
        return False, 0, -1

    # ── Trick complete ────────────────────────────────────────────────────────
    winner = determine_trick_winner(s.table_cards, s.table_seats, s.briscola)
    pts3 = 0
    for i in range(NUM_SEATS):
        pts3 += int(CARD_POINTS3[int(s.table_cards[i])])
    s.raw_scores[SEAT_TO_TEAM[winner]] += pts3
    s.first_of_turn = winner
    s.turn_num     += 1
    s.table_pos     = 0
    s.table_cards[:] = -1
    s.table_seats[:] = -1

    if s.turn_num >= HAND_SIZE:
        # Last-trick bonus: +1 point = +3 thirds.
        s.raw_scores[SEAT_TO_TEAM[winner]] += 3
        s.round_complete = True

    return True, pts3, winner


def round_floor_scores(s: GameState) -> Tuple[int, int]:
    """Final floor scores (team1, team2) for the round."""
    return int(s.raw_scores[0] // 3), int(s.raw_scores[1] // 3)


# ── Slow-engine bridge ─────────────────────────────────────────────────────────
# Helpers to convert from / to the original ``engine.Card`` / ``Suit`` so we can
# interoperate with HeuristicAgent and the websocket game loop.

def card_id_from_engine(card) -> int:
    """Map ``engine.Card`` → int card_id."""
    from aimaraffa.engine import Suit as _Suit
    suit_idx = (_Suit.BASTONI, _Suit.DENARA, _Suit.SPADE, _Suit.COPPE).index(card.suit)
    return suit_idx * 10 + (card.rank - 1)


def engine_card_from_id(card_id: int):
    """Map int card_id → ``engine.Card``."""
    from aimaraffa.engine import Card as _Card, Suit as _Suit
    suits = (_Suit.BASTONI, _Suit.DENARA, _Suit.SPADE, _Suit.COPPE)
    return _Card(suits[card_id // 10], (card_id % 10) + 1)


def suit_from_id(suit_id: int):
    from aimaraffa.engine import Suit as _Suit
    return (_Suit.BASTONI, _Suit.DENARA, _Suit.SPADE, _Suit.COPPE)[suit_id]


def suit_id(suit) -> int:
    from aimaraffa.engine import Suit as _Suit
    return (_Suit.BASTONI, _Suit.DENARA, _Suit.SPADE, _Suit.COPPE).index(suit)
