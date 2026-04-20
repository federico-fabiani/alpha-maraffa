"""Head-to-head tournament between two Marafone models (or vs random).

Side-swap halves the games so any first-player / position bias cancels out.
The Wilson 95% CI is what the pipeline uses to gate promotion.
"""

from __future__ import annotations

import logging
import math
import time
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import xgboost as xgb

from aimaraffa.engine import Card, Suit, get_valid_cards, get_valid_declarations
from aimaraffa.ml_agent import MLAgent, _COL_IDX, _COL_NAMES
from .simulator import Simulator, _GameState, _TEAM

logger = logging.getLogger(__name__)


def wilson_ci(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n) / denom
    return max(0.0, center - half), min(1.0, center + half)


# ── Two-agent runner ───────────────────────────────────────────────────────────

class _FastMLMatch(Simulator):
    """Simulator variant that routes inference to two boosters per game.

    Either side may be ``None`` → random agent (used for baselines and to
    bootstrap the very first version).
    """

    def __init__(self, agent_a_path: Optional[Path], agent_b_path: Optional[Path],
                 swap_sides: bool = False):
        super().__init__(agent_a_path, epsilon=0.0)
        self.swap_sides = swap_sides
        self._random = {"A": agent_a_path is None, "B": agent_b_path is None}
        self._agent_b: Optional[MLAgent] = (
            MLAgent(agent_b_path) if agent_b_path is not None else None
        )
        self._feature_agent: Optional[MLAgent] = self.agent or self._agent_b
        self._kits: Dict[str, tuple] = {}
        if not self._random["A"]:
            self._kits["A"] = self._build_kit(self.agent.model.get_booster())
        if not self._random["B"]:
            self._kits["B"] = self._build_kit(self._agent_b.model.get_booster())
        a_name = agent_a_path.name if agent_a_path else "random"
        b_name = agent_b_path.name if agent_b_path else "random"
        logger.info("FastMLMatch: A=%s  B=%s  swap_sides=%s", a_name, b_name, swap_sides)

    @staticmethod
    def _build_kit(booster: "xgb.Booster"):
        names = booster.feature_names
        types = booster.feature_types
        sel = None
        if names != _COL_NAMES:
            sel = np.array([_COL_IDX[n] for n in names], dtype=np.int32)
        return booster, sel, names, types

    def _agent_key_for_seat(self, seat: int) -> str:
        team = _TEAM[seat]
        if self.swap_sides:
            return "B" if team == 1 else "A"
        return "A" if team == 1 else "B"

    def _predict_with_kit(self, key: str, arr: np.ndarray) -> np.ndarray:
        booster, sel, names, types = self._kits[key]
        if sel is not None:
            arr = arr[:, sel]
        dmat = xgb.DMatrix(arr, feature_names=names, feature_types=types)
        return booster.predict(dmat)

    # ── Override: briscola selection ─────────────────────────────────────────

    def _select_briscolas(self, states: List[_GameState], round_num: int) -> None:
        groups: Dict[str, List[_GameState]] = {"A": [], "B": []}
        for state in states:
            if state.done:
                continue
            groups[self._agent_key_for_seat(state.briscola_selector)].append(state)

        suits_list = list(Suit)
        for key, group in groups.items():
            if not group:
                continue

            if self._random[key]:
                for state in group:
                    state.briscola = self._rng.choice(suits_list)
                continue

            rows: List[np.ndarray] = []
            slices: List[List[Tuple[int, int]]] = []
            for state in group:
                seat = state.briscola_selector
                hand = state.hands[seat]
                ctx = self._build_ctx(state, seat, round_num, turn_num=0)
                per_suit: List[Tuple[int, int]] = []
                for suit in Suit:
                    lo = len(rows)
                    for card in hand:
                        after = [c for c in hand if c != card]
                        for decl in get_valid_declarations(after, card.suit):
                            rows.append(
                                self._feature_agent._build_np_row(
                                    card, decl, suit, ctx, force_lead=True
                                )
                            )
                    per_suit.append((lo, len(rows)))
                slices.append(per_suit)

            if not rows:
                continue
            arr = np.stack(rows)
            preds = self._predict_with_kit(key, arr)
            for state, per_suit in zip(group, slices):
                suit_values = np.array(
                    [preds[lo:hi].max() if hi > lo else -np.inf
                     for (lo, hi) in per_suit],
                    dtype=np.float32,
                )
                state.briscola = suits_list[int(suit_values.argmax())]

    # ── Override: card selection per position ────────────────────────────────

    def _select_cards_per_position(
        self, states: List[_GameState], round_num: int, turn_num: int, position: int
    ) -> Dict[int, Tuple[Card, Optional[str]]]:
        decisions: Dict[int, Tuple[Card, Optional[str]]] = {}
        for key in ("A", "B"):
            sub_states = self._states_filtered_for_key(states, position, key)
            if not sub_states:
                continue
            decisions.update(
                self._decide_for_subset(sub_states, round_num, turn_num, position, key)
            )
        return decisions

    def _states_filtered_for_key(
        self, states: List[_GameState], position: int, key: str
    ) -> List[Tuple[int, _GameState]]:
        out: List[Tuple[int, _GameState]] = []
        for gi, state in enumerate(states):
            if state.done:
                continue
            seat = self._seat_at_position(state, position)
            if self._agent_key_for_seat(seat) == key:
                out.append((gi, state))
        return out

    def _decide_for_subset(
        self,
        indexed_states: List[Tuple[int, _GameState]],
        round_num: int, turn_num: int, position: int,
        key: str,
    ) -> Dict[int, Tuple[Card, Optional[str]]]:
        if self._random[key]:
            return self._random_subset_decisions(indexed_states, position)

        all_rows: List[np.ndarray] = []
        slices: List[Tuple[int, int]] = []
        candidates: List[List[Tuple[Card, Optional[str]]]] = []
        game_indices: List[int] = []

        is_lead_pos = (position == 0)
        cum_rows = 0

        for gi, state in indexed_states:
            seat = self._seat_at_position(state, position)
            hand = state.hands[seat]
            lead_suit = state.table_tuples[0][1].suit if state.table_tuples else None

            if state.maraffa_forced and seat == state.briscola_selector and lead_suit is None:
                forced = Card(state.briscola, 1)
                decls = get_valid_declarations([c for c in hand if c != forced], forced.suit)
                cands = [(forced, d) for d in decls]
            else:
                valid = get_valid_cards(hand, lead_suit)
                if is_lead_pos:
                    cands = []
                    for card in valid:
                        after = [c for c in hand if c != card]
                        for decl in get_valid_declarations(after, card.suit):
                            cands.append((card, decl))
                else:
                    cands = [(card, None) for card in valid]

            briscola_str = state.briscola.value
            lo = cum_rows

            if is_lead_pos:
                by_suit: Dict[str, List[Tuple[Card, Optional[str]]]] = {}
                for cand in cands:
                    sv = cand[0].suit.value
                    by_suit.setdefault(sv, []).append(cand)
                ordered: List[Tuple[Card, Optional[str]]] = []
                for sv, group in by_suit.items():
                    base = self._build_base_row(
                        state, seat, round_num, turn_num,
                        lead_suit_value=sv, is_lead_pos=True,
                    )
                    rows = self._expand_candidates(base, group, briscola_str, sv)
                    all_rows.append(rows)
                    ordered.extend(group)
                candidates.append(ordered)
                cum_rows += len(cands)
            else:
                lead_value = lead_suit.value  # type: ignore[union-attr]
                base = self._build_base_row(
                    state, seat, round_num, turn_num,
                    lead_suit_value=lead_value, is_lead_pos=False,
                )
                rows = self._expand_candidates(base, cands, briscola_str, lead_value)
                all_rows.append(rows)
                candidates.append(cands)
                cum_rows += len(cands)

            slices.append((lo, cum_rows))
            game_indices.append(gi)

        if not all_rows:
            return {}

        arr = np.concatenate(all_rows, axis=0) if len(all_rows) > 1 else all_rows[0]
        preds = self._predict_with_kit(key, arr)

        decisions: Dict[int, Tuple[Card, Optional[str]]] = {}
        for gi, cands, (lo, hi) in zip(game_indices, candidates, slices):
            pick = int(preds[lo:hi].argmax())
            decisions[gi] = cands[pick]
        return decisions

    def _random_subset_decisions(
        self,
        indexed_states: List[Tuple[int, _GameState]],
        position: int,
    ) -> Dict[int, Tuple[Card, Optional[str]]]:
        is_lead_pos = (position == 0)
        decisions: Dict[int, Tuple[Card, Optional[str]]] = {}
        for gi, state in indexed_states:
            seat = self._seat_at_position(state, position)
            hand = state.hands[seat]
            lead_suit = state.table_tuples[0][1].suit if state.table_tuples else None

            if state.maraffa_forced and seat == state.briscola_selector and lead_suit is None:
                forced = Card(state.briscola, 1)
                decls = get_valid_declarations([c for c in hand if c != forced], forced.suit)
                decisions[gi] = (forced, self._rng.choice(decls))
                continue

            valid = get_valid_cards(hand, lead_suit)
            card = self._rng.choice(valid)
            if is_lead_pos:
                decls = get_valid_declarations([c for c in hand if c != card], card.suit)
                decisions[gi] = (card, self._rng.choice(decls))
            else:
                decisions[gi] = (card, None)
        return decisions


