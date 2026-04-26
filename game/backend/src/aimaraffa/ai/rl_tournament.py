"""Tournament for RL models — round-based, seat-balanced.

Metric: round-win rate (A wins round when floor(A_pts) > floor(B_pts)).

Each "game" in the API is one round.  Full games are NOT played because
rounds are independent — agents cannot leverage cross-round information —
so counting round wins is a cleaner, lower-variance signal.

Seat balance: the briscola-selector seat (first to table each round) is
cycled deterministically 0→1→2→3→0→… so every seat leads an equal
number of rounds.  No positional luck remains in the aggregate.

Side swap: half the rounds have A=team1, half have A=team2.  Both halves
use an identically seeded rng so the same deals are replayed with sides
swapped — a paired design that cancels card-luck from the comparison.

Public entry point
------------------
``rl_tournament(model_a, model_b, games, seed)`` → dict

    model_a / model_b may be:
        Path        — a .pt RL checkpoint (→ RLAgent, greedy)
        "heuristic" — rule-based HeuristicAgent
        None        — random play

Returns the same dict schema as before so existing format_report and
promotion logic work unchanged.
"""

from __future__ import annotations

import logging
import random
import time
from math import floor
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from aimaraffa.engine import (
    Card, Deck, Suit,
    KEY_CARD, RANK_TO_POINTS,
    determine_turn_winner,
    get_valid_cards, get_valid_declarations,
)
from aimaraffa.agents.heuristic_agent import HeuristicAgent
from aimaraffa.agents.base import BaseAgent

from .simulator import _GameState, _TEAM, _SEATS
from .rl_agent import RLAgent
from .rl_agent_onnx import RLAgentOnnx
from .tournament import wilson_ci

logger = logging.getLogger(__name__)


# ── Agent factory ──────────────────────────────────────────────────────────────

def _make_agent(spec: object) -> Optional[BaseAgent]:
    if spec is None:
        return None
    if spec == "heuristic":
        return HeuristicAgent()
    if isinstance(spec, Path):
        if spec.suffix == ".onnx":
            return RLAgentOnnx(spec, device="cpu")
        return RLAgent(spec, device="cpu")
    raise TypeError(f"Unknown agent spec: {spec!r}")


# ── Random-play helper ─────────────────────────────────────────────────────────

def _random_decision(
    hand: List[Card],
    table: List[Tuple[int, Card]],
    rng:  random.Random,
    is_lead: bool,
) -> Tuple[Card, Optional[str]]:
    lead_suit = table[0][1].suit if table else None
    valid     = get_valid_cards(hand, lead_suit)
    card      = rng.choice(valid)
    decl = (
        rng.choice(get_valid_declarations([c for c in hand if c != card], card.suit))
        if is_lead else None
    )
    return card, decl


# ── Single-round simulation ────────────────────────────────────────────────────

def _run_round(
    agent_a:               Optional[BaseAgent],
    agent_b:               Optional[BaseAgent],
    briscola_selector_seat: int,
    swap_sides:            bool,
    rng:                   random.Random,
) -> Tuple[int, int]:
    """Play one complete round.

    Args:
        briscola_selector_seat: which seat selects briscola and leads trick 1.
            Cycled externally to guarantee every seat leads equally often.
        swap_sides: when True, A controls team2 and B controls team1.

    Returns:
        (floor(team1_round_pts), floor(team2_round_pts))
    """
    def _agent_for_seat(seat: int) -> Optional[BaseAgent]:
        team = _TEAM[seat]
        if swap_sides:
            return agent_b if team == 1 else agent_a
        return agent_a if team == 1 else agent_b

    state = _GameState()
    state.total_scores       = {1: 0, 2: 0}   # unused for metric, kept for API compat
    state.round_scores       = {1: 0.0, 2: 0.0}
    state.round_history      = {}
    state.table_tuples       = []
    state.maraffa_forced     = False

    # Deal
    deck = Deck()
    deck.shuffle(rng)
    for s in _SEATS:
        state.hands[s] = deck.cards[s * 10:(s + 1) * 10]

    # Force the desired briscola-selector seat instead of finding KEY_CARD.
    # Rounds are independent so any seat can lead; this guarantees balance.
    state.briscola_selector = briscola_selector_seat
    state.first_of_turn     = briscola_selector_seat

    active_agents = list({ag for ag in [agent_a, agent_b] if ag is not None})
    for ag in active_agents:
        ag.reset_round()

    # ── Briscola selection ─────────────────────────────────────────────────────
    sel_seat = state.briscola_selector
    ag       = _agent_for_seat(sel_seat)
    if ag is None:
        state.briscola = rng.choice(list(Suit))
    else:
        ctx = {
            "seat":                   sel_seat,
            "round_num":              1,
            "turn_num":               0,
            "briscola_selector_seat": sel_seat,
            "briscola":               None,
            "table_cards":            [],
            "round_scores":           {1: 0.0, 2: 0.0},
            "total_scores":           {1: 0, 2: 0},
            "hand":                   state.hands[sel_seat],
        }
        state.briscola = ag.select_briscola(ctx)

    hand_sel = state.hands[sel_seat]
    mar      = [c for c in hand_sel if c.suit == state.briscola and c.rank in (1, 2, 3)]
    if len(mar) == 3:
        state.maraffa_forced = True

    # ── 10 tricks ─────────────────────────────────────────────────────────────
    for turn_idx in range(10):
        turn_num = turn_idx + 1
        state.table_tuples   = []
        state.maraffa_forced = False

        for position in range(4):
            seat    = (state.first_of_turn + position) % 4
            hand    = state.hands[seat]
            lead_s  = state.table_tuples[0][1].suit if state.table_tuples else None
            is_lead = (position == 0)
            ag      = _agent_for_seat(seat)

            if ag is None:
                card, decl = _random_decision(hand, state.table_tuples, rng, is_lead)
            else:
                if state.maraffa_forced and seat == state.briscola_selector and lead_s is None:
                    forced = Card(state.briscola, 1)
                    fdecls = get_valid_declarations(
                        [c for c in hand if c != forced], forced.suit)
                    card = forced
                    decl = rng.choice(fdecls) if is_lead else None
                else:
                    ctx = {
                        "seat":                   seat,
                        "round_num":              1,
                        "turn_num":               turn_num,
                        "briscola_selector_seat": state.briscola_selector,
                        "briscola":               state.briscola,
                        "table_cards":            list(state.table_tuples),
                        "round_scores":           {1: round(state.round_scores[1], 2),
                                                   2: round(state.round_scores[2], 2)},
                        "total_scores":           {1: 0, 2: 0},
                        "hand":                   hand,
                    }
                    card, decl = ag.select_card(ctx, state.briscola)
                    if not is_lead:
                        decl = None

            declaration = decl if is_lead else None
            state.hands[seat].remove(card)
            key = f"{card.suit.value}_{card.rank}"
            state.round_history[key] = (seat, turn_num, declaration or "")
            state.table_tuples.append((seat, card))

            for ag2 in active_agents:
                ag2.record_card(card, seat, turn_num, declaration)

        winner_seat = determine_turn_winner(state.table_tuples, state.briscola)
        pts         = sum(RANK_TO_POINTS[c.rank] for _, c in state.table_tuples)
        state.round_scores[_TEAM[winner_seat]] += pts
        state.first_of_turn = winner_seat

    # Last-trick bonus
    state.round_scores[_TEAM[state.first_of_turn]] += 1.0

    return int(floor(state.round_scores[1])), int(floor(state.round_scores[2]))


