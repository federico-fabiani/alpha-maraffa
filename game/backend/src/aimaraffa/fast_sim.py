"""Vectorized Marafone simulator. Runs N games in parallel with NumPy.

Card encoding: id = suit_idx * 10 + rank_idx, where suit_idx in [0..3] maps to
(bastoni, denara, spade, coppe) and rank_idx in [0..9] maps to rank 1..10.
The 4 of Denara (KEY_CARD) is id 1*10 + 3 = 13.

All fractional points are stored as centi-points (int) to stay on the integer
path — round_score_centi // 100 reproduces Python's ``floor`` exactly.

The bot policies match aimaraffa.engine.bot_select_briscola / bot_select_card
(random valid card, most-common-suit briscola) in expectation; tie-breaks use
numpy argmax ordering (which can differ from the CPython dict/list ordering in
engine.py — this is fine for Monte-Carlo statistics).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np

# ── Static lookup tables ──────────────────────────────────────────────────────

# Rank strength (card_rank → power). Index 0 is unused (ranks start at 1).
# Briscola adds +100 on top of this.
_RANK_VALUE = np.array(
    [0, 11, 12, 13, 4, 5, 6, 7, 8, 9, 10], dtype=np.int16
)
# Points as centi-points (×100). Index 0 unused.
_RANK_POINTS_CENTI = np.array(
    [0, 100, 34, 34, 0, 0, 0, 0, 34, 34, 34], dtype=np.int16
)

GAME_WIN_THRESHOLD = 41
_KEY_CARD_ID = 1 * 10 + 3  # 4 of denara
_MAX_ROUNDS = 100          # hard safety cap; real games finish in < 20


def _deal(rng: np.random.Generator, n: int) -> np.ndarray:
    """Return one fresh permutation of 0..39 per game, shape (n, 40) int8."""
    # np.argsort over uniform floats is a fast parallel shuffle.
    return np.argsort(rng.random((n, 40), dtype=np.float32), axis=1).astype(np.int8)


def _random_valid_pick(
    rng: np.random.Generator,
    hand: np.ndarray,     # (M, 10) card_id or -1
    valid: np.ndarray,    # (M, 10) bool
) -> Tuple[np.ndarray, np.ndarray]:
    """Pick one uniformly-random valid slot per game; return (chosen_card, slot_idx)."""
    M = hand.shape[0]
    rnd = rng.random((M, 10), dtype=np.float32)
    rnd[~valid] = -1.0
    slot = rnd.argmax(axis=1)
    card = hand[np.arange(M), slot]
    return card, slot


def simulate_batch(
    n_games: int,
    seed: Optional[int] = None,
    return_stats: bool = False,
) -> Any:
    """Simulate ``n_games`` full games in parallel with the random bot policy.

    Returns ``total_scores`` of shape (n_games, 2) as int16. If ``return_stats``
    is True, also returns a dict with diagnostic counters.
    """
    rng = np.random.default_rng(seed)
    N = n_games

    total_scores = np.zeros((N, 2), dtype=np.int16)
    briscola_selector = np.full(N, -1, dtype=np.int8)  # -1 → not yet set
    active = np.ones(N, dtype=bool)

    rounds_total = 0
    for _round in range(_MAX_ROUNDS):
        act = np.nonzero(active)[0]
        if act.size == 0:
            break
        M = act.size

        # ── Deal ──────────────────────────────────────────────────────────────
        hands = _deal(rng, M).reshape(M, 4, 10)  # (M, seat, slot)

        # ── Determine first-round selector where needed ──────────────────────
        first = briscola_selector[act].copy()
        unset_mask = first < 0
        if unset_mask.any():
            sub = hands[unset_mask]
            # any(axis=2): which seats holds the 4 of denara
            holder = (sub == _KEY_CARD_ID).any(axis=2).argmax(axis=1)
            first[unset_mask] = holder.astype(np.int8)

        # ── Briscola = most-common suit in selector's hand ───────────────────
        sel_hand = hands[np.arange(M), first]                # (M, 10)
        sel_suits = (sel_hand // 10).astype(np.int8)
        # bincount per game: 4 buckets. vectorize with broadcasting.
        suit_counts = np.zeros((M, 4), dtype=np.int8)
        for s in range(4):
            suit_counts[:, s] = (sel_suits == s).sum(axis=1)
        briscola = suit_counts.argmax(axis=1).astype(np.int8)  # (M,)

        # ── Maraffa (cricca): selector holds ace+2+3 of briscola ─────────────
        c1 = briscola * 10 + 0  # ace of briscola (rank 1)
        c2 = briscola * 10 + 1
        c3 = briscola * 10 + 2
        has_maraffa = (
            (sel_hand == c1[:, None]).any(axis=1)
            & (sel_hand == c2[:, None]).any(axis=1)
            & (sel_hand == c3[:, None]).any(axis=1)
        )
        first_team = (first % 2).astype(np.int8)
        if has_maraffa.any():
            np.add.at(total_scores, (act[has_maraffa], first_team[has_maraffa]), 3)

        # ── Play 10 turns ────────────────────────────────────────────────────
        round_centi = np.zeros((M, 2), dtype=np.int32)
        cur_first = first.copy()
        maraffa_forced = has_maraffa.copy()

        arange_M = np.arange(M)

        for turn in range(10):
            order = (cur_first[:, None] + np.arange(4, dtype=np.int8)) % 4  # (M, 4)
            played = np.empty((M, 4), dtype=np.int8)

            for i in range(4):
                seats_i = order[:, i]
                hand_of = hands[arange_M, seats_i, :]        # (M, 10) view
                non_empty = hand_of >= 0

                if i == 0:
                    valid = non_empty
                    if turn == 0 and maraffa_forced.any():
                        ace = briscola * 10
                        forced = hand_of == ace[:, None]
                        valid = np.where(maraffa_forced[:, None], forced, valid)
                else:
                    lead_suit_i = played[:, 0] // 10
                    same_suit = ((hand_of // 10) == lead_suit_i[:, None]) & non_empty
                    has_lead = same_suit.any(axis=1)
                    valid = np.where(has_lead[:, None], same_suit, non_empty)

                card, slot = _random_valid_pick(rng, hand_of, valid)
                played[:, i] = card
                hands[arange_M, seats_i, slot] = -1           # consume

            # Turn winner (briscola > lead > off-suit)
            lead_suit = played[:, 0] // 10
            played_suit = played // 10
            played_rank = (played % 10) + 1
            vals = _RANK_VALUE[played_rank]
            is_b = played_suit == briscola[:, None]
            is_l = (played_suit == lead_suit[:, None]) & ~is_b
            power = np.where(is_b, vals + 100, np.where(is_l, vals, 0))
            winner_pos = power.argmax(axis=1)
            cur_first = order[arange_M, winner_pos]
            winner_team = (cur_first % 2).astype(np.int8)
            turn_pts_centi = _RANK_POINTS_CENTI[played_rank].sum(axis=1).astype(np.int32)
            np.add.at(round_centi, (arange_M, winner_team), turn_pts_centi)

        # Last-trick bonus = +1 point = +100 centi
        last_team = (cur_first % 2).astype(np.int8)
        np.add.at(round_centi, (arange_M, last_team), 100)

        # Floor → integer points, add to totals
        round_score = (round_centi // 100).astype(np.int16)
        total_scores[act] += round_score

        # Rotate selector
        briscola_selector[act] = ((first + 1) % 4).astype(np.int8)

        # Check termination
        newly_done = total_scores[act].max(axis=1) >= GAME_WIN_THRESHOLD
        active[act[newly_done]] = False
        rounds_total += M

    if return_stats:
        return total_scores, {"rounds": int(rounds_total)}
    return total_scores
