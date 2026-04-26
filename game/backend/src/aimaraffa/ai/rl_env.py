"""Single-game Maraffa environment for PPO rollout collection.

Public entry point
------------------
``run_episode(policy, device, opponent, rng)`` → ``list[DecisionRecord]``

Runs one complete game (multiple rounds until a team reaches 41 points).
All 4 seats use ``policy`` for self-play; optionally a HeuristicAgent can
replace team-2 (seats 1, 3) for the grounding curriculum.

Reward signal
-------------
After each completed trick the 4 participating decisions receive an
*incremental* reward equal to:

  r_i = pts_earned_this_trick × sign_i
        where sign_i = +1 if my_team won the trick, else -1

After a round completes the last-trick bonus (+1 pt to winner) is
distributed to the 4 decisions of the last trick.  This produces a dense
per-step signal that exactly decomposes the supervised ``future_pts_diff``
target when summed from each decision to round-end.

Feature rows are built with the same ``Simulator._build_base_row`` +
``_expand_candidates`` infrastructure as the XGBoost training path, so
the encoding is byte-for-byte identical.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from math import floor
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch

from aimaraffa.engine import (
    Card, Deck, Suit,
    GAME_WIN_THRESHOLD, KEY_CARD, RANK_TO_POINTS,
    determine_turn_winner,
    get_valid_cards, get_valid_declarations,
)
from aimaraffa.agents.heuristic_agent import HeuristicAgent

from .simulator import (
    Simulator,
    _GameState,
    _TEAM,
    _SEATS,
    _SUIT_ENC,
)
from .rl_model import MarafonePolicy


# ── Decision record ────────────────────────────────────────────────────────────

@dataclass
class DecisionRecord:
    """One agent decision within an episode — filled in two phases.

    Phase 1 (at decision time): feats, action, log_prob, value, seat, team.
    Phase 2 (after trick/round): reward.
    """
    feats:    np.ndarray    # [n_cands, n_features] — candidate feature rows
    n_cands:  int           # number of valid candidates (<= feats.shape[0])
    action:   int           # sampled candidate index
    log_prob: float         # log π(a|s)
    value:    float         # V̂(s)
    reward:   float = 0.0  # filled retroactively after trick completes
    seat:     int   = 0
    team:     int   = 1    # 1 or 2


# ── Briscola-selection candidate builder ───────────────────────────────────────

def _briscola_candidates(
    state:     "_GameState",
    seat:      int,
    round_num: int,
    sim:       "Simulator",
) -> Tuple[np.ndarray, List[Suit]]:
    """Build one representative feature row per suit for briscola selection.

    For each of the 4 suits we temporarily set ``state.briscola`` to that
    suit, then build a base row using the first card in hand as the
    representative lead.  The policy evaluates these 4 rows and picks a suit.

    Returns:
        feat_matrix: [4, N_FEATURES] float32
        suits_list:  [4] ordered list of Suit values matching the rows
    """
    suits_list = list(Suit)
    hand       = state.hands[seat]
    rows: List[np.ndarray] = []

    orig_briscola = state.briscola  # None during briscola selection

    for suit in suits_list:
        state.briscola = suit          # temporarily set for _build_base_row

        if hand:
            # Use the first valid card as the representative opening.
            rep_card = hand[0]
            lead_val = rep_card.suit.value
        else:
            lead_val = suit.value

        base = sim._build_base_row(
            state, seat, round_num, 0,
            lead_suit_value=lead_val, is_lead_pos=True,
        )
        rows.append(base)

    state.briscola = orig_briscola     # restore

    return np.stack(rows), suits_list   # [4, N_FEATURES], [4 suits]


# ── Card-play candidate builder ────────────────────────────────────────────────

def _card_candidates(
    state:     "_GameState",
    seat:      int,
    round_num: int,
    turn_num:  int,
    position:  int,
    sim:       "Simulator",
) -> Tuple[np.ndarray, List[Tuple[Card, Optional[str]]]]:
    """Build ``[n_cands, N_FEATURES]`` matrix + candidate list for one play."""
    hand      = state.hands[seat]
    lead_suit = state.table_tuples[0][1].suit if state.table_tuples else None
    is_lead   = (position == 0)

    if state.maraffa_forced and seat == state.briscola_selector and lead_suit is None:
        forced = Card(state.briscola, 1)
        decls  = get_valid_declarations([c for c in hand if c != forced], forced.suit)
        cands: List[Tuple[Card, Optional[str]]] = [(forced, d) for d in decls]
    else:
        valid = get_valid_cards(hand, lead_suit)
        if is_lead:
            cands = []
            for card in valid:
                after = [c for c in hand if c != card]
                for decl in get_valid_declarations(after, card.suit):
                    cands.append((card, decl))
        else:
            cands = [(card, None) for card in valid]

    briscola_str   = state.briscola.value
    all_row_blocks: List[np.ndarray] = []

    if is_lead:
        by_suit: Dict[str, List[Tuple[Card, Optional[str]]]] = {}
        for cand in cands:
            by_suit.setdefault(cand[0].suit.value, []).append(cand)
        ordered_cands: List[Tuple[Card, Optional[str]]] = []
        for sv, group in by_suit.items():
            base = sim._build_base_row(
                state, seat, round_num, turn_num,
                lead_suit_value=sv, is_lead_pos=True,
            )
            block = sim._expand_candidates(base, group, briscola_str, sv)
            all_row_blocks.append(block)
            ordered_cands.extend(group)
        cands = ordered_cands
    else:
        lead_val = lead_suit.value   # type: ignore[union-attr]
        base  = sim._build_base_row(
            state, seat, round_num, turn_num,
            lead_suit_value=lead_val, is_lead_pos=False,
        )
        block = sim._expand_candidates(base, cands, briscola_str, lead_val)
        all_row_blocks.append(block)

    arr = (
        np.concatenate(all_row_blocks, axis=0)
        if len(all_row_blocks) > 1
        else all_row_blocks[0]
    )
    return arr, cands


# ── Episode runner ─────────────────────────────────────────────────────────────

def run_episode(
    policy:   MarafonePolicy,
    device:   str,
    opponent: Optional[HeuristicAgent] = None,
    rng:      Optional[random.Random]  = None,
    seed:     Optional[int]            = None,
) -> List[DecisionRecord]:
    """Play one complete game, returning all agent decisions with rewards.

    Args:
        policy:   The current RL policy, controlling all seats (or team-1
                  seats when ``opponent`` is set).
        device:   Torch device string ("cpu" / "cuda").
        opponent: When not None, this HeuristicAgent controls team-2 (seats
                  1, 3); used for the grounding curriculum.
        rng:      Pre-seeded random.Random; a fresh one is created if None.
        seed:     Seed for a fresh rng (ignored when rng is supplied).

    Returns:
        List of ``DecisionRecord`` with rewards filled in.  One record per
        policy decision (briscola selection + card plays for team-1 seats,
        plus card plays for team-2 seats when opponent is None).
    """
    if rng is None:
        rng = random.Random(seed)

    # Create a Simulator with no model — we only borrow its stateless
    # _build_base_row / _expand_candidates helpers (no inference).
    sim = Simulator(model_path=None)

    state = _GameState()
    state.briscola_selector = None
    records: List[DecisionRecord] = []

    policy.eval()

    def _policy_owns(seat: int) -> bool:
        return opponent is None or _TEAM[seat] == 1

    def _select_card_heuristic(
        seat: int, round_num: int, turn_num: int, position: int
    ) -> Tuple[Card, Optional[str]]:
        hand     = state.hands[seat]
        lead_s   = state.table_tuples[0][1].suit if state.table_tuples else None
        is_lead  = (position == 0)

        if state.maraffa_forced and seat == state.briscola_selector and lead_s is None:
            forced = Card(state.briscola, 1)
            decls  = get_valid_declarations([c for c in hand if c != forced], forced.suit)
            return forced, rng.choice(decls)

        ctx  = sim._build_ctx(state, seat, round_num, turn_num)
        card, decl = opponent.select_card(ctx, state.briscola)   # type: ignore[union-attr]
        return card, (decl if is_lead else None)

    def _query_policy(
        feats: np.ndarray, seat: int, team: int
    ) -> DecisionRecord:
        t = torch.from_numpy(feats).float().to(device)
        with torch.no_grad():
            action_t, log_prob_t, value_t = policy.act_sample(t)
        rec = DecisionRecord(
            feats    = feats,
            n_cands  = feats.shape[0],
            action   = int(action_t.item()),
            log_prob = float(log_prob_t.item()),
            value    = float(value_t.item()),
            seat     = seat,
            team     = team,
        )
        records.append(rec)
        return rec

    round_num = 0

    while max(state.total_scores.values()) < GAME_WIN_THRESHOLD:
        round_num += 1

        # ── Deal ─────────────────────────────────────────────────────────────
        deck = Deck()
        deck.shuffle()
        for s in _SEATS:
            state.hands[s] = deck.cards[s * 10:(s + 1) * 10]

        if state.briscola_selector is None:
            for s in _SEATS:
                if KEY_CARD in state.hands[s]:
                    state.briscola_selector = s
                    break

        state.round_history  = {}
        state.round_scores   = {1: 0.0, 2: 0.0}
        state.table_tuples   = []
        state.maraffa_forced = False

        if opponent is not None:
            opponent.reset_round()

        # ── Briscola selection ────────────────────────────────────────────────
        sel_seat = state.briscola_selector
        if _policy_owns(sel_seat):
            feats, suits_list = _briscola_candidates(state, sel_seat, round_num, sim)
            rec  = _query_policy(feats, sel_seat, _TEAM[sel_seat])
            # action is the suit index (0–3)
            state.briscola = suits_list[rec.action % len(suits_list)]
        else:
            ctx = sim._build_ctx(state, sel_seat, round_num, turn_num=0)
            state.briscola = opponent.select_briscola(ctx)   # type: ignore[union-attr]

        # Maraffa bonus check
        hand_sel = state.hands[sel_seat]
        mar = [c for c in hand_sel if c.suit == state.briscola and c.rank in (1, 2, 3)]
        if len(mar) == 3:
            state.total_scores[_TEAM[sel_seat]] += 3
            state.maraffa_forced = True
        state.first_of_turn = sel_seat

        # Track record indices per trick for retroactive reward assignment.
        trick_records: List[List[int]] = []

        # ── 10 turns ──────────────────────────────────────────────────────────
        for turn_idx in range(10):
            turn_num = turn_idx + 1
            state.table_tuples   = []
            state.maraffa_forced = False
            trick_rec_indices:  List[int] = []

            for position in range(4):
                seat = (state.first_of_turn + position) % 4
                team = _TEAM[seat]

                if _policy_owns(seat):
                    feats, cands = _card_candidates(
                        state, seat, round_num, turn_num, position, sim,
                    )
                    rec   = _query_policy(feats, seat, team)
                    # Clamp action index in case feats was padded.
                    action_idx = rec.action % len(cands)
                    card, decl = cands[action_idx]
                    trick_rec_indices.append(len(records) - 1)
                else:
                    card, decl = _select_card_heuristic(seat, round_num, turn_num, position)

                declaration = decl if position == 0 else None

                state.hands[seat].remove(card)
                key = f"{card.suit.value}_{card.rank}"
                state.round_history[key] = (seat, turn_num, declaration or "")
                state.table_tuples.append((seat, card))

                if opponent is not None:
                    opponent.record_card(card, seat, turn_num, declaration)

            # ── Trick resolution + reward ─────────────────────────────────────
            winner_seat = determine_turn_winner(state.table_tuples, state.briscola)
            winner_team = _TEAM[winner_seat]
            pts         = sum(RANK_TO_POINTS[c.rank] for _, c in state.table_tuples)
            state.round_scores[winner_team] += pts
            state.first_of_turn = winner_seat

            for idx in trick_rec_indices:
                rec_team = records[idx].team
                records[idx].reward = pts * (1.0 if rec_team == winner_team else -1.0)

            trick_records.append(trick_rec_indices)

        # ── Last-trick bonus + floor + totals ─────────────────────────────────
        last_winner_team = _TEAM[state.first_of_turn]
        state.round_scores[last_winner_team] += 1.0

        if trick_records:
            for idx in trick_records[-1]:
                rec_team = records[idx].team
                records[idx].reward += 1.0 * (1.0 if rec_team == last_winner_team else -1.0)

        s1 = int(floor(state.round_scores[1]))
        s2 = int(floor(state.round_scores[2]))
        state.total_scores[1] += s1
        state.total_scores[2] += s2

        if max(state.total_scores.values()) < GAME_WIN_THRESHOLD:
            state.briscola_selector = (state.briscola_selector + 1) % 4

    return records
