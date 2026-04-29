"""State feature encoder for the AlphaZero-style Marafone network.

Output is a flat float32 vector summarising the public state + the root
seat's private hand.  The encoder is **state-only** (no candidate); the
network's policy head emits logits over the fixed (card, declaration)
action space.

Layout
------
``encode_state(state, root_seat)`` returns float32[STATE_DIM] with:

    [   0 :  40 ]  one-hot — cards in *root* hand
    [  40 :  80 ]  one-hot — cards already played (any seat)
    [  80 : 120 ]  one-hot — cards owned by *partner* among played
    [ 120 : 160 ]  one-hot — cards owned by *opp_left* among played (next seat)
    [ 160 : 200 ]  one-hot — cards owned by *opp_right* among played (prev seat)
    [ 200 : 204 ]  one-hot — briscola suit
    [ 204 : 208 ]  one-hot — current trick lead suit (zero if leading)
    [ 208 : 212 ]  one-hot — own seat (0..3)
    [ 212 : 220 ]  position-in-trick one-hot (0..3) + relative seat to selector (0..3)
    [ 220 : 230 ]  turn_num one-hot (1..10)
    [ 230 : 234 ]  table cards (0..3): for each position, normalized power-rank.
    [ 234 : 250 ]  per-seat-per-suit void flags (4 seats × 4 suits)
    [ 250 : 266 ]  per-seat-per-suit must_have flags (4 seats × 4 suits)
    [ 266 : 270 ]  remaining hand size of each seat / 10
    [ 270 : 273 ]  current trick partial points (mine, partner-team, opp-team) / 11
    [ 273 : 276 ]  round score so far (mine, opp) / 35  + bias
    [ 276 : 280 ]  declarations seen this round (busso/striscio/volo by my partner / by opps)
    [ 280 : 284 ]  reserved (zero)

Total: STATE_DIM = 284 features.

Action space
------------
160 actions = 40 cards × 4 declaration slots.  Index = card_id * 4 + decl
where decl ∈ {0=NONE, 1=BUSSO, 2=STRISCIO, 3=VOLO}.

Only legal indices are unmasked; ``legal_action_mask(state, seat, belief)``
returns a bool[160] mask used for both policy sampling and CE-loss masking.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from .fast_engine import (
    NUM_CARDS, NUM_SEATS, HAND_SIZE,
    CARD_TO_SUIT, CARD_TO_RANK, CARD_VALUE, CARD_POINTS3,
    DECL_NONE, DECL_BUSSO, DECL_STRISCIO, DECL_VOLO,
    GameState, hand_view, legal_card_actions, valid_declarations,
    SEAT_TO_TEAM, lead_suit, seat_to_play,
)
from .belief import BeliefState


STATE_DIM   = 284
N_ACTIONS   = 160     # 40 cards × 4 declarations
DECL_TO_IDX = {DECL_NONE: 0, DECL_BUSSO: 1, DECL_STRISCIO: 2, DECL_VOLO: 3}
IDX_TO_DECL = {v: k for k, v in DECL_TO_IDX.items()}


def action_index(card: int, decl: int) -> int:
    """Map (card_id, declaration) → flat action index in [0, 160)."""
    return card * 4 + DECL_TO_IDX[decl]


def split_action(idx: int) -> Tuple[int, int]:
    """Inverse of action_index — returns (card_id, decl)."""
    return idx // 4, IDX_TO_DECL[idx % 4]


# ── Mask construction ──────────────────────────────────────────────────────────

def legal_action_mask(s: GameState, seat: Optional[int] = None) -> np.ndarray:
    """Return bool[160] mask over the fixed action space."""
    if seat is None:
        seat = seat_to_play(s)
    mask = np.zeros(N_ACTIONS, dtype=bool)
    legal = legal_card_actions(s, seat)
    if s.table_pos == 0:
        # Lead: declaration matters; valid_declarations depends on the card.
        for c in legal:
            decls = valid_declarations(s, seat, int(c))
            for d in decls:
                mask[action_index(int(c), int(d))] = True
    else:
        # Follower: only DECL_NONE legal.
        for c in legal:
            mask[action_index(int(c), DECL_NONE)] = True
    return mask


# ── State encoder ─────────────────────────────────────────────────────────────

def encode_state(
    s:         GameState,
    root_seat: int,
    belief:    Optional[BeliefState] = None,
) -> np.ndarray:
    """Build the float32[STATE_DIM] feature vector.

    ``belief`` is used to fill the void/must_have blocks.  When None,
    a fresh BeliefState is built from the state (slower).
    """
    if belief is None:
        belief = BeliefState.from_state(s, root_seat)

    out = np.zeros(STATE_DIM, dtype=np.float32)

    partner    = (root_seat + 2) % 4
    opp_left   = (root_seat + 1) % 4
    opp_right  = (root_seat + 3) % 4

    # ── [0:40] cards in root hand ──
    rh = s.hands[root_seat]
    for c in rh:
        if c >= 0:
            out[int(c)] = 1.0

    # ── [40:80] cards already played ──
    for c in range(NUM_CARDS):
        if (s.played_mask >> c) & 1:
            out[40 + c] = 1.0
            owner = int(s.card_owner[c])
            if owner == partner:
                out[80 + c] = 1.0
            elif owner == opp_left:
                out[120 + c] = 1.0
            elif owner == opp_right:
                out[160 + c] = 1.0

    # ── [200:204] briscola suit ──
    if 0 <= s.briscola < 4:
        out[200 + s.briscola] = 1.0

    # ── [204:208] current trick lead suit (zero when leading) ──
    ls = lead_suit(s)
    if ls >= 0:
        out[204 + ls] = 1.0

    # ── [208:212] own seat ──
    out[208 + root_seat] = 1.0

    # ── [212:216] position in trick (0..3) ──
    out[212 + min(s.table_pos, 3)] = 1.0

    # ── [216:220] relative seat-to-selector ──
    rel = (root_seat - s.briscola_selector) % 4
    out[216 + rel] = 1.0

    # ── [220:230] turn_num one-hot (1..10) ──
    if 0 <= s.turn_num < HAND_SIZE:
        out[220 + s.turn_num] = 1.0

    # ── [230:234] table cards normalized strength (relative to briscola/lead) ──
    for i in range(s.table_pos):
        c = int(s.table_cards[i])
        suit = int(CARD_TO_SUIT[c])
        if suit == s.briscola:
            p = int(CARD_VALUE[c]) + 100
        elif suit == ls:
            p = int(CARD_VALUE[c])
        else:
            p = 0
        out[230 + i] = p / 113.0   # max: rank 3 briscola = 13+100=113

    # ── [234:250] void flags per seat per suit ──
    out[234:250] = belief.void.astype(np.float32).flatten()

    # ── [250:266] must_have flags per seat per suit ──
    out[250:266] = belief.must_have.astype(np.float32).flatten()

    # ── [266:270] remaining hand size / 10 per seat ──
    for seat in range(NUM_SEATS):
        out[266 + seat] = float(s.n_cards[seat]) / HAND_SIZE

    # ── [270:273] current trick partial points (mine, partner-team-not-mine, opp-team) ──
    my_team   = int(SEAT_TO_TEAM[root_seat])
    points_mine    = 0
    points_partner = 0
    points_opp     = 0
    for i in range(s.table_pos):
        c     = int(s.table_cards[i])
        owner = int(s.table_seats[i])
        pts3  = int(CARD_POINTS3[c])
        if owner == root_seat:
            points_mine += pts3
        elif int(SEAT_TO_TEAM[owner]) == my_team:
            points_partner += pts3
        else:
            points_opp += pts3
    out[270] = points_mine    / 11.0
    out[271] = points_partner / 11.0
    out[272] = points_opp     / 11.0

    # ── [273:276] round score so far (mine, opp) / 35 + bias ──
    my_team_idx = int(SEAT_TO_TEAM[root_seat])
    opp_team_idx = 1 - my_team_idx
    out[273] = float(s.raw_scores[my_team_idx])  / 35.0
    out[274] = float(s.raw_scores[opp_team_idx]) / 35.0
    out[275] = float(s.raw_scores[my_team_idx] - s.raw_scores[opp_team_idx]) / 35.0

    # ── [276:280] declarations summary (counts of each by partner-team / opp-team) ──
    decl_partner_busso = 0
    decl_partner_other = 0
    decl_opp_busso     = 0
    decl_opp_other     = 0
    for c in range(NUM_CARDS):
        if not s.card_is_lead[c]:
            continue
        d = int(s.card_decl[c])
        if d == DECL_NONE:
            continue
        owner = int(s.card_owner[c])
        is_my_team = (int(SEAT_TO_TEAM[owner]) == my_team)
        if is_my_team:
            if d == DECL_BUSSO:
                decl_partner_busso += 1
            else:
                decl_partner_other += 1
        else:
            if d == DECL_BUSSO:
                decl_opp_busso += 1
            else:
                decl_opp_other += 1
    out[276] = decl_partner_busso / 4.0
    out[277] = decl_partner_other / 4.0
    out[278] = decl_opp_busso     / 4.0
    out[279] = decl_opp_other     / 4.0

    return out
