"""Numba-JIT Marafone simulator — one full game per native call, parallel over games.

Same card-id and centi-point conventions as aimaraffa.fast_sim, but here every
inner loop is fused in machine code so the per-game cost drops to tens of
microseconds.
"""

from __future__ import annotations

import numpy as np
from numba import njit, prange

_RANK_VALUE = np.array(
    [0, 11, 12, 13, 4, 5, 6, 7, 8, 9, 10], dtype=np.int16
)
_RANK_POINTS_CENTI = np.array(
    [0, 100, 34, 34, 0, 0, 0, 0, 34, 34, 34], dtype=np.int16
)

GAME_WIN_THRESHOLD = 41
_KEY_CARD_ID = 13  # 4 of denara


@njit(cache=True, boundscheck=False, fastmath=False)
def _play_one(rank_value, rank_points_centi):
    """Simulate one full game (random bot) and return final (t1, t2) scores."""
    total_t1 = np.int32(0)
    total_t2 = np.int32(0)
    selector = np.int8(-1)

    # Reused per-round buffers (allocated once per call — numba keeps them alive)
    hands = np.empty((4, 10), dtype=np.int8)
    deck = np.empty(40, dtype=np.int8)

    while (total_t1 < GAME_WIN_THRESHOLD) and (total_t2 < GAME_WIN_THRESHOLD):
        # ── Deal via in-place Fisher-Yates ────────────────────────────────────
        for i in range(40):
            deck[i] = i
        for i in range(39, 0, -1):
            j = np.random.randint(0, i + 1)
            tmp = deck[i]
            deck[i] = deck[j]
            deck[j] = tmp
        for s in range(4):
            for k in range(10):
                hands[s, k] = deck[s * 10 + k]

        # ── Briscola selector ────────────────────────────────────────────────
        if selector < 0:
            for s in range(4):
                for k in range(10):
                    if hands[s, k] == _KEY_CARD_ID:
                        selector = np.int8(s)
                        break
                if selector >= 0:
                    break

        # ── Briscola = most-common suit in selector's hand (ties: lower idx) ─
        c0 = 0; c1 = 0; c2 = 0; c3 = 0
        for k in range(10):
            s = hands[selector, k] // 10
            if s == 0: c0 += 1
            elif s == 1: c1 += 1
            elif s == 2: c2 += 1
            else: c3 += 1
        briscola = np.int8(0); best = c0
        if c1 > best: best = c1; briscola = np.int8(1)
        if c2 > best: best = c2; briscola = np.int8(2)
        if c3 > best: best = c3; briscola = np.int8(3)

        # ── Maraffa (1,2,3 of briscola) ─────────────────────────────────────
        ace_id = briscola * 10        # rank 1 of briscola
        two_id = ace_id + 1           # rank 2
        three_id = ace_id + 2         # rank 3
        has1 = False; has2 = False; has3 = False
        for k in range(10):
            v = hands[selector, k]
            if v == ace_id: has1 = True
            elif v == two_id: has2 = True
            elif v == three_id: has3 = True
        maraffa = has1 and has2 and has3
        if maraffa:
            if selector % 2 == 0:
                total_t1 += 3
            else:
                total_t2 += 3

        # ── Play 10 turns ───────────────────────────────────────────────────
        round_centi_t1 = np.int32(0)
        round_centi_t2 = np.int32(0)
        first = np.int8(selector)
        maraffa_forced = maraffa

        for turn in range(10):
            # Position 0..3 turn order (rotated from `first`)
            # Record played cards per position; we need them to compute winner.
            played_0 = np.int8(0); played_1 = np.int8(0)
            played_2 = np.int8(0); played_3 = np.int8(0)

            lead_suit = np.int8(-1)

            for i in range(4):
                seat = (first + i) % 4

                # ── Pick slot ────────────────────────────────────────────────
                if i == 0 and turn == 0 and maraffa_forced:
                    # Must lead ace of briscola
                    chosen_slot = -1
                    for k in range(10):
                        if hands[seat, k] == ace_id:
                            chosen_slot = k
                            break
                elif i == 0:
                    # Any non-empty slot, uniform
                    nonempty = 0
                    for k in range(10):
                        if hands[seat, k] >= 0:
                            nonempty += 1
                    pick = np.random.randint(0, nonempty)
                    cnt = 0; chosen_slot = -1
                    for k in range(10):
                        if hands[seat, k] >= 0:
                            if cnt == pick:
                                chosen_slot = k
                                break
                            cnt += 1
                else:
                    # Follow lead suit if possible
                    matching = 0
                    for k in range(10):
                        v = hands[seat, k]
                        if v >= 0 and (v // 10) == lead_suit:
                            matching += 1
                    if matching > 0:
                        pick = np.random.randint(0, matching)
                        cnt = 0; chosen_slot = -1
                        for k in range(10):
                            v = hands[seat, k]
                            if v >= 0 and (v // 10) == lead_suit:
                                if cnt == pick:
                                    chosen_slot = k
                                    break
                                cnt += 1
                    else:
                        nonempty = 0
                        for k in range(10):
                            if hands[seat, k] >= 0:
                                nonempty += 1
                        pick = np.random.randint(0, nonempty)
                        cnt = 0; chosen_slot = -1
                        for k in range(10):
                            if hands[seat, k] >= 0:
                                if cnt == pick:
                                    chosen_slot = k
                                    break
                                cnt += 1

                card = hands[seat, chosen_slot]
                hands[seat, chosen_slot] = -1
                if i == 0:
                    played_0 = card
                    lead_suit = card // 10
                elif i == 1:
                    played_1 = card
                elif i == 2:
                    played_2 = card
                else:
                    played_3 = card

            # ── Turn winner & points ─────────────────────────────────────────
            best_pow = np.int16(-1)
            best_pos = 0
            # Inline power for each of the 4 played cards
            for i in range(4):
                if i == 0: c = played_0
                elif i == 1: c = played_1
                elif i == 2: c = played_2
                else:       c = played_3
                suit = c // 10
                rank = (c % 10) + 1
                val = rank_value[rank]
                if suit == briscola:
                    pw = val + 100
                elif suit == lead_suit:
                    pw = val
                else:
                    pw = np.int16(0)
                if pw > best_pow:
                    best_pow = pw
                    best_pos = i

            winner_seat = (first + best_pos) % 4
            # Turn points
            turn_centi = (
                rank_points_centi[(played_0 % 10) + 1]
                + rank_points_centi[(played_1 % 10) + 1]
                + rank_points_centi[(played_2 % 10) + 1]
                + rank_points_centi[(played_3 % 10) + 1]
            )
            if winner_seat % 2 == 0:
                round_centi_t1 += np.int32(turn_centi)
            else:
                round_centi_t2 += np.int32(turn_centi)

            first = np.int8(winner_seat)

        # ── Last-trick bonus (+1 point) & floor ────────────────────────────
        if first % 2 == 0:
            round_centi_t1 += np.int32(100)
        else:
            round_centi_t2 += np.int32(100)
        total_t1 += round_centi_t1 // 100
        total_t2 += round_centi_t2 // 100

        # Rotate selector for next round
        selector = np.int8((selector + 1) % 4)

    return total_t1, total_t2


@njit(cache=True, parallel=True, boundscheck=False)
def simulate_batch_numba(n_games, seed):
    """Simulate ``n_games`` games in parallel threads, each with its own seed."""
    results = np.zeros((n_games, 2), dtype=np.int32)
    rv = _RANK_VALUE
    rpc = _RANK_POINTS_CENTI
    for g in prange(n_games):
        np.random.seed(seed + g)
        t1, t2 = _play_one(rv, rpc)
        results[g, 0] = t1
        results[g, 1] = t2
    return results
