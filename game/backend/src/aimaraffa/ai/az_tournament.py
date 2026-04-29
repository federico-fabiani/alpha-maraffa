"""Round-based tournament between AZ-style agents (or vs heuristic / random).

Reuses the rl_tournament round-runner via a thin agent factory that
recognises AZ checkpoints alongside RL ones.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from aimaraffa.agents.base import BaseAgent
from aimaraffa.agents.heuristic_agent import HeuristicAgent

from . import config_az as cfg
from .az_agent      import AZAgent
from .rl_tournament import rl_tournament as _rl_tournament_run

logger = logging.getLogger(__name__)


def _make_agent(spec: object) -> Optional[BaseAgent]:
    """Spec resolver for AZ tournaments.

    ``spec`` can be:
        None                            → random
        "heuristic"                     → HeuristicAgent
        Path / str ending in .pt/.onnx  → AZAgent (full ISMCTS)
        ("az_greedy", Path)             → AZAgent with use_search=False
        ("az", Path, n_sims, n_dets)    → AZAgent with custom MCTS knobs
    """
    if spec is None:
        return None
    if spec == "heuristic":
        return HeuristicAgent()
    if isinstance(spec, (str, Path)) and str(spec).endswith((".pt", ".onnx")):
        return AZAgent(Path(spec))
    if isinstance(spec, tuple) and spec and spec[0] == "az_greedy":
        return AZAgent(Path(spec[1]), use_search=False)
    if isinstance(spec, tuple) and spec and spec[0] == "az":
        path, n_sims, n_dets = spec[1], spec[2], spec[3]
        return AZAgent(Path(path), n_simulations=n_sims, n_determinizations=n_dets)
    raise TypeError(f"Unknown agent spec: {spec!r}")


def az_tournament(
    model_a: object,
    model_b: object,
    games:   int = cfg.TOURNEY_GAMES,
    seed:    int = cfg.TOURNEY_SEED,
) -> dict:
    """Run a paired round-based tournament between two agent specs.

    The implementation reuses ``rl_tournament._run_round`` indirectly:
    we monkey-patch its agent factory for the duration of the call.

    For now we re-implement the round runner here to avoid coupling.
    """
    # Build agents.
    a = _make_agent(model_a)
    b = _make_agent(model_b)
    return _run_paired(a, b, games, seed)


# ── Re-implementation of paired round runner ─────────────────────────────────

import math
import random
import time
from typing import List, Tuple

import numpy as np

from aimaraffa.engine import (
    Card, Suit, Deck,
    RANK_TO_POINTS,
    determine_turn_winner,
    get_valid_cards, get_valid_declarations,
)


def _run_round(
    agent_a:                Optional[BaseAgent],
    agent_b:                Optional[BaseAgent],
    briscola_selector_seat: int,
    swap_sides:             bool,
    rng:                    random.Random,
) -> Tuple[int, int]:
    seats_team = {0: 1, 1: 2, 2: 1, 3: 2}

    def agent_for(seat: int) -> Optional[BaseAgent]:
        team = seats_team[seat]
        if swap_sides:
            return agent_b if team == 1 else agent_a
        return agent_a if team == 1 else agent_b

    deck = Deck()
    deck.shuffle(rng)
    hands = {s: deck.cards[s * 10:(s + 1) * 10] for s in range(4)}
    round_scores = {1: 0.0, 2: 0.0}

    for ag in {a for a in (agent_a, agent_b) if a is not None}:
        ag.reset_round()

    # Briscola selection
    sel = briscola_selector_seat
    ag = agent_for(sel)
    if ag is None:
        briscola = rng.choice(list(Suit))
    else:
        ctx = {
            "seat": sel, "round_num": 1, "turn_num": 0,
            "briscola_selector_seat": sel, "briscola": None,
            "table_cards": [], "round_scores": {1: 0.0, 2: 0.0},
            "total_scores": {1: 0, 2: 0}, "hand": hands[sel],
        }
        briscola = ag.select_briscola(ctx)

    # Maraffa cricca
    sel_hand = hands[sel]
    mar = [c for c in sel_hand if c.suit == briscola and c.rank in (1, 2, 3)]
    maraffa_forced = (len(mar) == 3)

    first_of_turn = sel
    table_cards: List[Tuple[int, Card]] = []

    for trick in range(10):
        table_cards = []
        for pos in range(4):
            seat = (first_of_turn + pos) % 4
            ag   = agent_for(seat)
            lead = table_cards[0][1].suit if table_cards else None
            is_lead = (pos == 0)

            if maraffa_forced and seat == sel and lead is None:
                forced = Card(briscola, 1)
                fdecls = get_valid_declarations([c for c in hands[seat] if c != forced], briscola)
                card = forced
                decl = rng.choice(fdecls) if is_lead else None
                maraffa_forced = False
            elif ag is None:
                valid = get_valid_cards(hands[seat], lead)
                card = rng.choice(valid)
                decl = (rng.choice(get_valid_declarations([c for c in hands[seat] if c != card], card.suit))
                        if is_lead else None)
            else:
                ctx = {
                    "seat": seat, "round_num": 1, "turn_num": trick + 1,
                    "briscola_selector_seat": sel, "briscola": briscola,
                    "table_cards": list(table_cards),
                    "round_scores": {1: round(round_scores[1], 2), 2: round(round_scores[2], 2)},
                    "total_scores": {1: 0, 2: 0}, "hand": hands[seat],
                }
                card, decl = ag.select_card(ctx, briscola)
                if not is_lead:
                    decl = None

            hands[seat] = [c for c in hands[seat] if c != card]
            table_cards.append((seat, card))

            for ag2 in {a for a in (agent_a, agent_b) if a is not None}:
                ag2.record_card(card, seat, trick + 1, decl if is_lead else None)

        winner_seat = determine_turn_winner(table_cards, briscola)
        pts = sum(RANK_TO_POINTS[c.rank] for _, c in table_cards)
        round_scores[seats_team[winner_seat]] += pts
        first_of_turn = winner_seat

    round_scores[seats_team[first_of_turn]] += 1.0

    from math import floor
    return int(floor(round_scores[1])), int(floor(round_scores[2]))


def _wilson_ci(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n) / denom
    return max(0.0, center - half), min(1.0, center + half)


def _run_paired(agent_a, agent_b, n_rounds: int, seed: int) -> dict:
    half = n_rounds // 2
    t0 = time.perf_counter()

    rng1 = random.Random(seed)
    rng2 = random.Random(seed)

    res1: List[Tuple[int, int]] = []
    for i in range(half):
        res1.append(_run_round(agent_a, agent_b, i % 4, False, rng1))
    res2: List[Tuple[int, int]] = []
    for i in range(n_rounds - half):
        res2.append(_run_round(agent_a, agent_b, i % 4, True, rng2))

    a_wins = (sum(1 for x, y in res1 if x > y)
              + sum(1 for x, y in res2 if y > x))
    b_wins = (sum(1 for x, y in res1 if y > x)
              + sum(1 for x, y in res2 if x > y))
    decisive = a_wins + b_wins
    win_rate_a = a_wins / decisive if decisive else 0.0
    lo, hi = _wilson_ci(a_wins, decisive)
    margin1 = float(np.mean([x - y for x, y in res1])) if res1 else 0.0
    margin2 = float(np.mean([y - x for x, y in res2])) if res2 else 0.0
    avg_margin = (margin1 * half + margin2 * (n_rounds - half)) / max(1, n_rounds)

    return {
        "games":         n_rounds,
        "a_wins":        a_wins,
        "b_wins":        b_wins,
        "ties":          n_rounds - a_wins - b_wins,
        "win_rate_a":    win_rate_a,
        "ci95_lo":       lo,
        "ci95_hi":       hi,
        "avg_margin_a":  avg_margin,
        "duration_sec":  time.perf_counter() - t0,
    }