# ── Driver ─────────────────────────────────────────────────────────────────────

def tournament(
    model_a: Optional[Path],
    model_b: Optional[Path],
    games: int,
    seed: Optional[int] = None,
) -> Dict:
    """Play ``games`` head-to-head, half with sides swapped.

    Returns a dict with win/tie counts, A's win-rate, Wilson 95% CI, and
    average margin (A − B in round points).
    """
    games_a = games // 2
    games_b = games - games_a

    logger.info("Tournament: %d games (%d A=team1, %d A=team2)",
                games, games_a, games_b)

    match = _FastMLMatch(model_a, model_b, swap_sides=False)
    t0 = time.perf_counter()
    totals_1 = match.run(n_games=games_a, seed=seed, output_path=None)
    match_swapped = _FastMLMatch(model_a, model_b, swap_sides=True)
    totals_2 = match_swapped.run(
        n_games=games_b,
        seed=None if seed is None else seed + 1,
        output_path=None,
    )
    dt = time.perf_counter() - t0

    a_wins_1 = int((totals_1[:, 0] > totals_1[:, 1]).sum())
    b_wins_1 = int((totals_1[:, 0] < totals_1[:, 1]).sum())
    tie_1    = int((totals_1[:, 0] == totals_1[:, 1]).sum())
    margin_a_1 = float((totals_1[:, 0] - totals_1[:, 1]).mean()) if games_a else 0.0

    a_wins_2 = int((totals_2[:, 1] > totals_2[:, 0]).sum())
    b_wins_2 = int((totals_2[:, 1] < totals_2[:, 0]).sum())
    tie_2    = int((totals_2[:, 0] == totals_2[:, 1]).sum())
    margin_a_2 = float((totals_2[:, 1] - totals_2[:, 0]).mean()) if games_b else 0.0

    a_wins = a_wins_1 + a_wins_2
    b_wins = b_wins_1 + b_wins_2
    ties   = tie_1 + tie_2
    decisive = a_wins + b_wins
    win_rate_a = a_wins / decisive if decisive else 0.0
    lo, hi = wilson_ci(a_wins, decisive)
    avg_margin = (margin_a_1 * games_a + margin_a_2 * games_b) / max(1, games_a + games_b)

    return {
        "games": games,
        "games_a_team1": games_a,
        "games_a_team2": games_b,
        "a_wins": a_wins,
        "b_wins": b_wins,
        "ties": ties,
        "win_rate_a": win_rate_a,
        "ci95_lo": lo,
        "ci95_hi": hi,
        "avg_margin_a": avg_margin,
        "duration_sec": dt,
        "games_per_sec": games / dt if dt > 0 else float("inf"),
        "a_wins_when_team1": a_wins_1,
        "a_wins_when_team2": a_wins_2,
    }


