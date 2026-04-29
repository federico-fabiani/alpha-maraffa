"""Belief tracking + determinization for Marafone with hidden hands.

Public API
----------
- ``BeliefState``: tracks for the *root seat* what is known/unknown
  about the other three seats' hands.
- ``BeliefState.from_state(state, root_seat)``: build from a fast_engine
  ``GameState`` after observing all played cards.
- ``BeliefState.update_from_play(...)``: apply hard constraints when a
  seat plays a card (suit-following, declarations).
- ``determinize(belief, rng)``: sample a consistent assignment of
  hidden cards to opponent hands.  Returns ``int8[3, max_hand]`` cards
  per non-root seat plus their lengths.

Constraints modelled
--------------------
* **Hard void**: seat known to have no card of suit X.
  Sources: played off-suit when X was led; declared volo on suit X;
  card-counting (played + my-hand uses up all 10 of suit X).
* **Has-cards in suit X**: seat known to hold ≥1 card of suit X.
  Sources: declared striscio (after the lead) or busso, and is therefore
  not yet void.  Soft: weight increases sampling chance for that suit.
* **Hand size**: every non-root seat has a fixed number of remaining
  cards = ``HAND_SIZE - turns_with_play_for_that_seat``.

Sampling algorithm
------------------
Rejection-free constraint propagation:

1. Start with the set of unseen cards (= all 40 minus played minus my hand).
2. Compute, for each (seat, suit) pair, max-allowed count.
   - Hard void → 0.
   - Otherwise → unbounded (≤ remaining hand size).
3. Use **iterative max-flow style** allocation: for each card pick a
   compatible seat weighted by remaining hand size and "wants suit"
   bias from striscio/busso/has-cards observations.  If the partial
   assignment runs out of capacity, restart (rare in practice).

This is a Monte-Carlo determinization standard for trick-taking games
(e.g. Cowling-Powley-Whitehouse 2012).  Bias weights drive the
distribution toward plausible deals — much better than uniform
sampling because uniform ignores observed declarations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from .fast_engine import (
    NUM_CARDS, NUM_SEATS, HAND_SIZE,
    CARD_TO_SUIT, CARD_TO_RANK, CARD_VALUE,
    DECL_NONE, DECL_BUSSO, DECL_STRISCIO, DECL_VOLO,
    GameState,
)


# ── Belief state ───────────────────────────────────────────────────────────────

@dataclass
class BeliefState:
    """What the root seat knows about the other 3 seats.

    Attributes
    ----------
    root_seat
        Seat whose hand we *do* know directly.
    void
        bool[4, 4]: ``void[seat, suit]`` is True when ``seat`` is known
        to hold no card of ``suit``.  ``void[root_seat, *]`` is set
        from the actual root hand.
    must_have
        bool[4, 4]: ``must_have[seat, suit]`` is True when ``seat`` is
        currently known to hold ≥1 card of ``suit`` (e.g. just declared
        striscio or busso and has not yet played the suit since).
    n_cards
        int[4]: remaining hand size of each seat.
    unseen_mask
        int (40-bit): set of cards whose owner is unknown to root.
        Excludes both played cards and root's own hand.
    """
    root_seat:    int                = 0
    void:         np.ndarray         = field(default_factory=lambda: np.zeros((NUM_SEATS, 4), dtype=bool))
    must_have:    np.ndarray         = field(default_factory=lambda: np.zeros((NUM_SEATS, 4), dtype=bool))
    n_cards:      np.ndarray         = field(default_factory=lambda: np.full(NUM_SEATS, HAND_SIZE, dtype=np.int8))
    unseen_mask:  int                = 0

    @classmethod
    def from_state(cls, state: GameState, root_seat: int) -> "BeliefState":
        """Build a belief by replaying every observed card from a finished or in-progress state."""
        b = cls(root_seat=root_seat)
        b.n_cards[:] = state.n_cards
        # Unseen = all cards minus played minus root's hand.
        all_cards = (1 << NUM_CARDS) - 1
        root_hand_mask = 0
        rh = state.hands[root_seat]
        for c in rh:
            if c >= 0:
                root_hand_mask |= (1 << int(c))
        b.unseen_mask = all_cards & ~state.played_mask & ~root_hand_mask

        # Apply: root knows everything in its own hand, so it's void in suits not in hand.
        suits_in_root_hand = set()
        for c in rh:
            if c >= 0:
                suits_in_root_hand.add(int(CARD_TO_SUIT[c]))
        for suit in range(4):
            if suit not in suits_in_root_hand:
                b.void[root_seat, suit] = True

        # Replay played cards in turn order to recover declarations + suit-follow constraints.
        # We can't recover the lead seat per trick from card_owner alone without the trick
        # boundaries, so we use card_turn to group.
        played = [(int(state.card_turn[c]), int(c), int(state.card_owner[c]), int(state.card_decl[c]))
                  for c in range(NUM_CARDS) if state.played_mask & (1 << c)]
        played.sort()  # by turn, then card_id (deterministic)

        # Group by turn_num — within a turn, the play order is preserved by card_owner sequence.
        # We need lead seat per turn; we recover it as: in each completed trick, the lead is the
        # seat whose card has DECL != -1 OR (no decl) the seat that played first; we can't
        # reliably recover ordering from this snapshot alone, so we approximate using the
        # first card in turn order with a non-NONE declaration (always recorded for the lead).
        turn_groups: dict[int, list[tuple[int,int,int]]] = {}
        for turn, cid, owner, decl in played:
            turn_groups.setdefault(turn, []).append((cid, owner, decl))

        # ── per-trick logic ──
        for turn in sorted(turn_groups):
            entries = turn_groups[turn]
            # Lead detection: card_is_lead flag identifies the leading card precisely.
            lead_idx = -1
            for i, (cid, owner, decl) in enumerate(entries):
                if state.card_is_lead[cid]:
                    lead_idx = i
                    break
            if lead_idx < 0:
                continue
            lead_cid   = entries[lead_idx][0]
            lead_owner = entries[lead_idx][1]
            lead_decl  = entries[lead_idx][2]
            lead_suit  = int(CARD_TO_SUIT[lead_cid])

            # Lead declaration constraints.
            if lead_decl == DECL_VOLO:
                b.void[lead_owner, lead_suit] = True
            elif lead_decl == DECL_STRISCIO:
                b.must_have[lead_owner, lead_suit] = True
            elif lead_decl == DECL_BUSSO:
                # busso means strongest of the suit is OUT (not held by lead) and lead holds 2nd.
                # Encode as must_have for the suit; specific rank inference is hard from snapshot.
                b.must_have[lead_owner, lead_suit] = True

            # Followers: any card not of lead suit reveals void in lead suit.
            for cid, owner, _ in entries:
                if owner == lead_owner:
                    continue
                if int(CARD_TO_SUIT[cid]) != lead_suit:
                    b.void[owner, lead_suit] = True

        # ── Card-counting void inference ──
        # If played + root_hand_count for a suit equals 10, all opponents are void there.
        for suit in range(4):
            n_played_suit = 0
            for c in range(NUM_CARDS):
                if (state.played_mask & (1 << c)) and CARD_TO_SUIT[c] == suit:
                    n_played_suit += 1
            n_root_suit = sum(1 for c in rh if c >= 0 and int(CARD_TO_SUIT[c]) == suit)
            if n_played_suit + n_root_suit >= 10:
                for seat in range(NUM_SEATS):
                    if seat != root_seat:
                        b.void[seat, suit] = True

        return b


# ── Determinization ────────────────────────────────────────────────────────────

class DeterminizeError(RuntimeError):
    """Constraint set was infeasible after retries."""


def determinize(
    belief:        BeliefState,
    rng:           np.random.Generator,
    max_attempts:  int = 30,
) -> np.ndarray:
    """Sample a consistent assignment of unseen cards to non-root seats.

    Returns
    -------
    hands_out : int8[NUM_SEATS, HAND_SIZE]
        Full hand for every seat including root (root is copied unchanged
        from belief.unseen_mask + caller's responsibility — actually root
        is filled with -1 here; callers compose with the state's known
        root hand).
        For non-root seats, the first ``belief.n_cards[seat]`` slots hold
        sampled cards; remaining slots are -1.
    """
    unseen = [c for c in range(NUM_CARDS) if (belief.unseen_mask >> c) & 1]
    targets = [s for s in range(NUM_SEATS) if s != belief.root_seat]
    capacity = {s: int(belief.n_cards[s]) for s in targets}

    if sum(capacity.values()) != len(unseen):
        raise DeterminizeError(
            f"Capacity mismatch: unseen={len(unseen)} sum_n_cards={sum(capacity.values())}")

    for attempt in range(max_attempts):
        result = _try_determinize(belief, unseen, targets, capacity, rng)
        if result is not None:
            return result

    raise DeterminizeError(f"Failed to determinize after {max_attempts} attempts")


def _try_determinize(
    belief:    BeliefState,
    unseen:    List[int],
    targets:   List[int],
    capacity:  dict,
    rng:       np.random.Generator,
) -> Optional[np.ndarray]:
    """Single attempt at constraint-satisfying allocation.  Returns None on failure."""
    rem_cap = dict(capacity)
    out = np.full((NUM_SEATS, HAND_SIZE), -1, dtype=np.int8)
    out_count = {s: 0 for s in targets}

    # Sort unseen cards by *fewest compatible seats first* to surface infeasibility early.
    def n_compatible(card_id: int) -> int:
        suit = int(CARD_TO_SUIT[card_id])
        return sum(1 for s in targets if not belief.void[s, suit] and rem_cap[s] > 0)

    order = sorted(unseen, key=lambda c: (n_compatible(c), int(rng.integers(0, 1 << 30))))

    for card in order:
        suit = int(CARD_TO_SUIT[card])
        candidates = []
        weights    = []
        for s in targets:
            if belief.void[s, suit]:
                continue
            if rem_cap[s] <= 0:
                continue
            # Weight: remaining capacity × (1 + must_have bias).
            w = rem_cap[s] * (3.0 if belief.must_have[s, suit] else 1.0)
            candidates.append(s)
            weights.append(w)
        if not candidates:
            return None
        weights_arr = np.asarray(weights, dtype=np.float64)
        weights_arr /= weights_arr.sum()
        chosen = candidates[int(rng.choice(len(candidates), p=weights_arr))]
        out[chosen, out_count[chosen]] = card
        out_count[chosen] += 1
        rem_cap[chosen] -= 1

    # Verify must_have satisfaction; reject if any unmet.
    for s in targets:
        for suit in range(4):
            if belief.must_have[s, suit]:
                row = out[s]
                has = any(c >= 0 and int(CARD_TO_SUIT[c]) == suit for c in row)
                if not has:
                    return None
    return out


# ── Helper: reconstruct full state from belief + sampled hands ────────────────

def state_from_determinization(
    base_state:     GameState,
    sampled_hands:  np.ndarray,
    root_seat:      int,
) -> GameState:
    """Build a fully-observed GameState by combining root's true hand with
    sampled opponent hands.

    The returned state is independent of ``base_state`` (deep-copied).
    """
    from .fast_engine import copy_state
    s = copy_state(base_state)
    for seat in range(NUM_SEATS):
        if seat == root_seat:
            continue
        s.hands[seat] = sampled_hands[seat]
        s.n_cards[seat] = int((sampled_hands[seat] >= 0).sum())
    return s
