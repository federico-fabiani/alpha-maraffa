"""Self-play data generation for AlphaZero-style Marafone training.

One round = one imperfect-info game with independent deal. Each
decision in the round invokes ISMCTS to get a visit distribution
``pi_target`` and a state value (averaged at root).  The round-end
margin (in [-1, +1]) is broadcast to every recorded decision as the
value target ``z``.

Data record (per decision)
--------------------------
    state_feats   float32[STATE_DIM]
    legal_mask    bool   [N_ACTIONS]
    pi_target     float32[N_ACTIONS]   # zero outside legal indices
    z             float32              # round-end margin in [-1, +1]
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import numpy as np

from aimaraffa.agents.heuristic_agent import HeuristicAgent
from aimaraffa.engine import Suit

from .belief        import BeliefState
from .fast_engine   import (
    NUM_SEATS, SEAT_TO_TEAM, ROUND_TOTAL_POINTS3,
    DECL_NONE, GameState,
    deal_round, apply_card, seat_to_play,
)
from .az_features   import (
    encode_state, legal_action_mask, split_action,
)
from .ismcts        import ISMCTS

logger = logging.getLogger(__name__)


# ── Decision record ────────────────────────────────────────────────────────────

@dataclass
class AZRecord:
    state_feats: np.ndarray   # float32[STATE_DIM]
    legal_mask:  np.ndarray   # bool   [N_ACTIONS]
    pi_target:   np.ndarray   # float32[N_ACTIONS]
    seat:        int
    team:        int          # 1 or 2 (matches engine convention)
    z:           float = 0.0  # filled at round end


# ── Heuristic adapter for opponents ────────────────────────────────────────────

def _heuristic_decide(
    state:       GameState,
    seat:        int,
    heuristic:   HeuristicAgent,
    rng:         random.Random,
) -> Tuple[int, int]:
    """Use the existing HeuristicAgent to choose a card+declaration.

    The heuristic operates on engine.Card / Suit objects, so we marshal
    in/out at this boundary.  Returns ``(card_id, decl_int)``.
    """
    from .fast_engine import engine_card_from_id, suit_from_id

    # Build context dict the heuristic expects.
    hand_engine = [engine_card_from_id(int(c)) for c in state.hands[seat] if c >= 0]
    table_cards = [
        (int(state.table_seats[i]), engine_card_from_id(int(state.table_cards[i])))
        for i in range(state.table_pos)
    ]
    # Convert raw_scores (thirds) into approximate floor-fraction; the heuristic
    # only really uses round_scores qualitatively, so a thirds-style float works.
    rs1 = float(state.raw_scores[0]) / 3.0
    rs2 = float(state.raw_scores[1]) / 3.0
    ctx = {
        "seat":                   seat,
        "round_num":              1,
        "turn_num":               state.turn_num + 1,
        "briscola_selector_seat": state.briscola_selector,
        "briscola":               suit_from_id(state.briscola),
        "table_cards":            table_cards,
        "round_scores":           {1: rs1, 2: rs2},
        "total_scores":           {1: 0, 2: 0},
        "hand":                   hand_engine,
    }
    bris = suit_from_id(state.briscola)
    is_lead = (state.table_pos == 0)
    card, decl_str = heuristic.select_card(ctx, bris)
    cid = card.suit.value  # we want id; reach into mapping
    from .fast_engine import card_id_from_engine
    cid = card_id_from_engine(card)
    if not is_lead:
        decl_str = None
    decl_map = {None: DECL_NONE, "busso": 0, "striscio": 1, "volo": 2}
    return cid, decl_map.get(decl_str, DECL_NONE)


def _heuristic_select_briscola(
    state: GameState, seat: int, heuristic: HeuristicAgent
) -> int:
    from .fast_engine import engine_card_from_id, suit_id
    hand = [engine_card_from_id(int(c)) for c in state.hands[seat] if c >= 0]
    ctx = {"hand": hand}
    return suit_id(heuristic.select_briscola(ctx))


def _record_card_in_heuristic(
    heuristic: HeuristicAgent,
    state:     GameState,
    seat:      int,
    cid:       int,
    decl:      int,
    is_lead:   bool,
) -> None:
    from .fast_engine import engine_card_from_id
    decl_map = {DECL_NONE: None, 0: "busso", 1: "striscio", 2: "volo"}
    heuristic.record_card(
        engine_card_from_id(cid),
        seat,
        state.turn_num + 1,
        decl_map.get(decl) if is_lead else None,
    )


# ── Single self-play round ────────────────────────────────────────────────────

def play_selfplay_round(
    eval_fn:                 Callable,
    *,
    n_simulations:           int   = 64,
    n_determinizations:      int   = 16,
    c_puct:                  float = 1.5,
    dirichlet_alpha:         float = 0.3,
    dirichlet_eps:           float = 0.25,
    temperature:             float = 1.0,
    temp_falloff_turn:       int   = 4,
    rng_np:                  Optional[np.random.Generator] = None,
    rng_py:                  Optional[random.Random]       = None,
    briscola_selector:       Optional[int] = None,
    opponent_heuristic_team: Optional[int] = None,
) -> List[AZRecord]:
    """Play one round; return all decision records made by the AZ policy.

    When ``opponent_heuristic_team`` is set (1 or 2), that team's seats
    are controlled by HeuristicAgent (no ISMCTS, no records).  This
    is the **curriculum** option for grounded play during early
    iterations.  When ``None`` (default), all 4 seats use ISMCTS — pure
    self-play.
    """
    rng_np = rng_np or np.random.default_rng()
    rng_py = rng_py or random.Random()

    # Random briscola selector if unspecified.
    sel = briscola_selector if briscola_selector is not None else rng_py.randrange(NUM_SEATS)
    state = deal_round(rng_np, briscola_selector=sel)

    # Briscola selection: use heuristic if available, else simple "longest suit" rule.
    heuristic_pool: Optional[List[HeuristicAgent]] = None
    if opponent_heuristic_team is not None:
        heuristic_pool = [HeuristicAgent() for _ in range(NUM_SEATS)]
        for h in heuristic_pool:
            h.reset_round()

    # Briscola — selector picks longest suit, ties broken by cricca presence.
    # Reuse HeuristicAgent.select_briscola for fairness even in pure self-play.
    pseudo_h = heuristic_pool[sel] if heuristic_pool else HeuristicAgent()
    state.briscola = _heuristic_select_briscola(state, sel, pseudo_h)

    # Maraffa (cricca) check.
    sel_hand = state.hands[sel]
    sel_briscola_cards = [int(c) for c in sel_hand if c >= 0 and (int(c) // 10) == state.briscola]
    has_cricca = (
        len(sel_briscola_cards) >= 3
        and any((c % 10) == 0 for c in sel_briscola_cards)   # rank 1 (ace)
        and any((c % 10) == 1 for c in sel_briscola_cards)   # rank 2
        and any((c % 10) == 2 for c in sel_briscola_cards)   # rank 3
    )
    if has_cricca:
        state.maraffa_forced = True
        # Bonus +3 points = +9 thirds added to selector's team raw score.
        state.raw_scores[int(SEAT_TO_TEAM[sel])] += 9

    state.first_of_turn = sel

    mcts = ISMCTS(
        eval_fn               = eval_fn,
        c_puct                = c_puct,
        n_simulations         = n_simulations,
        n_determinizations    = n_determinizations,
        dirichlet_alpha       = dirichlet_alpha,
        dirichlet_eps         = dirichlet_eps,
        seed                  = int(rng_py.random() * 1e9),
    )

    records: List[AZRecord] = []

    while not state.round_complete:
        seat = seat_to_play(state)
        team = int(SEAT_TO_TEAM[seat]) + 1   # to match 1/2 convention used in tournament

        # Heuristic-controlled seat → no MCTS, no record.
        if opponent_heuristic_team is not None and team == opponent_heuristic_team:
            h = heuristic_pool[seat]
            cid, decl = _heuristic_decide(state, seat, h, rng_py)
            is_lead = (state.table_pos == 0)
            for hh in heuristic_pool:
                _record_card_in_heuristic(hh, state, seat, cid, decl, is_lead)
            apply_card(state, seat, cid, decl)
            continue

        # AZ-controlled seat → ISMCTS search + sample/argmax action.
        belief = BeliefState.from_state(state, seat)
        # Inject Dirichlet noise only at root in self-play.
        mcts.dirichlet_eps = dirichlet_eps
        pi_target, _ = mcts.search(state, root_seat=seat, belief=belief)

        feats = encode_state(state, seat, belief)
        mask  = legal_action_mask(state, seat)

        # Sample temperature-controlled (or argmax after fall-off).
        turn_idx = state.turn_num   # tricks completed so far
        if temperature > 0 and turn_idx < temp_falloff_turn:
            probs = pi_target.astype(np.float64)
            if temperature != 1.0:
                probs = np.power(probs + 1e-12, 1.0 / temperature)
            s = probs.sum()
            if s <= 0:
                action_idx = int(np.argmax(pi_target))
            else:
                probs = probs / s
                action_idx = int(rng_np.choice(len(probs), p=probs))
        else:
            action_idx = int(np.argmax(pi_target))

        records.append(AZRecord(
            state_feats = feats,
            legal_mask  = mask,
            pi_target   = pi_target,
            seat        = seat,
            team        = team,
        ))

        cid, decl = split_action(action_idx)
        if heuristic_pool is not None:
            for hh in heuristic_pool:
                _record_card_in_heuristic(hh, state, seat, cid, decl, state.table_pos == 0)
        apply_card(state, seat, cid, decl)

    # ── Round end: assign z to every record from its team's perspective ──
    diff_thirds = int(state.raw_scores[0] - state.raw_scores[1])  # team1 - team2
    z_team1 = max(-1.0, min(1.0, diff_thirds / float(ROUND_TOTAL_POINTS3)))
    for r in records:
        r.z = z_team1 if r.team == 1 else -z_team1

    return records