# ── Tournament driver ──────────────────────────────────────────────────────────

def rl_tournament(
    model_a: object,
    model_b: object,
    games:   int,
    seed:    Optional[int] = None,
) -> Dict:
    """Round-based head-to-head between two agent specs.

    Args:
        games: number of rounds to play (each round = one deal).
               Use a multiple of 8 for perfect seat × side balance.

    Returns dict compatible with format_report and promotion logic.
    """
    n_rounds = games
    half     = n_rounds // 2

    logger.info(
        "RL Tournament: %d rounds (%d A=team1, %d A=team2), seed=%s",
        n_rounds, half, n_rounds - half, seed,
    )

    t0      = time.perf_counter()
    agent_a = _make_agent(model_a)
    agent_b = _make_agent(model_b)

    # Both halves use the same seed → identical deals with sides swapped.
    # Paired design cancels card-luck; only skill gap remains in the aggregate.
    rng1 = random.Random(seed)
    rng2 = random.Random(seed)

    totals_1: List[Tuple[int, int]] = []   # A=team1
    for i in range(half):
        sel_seat = i % 4
        totals_1.append(_run_round(agent_a, agent_b, sel_seat, swap_sides=False, rng=rng1))

    totals_2: List[Tuple[int, int]] = []   # A=team2
    for i in range(n_rounds - half):
        sel_seat = i % 4
        totals_2.append(_run_round(agent_a, agent_b, sel_seat, swap_sides=True, rng=rng2))

    dt = time.perf_counter() - t0

    # A wins round when it scores more floor-points than B.
    a_wins_1 = sum(1 for t1, t2 in totals_1 if t1 > t2)   # A as team1
    b_wins_1 = sum(1 for t1, t2 in totals_1 if t2 > t1)
    tie_1    = half - a_wins_1 - b_wins_1
    margin_1 = float(np.mean([t1 - t2 for t1, t2 in totals_1])) if totals_1 else 0.0

    a_wins_2 = sum(1 for t1, t2 in totals_2 if t2 > t1)   # A as team2
    b_wins_2 = sum(1 for t1, t2 in totals_2 if t1 > t2)
    tie_2    = (n_rounds - half) - a_wins_2 - b_wins_2
    margin_2 = float(np.mean([t2 - t1 for t1, t2 in totals_2])) if totals_2 else 0.0

    a_wins    = a_wins_1 + a_wins_2
    b_wins    = b_wins_1 + b_wins_2
    ties      = tie_1 + tie_2
    decisive  = a_wins + b_wins
    win_rate_a = a_wins / decisive if decisive else 0.0
    lo, hi     = wilson_ci(a_wins, decisive)
    avg_margin = (margin_1 * half + margin_2 * (n_rounds - half)) / max(1, n_rounds)

    return {
        "games":             n_rounds,
        "games_a_team1":     half,
        "games_a_team2":     n_rounds - half,
        "a_wins":            a_wins,
        "b_wins":            b_wins,
        "ties":              ties,
        "win_rate_a":        win_rate_a,
        "ci95_lo":           lo,
        "ci95_hi":           hi,
        "avg_margin_a":      avg_margin,
        "duration_sec":      dt,
        "games_per_sec":     n_rounds / dt if dt > 0 else float("inf"),
        "a_wins_when_team1": a_wins_1,
        "a_wins_when_team2": a_wins_2,
    }