def format_report(label_a: str, label_b: str, res: Dict) -> str:
    """Render a tournament result as the same plain-text block we used to print."""
    wr = res["win_rate_a"] * 100
    lo = res["ci95_lo"] * 100
    hi = res["ci95_hi"] * 100

    if res["ci95_lo"] > 0.5:
        verdict = "A is significantly stronger (95% CI above 50%)."
    elif res["ci95_hi"] < 0.5:
        verdict = "B is significantly stronger (A CI below 50%)."
    else:
        verdict = "Inconclusive — CI straddles 50%. Increase games."

    buf = StringIO()
    print("=" * 62, file=buf)
    print(f"  Tournament:  A = {label_a}", file=buf)
    print(f"               B = {label_b}", file=buf)
    print("=" * 62, file=buf)
    print(f"  Games total        : {res['games']}", file=buf)
    print(f"  A as team1 / team2 : {res['games_a_team1']} / {res['games_a_team2']}", file=buf)
    print(f"  A wins             : {res['a_wins']}  "
          f"(team1: {res['a_wins_when_team1']}, team2: {res['a_wins_when_team2']})", file=buf)
    print(f"  B wins             : {res['b_wins']}", file=buf)
    print(f"  Ties               : {res['ties']}", file=buf)
    print("-" * 62, file=buf)
    print(f"  A win-rate         : {wr:.2f}%  [95% CI {lo:.2f}% – {hi:.2f}%]", file=buf)
    print(f"  Avg margin (A - B) : {res['avg_margin_a']:+.2f} points", file=buf)
    print(f"  Time               : {res['duration_sec']:.1f}s  "
          f"({res['games_per_sec']:.1f} games/s)", file=buf)
    print(f"  Verdict            : {verdict}", file=buf)
    print("=" * 62, file=buf)
    return buf.getvalue()
