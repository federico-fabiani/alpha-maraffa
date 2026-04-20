"""Marafone game simulator + dataset writer — single block.

One entry point: ``simulate(n_games, model_path=None, ...)``.

- ``model_path=None`` → random self-play. Uniformly picks among legal moves.
  No XGBoost inference, so it's the fastest path (used to bootstrap v1).
- ``model_path=<.joblib>`` → ML self-play with cross-game batched inference:
  every decision point collects candidate feature rows from **all active games**
  and submits one big ``xgb.predict`` call. ε-greedy exploration optional.

When ``output_path`` is set, per-play feature rows are streamed to Parquet via
:class:`GameTracker` (full schema needed for downstream training).

This file deliberately bundles schema, tracker, game-state, simulator, and the
``simulate()`` wrapper so the whole simulation surface lives in one place.
"""

from __future__ import annotations

import logging
import random
import time
from math import floor
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import xgboost as xgb

from aimaraffa.engine import (
    Card, Deck, Suit,
    GAME_WIN_THRESHOLD, KEY_CARD, RANK_TO_POINTS,
    determine_turn_winner,
    get_valid_cards, get_valid_declarations,
)
from aimaraffa.ml_agent import (
    MLAgent,
    _COL_IDX, _COL_NAMES, _COL_TYPES, _ROW_TEMPLATE,
    _SUIT_ENC, _DECL_ENC, _STATUS_ENC, _TEAM_OF,
)

logger = logging.getLogger(__name__)


# ── Constants ──────────────────────────────────────────────────────────────────

_SUITS = ["bastoni", "denara", "spade", "coppe"]
_RANKS = list(range(1, 11))
_SEATS = (0, 1, 2, 3)
_TEAM  = {0: 1, 1: 2, 2: 1, 3: 2}


# ── Dataset row schema ─────────────────────────────────────────────────────────
# Column order and dtypes are part of the contract with train.py / analyze.py.
# Keep in sync with aimaraffa.ml_agent._COL_NAMES (inference-time encoding).

_HAND_TEMPLATE: Dict[str, int] = {}
for _r in _RANKS:
    _HAND_TEMPLATE[f"hand_briscola_{_r}"] = 0
    _HAND_TEMPLATE[f"hand_lead_{_r}"]     = 0
    _HAND_TEMPLATE[f"hand_other_{_r}_count"] = 0

_HISTORY_TEMPLATE: dict = {}
for _s in _SUITS:
    for _r in _RANKS:
        _HISTORY_TEMPLATE[f"hist_{_s}_{_r}_is_my_team"] = -1
        _HISTORY_TEMPLATE[f"hist_{_s}_{_r}_turn"] = -1
        _HISTORY_TEMPLATE[f"hist_{_s}_{_r}_decl"] = ""

_FIELDNAMES: List[str] = (
    [
        "game_id", "round_num", "turn_num", "play_order",
        "seat", "team", "briscola_suit", "briscola_selector_is_my_team",
        "card_rank", "card_is_briscola", "card_is_lead",
        "is_lead", "lead_suit", "declaration",
        "table_0_rank", "table_0_is_briscola", "table_0_is_lead", "table_0_is_my_team",
        "table_1_rank", "table_1_is_briscola", "table_1_is_lead", "table_1_is_my_team",
        "table_2_rank", "table_2_is_briscola", "table_2_is_lead", "table_2_is_my_team",
        "round_score_t1", "round_score_t2",
        "total_score_t1", "total_score_t2",
    ]
    + [f"hand_briscola_{r}"      for r in _RANKS]
    + [f"hand_lead_{r}"          for r in _RANKS]
    + [f"hand_other_{r}_count"   for r in _RANKS]
    + [f"hist_{s}_{r}_is_my_team" for s in _SUITS for r in _RANKS]
    + [f"hist_{s}_{r}_turn"       for s in _SUITS for r in _RANKS]
    + [f"hist_{s}_{r}_decl"       for s in _SUITS for r in _RANKS]
    + ["partner_suit_status", "opp_left_suit_status", "opp_right_suit_status"]
    + [
        "turn_winner_seat", "turn_winner_team", "turn_pts",
        "round_pts_t1", "round_pts_t2",
        "round_pts_player_team", "round_pts_diff", "future_pts_diff",
    ]
)

# Tight dtypes — keeps a 10k-game Parquet around 1 GB instead of 11 GB.
_DTYPE_MAP: Dict[str, str] = {
    "game_id":                       "category",
    "round_num":                     "int8",
    "turn_num":                      "int8",
    "play_order":                    "int8",
    "seat":                          "int8",
    "team":                          "int8",
    "briscola_suit":                 "category",
    "briscola_selector_is_my_team":  "int8",
    "card_rank":                     "int8",
    "card_is_briscola":              "int8",
    "card_is_lead":                  "int8",
    "is_lead":                       "int8",
    "lead_suit":                     "category",
    "declaration":                   "category",
    "table_0_rank":                  "int8",
    "table_0_is_briscola":           "int8",
    "table_0_is_lead":               "int8",
    "table_0_is_my_team":            "int8",
    "table_1_rank":                  "int8",
    "table_1_is_briscola":           "int8",
    "table_1_is_lead":               "int8",
    "table_1_is_my_team":            "int8",
    "table_2_rank":                  "int8",
    "table_2_is_briscola":           "int8",
    "table_2_is_lead":               "int8",
    "table_2_is_my_team":            "int8",
    "round_score_t1":                "float32",
    "round_score_t2":                "float32",
    "total_score_t1":                "int16",
    "total_score_t2":                "int16",
    **{f"hand_briscola_{r}":         "int8" for r in _RANKS},
    **{f"hand_lead_{r}":             "int8" for r in _RANKS},
    **{f"hand_other_{r}_count":      "int8" for r in _RANKS},
    **{f"hist_{s}_{r}_is_my_team":   "int8" for s in _SUITS for r in _RANKS},
    **{f"hist_{s}_{r}_turn":         "int8" for s in _SUITS for r in _RANKS},
    **{f"hist_{s}_{r}_decl":     "category" for s in _SUITS for r in _RANKS},
    "partner_suit_status":           "category",
    "opp_left_suit_status":          "category",
    "opp_right_suit_status":         "category",
    "turn_winner_seat":              "int8",
    "turn_winner_team":              "int8",
    "turn_pts":                      "float32",
    "round_pts_t1":                  "int8",
    "round_pts_t2":                  "int8",
    "round_pts_player_team":         "int8",
    "round_pts_diff":                "int16",
    "future_pts_diff":               "int16",
}


# ── Schema helpers (used by GameTracker) ───────────────────────────────────────

def _suit_role(suit: str, briscola: str, lead: str) -> Tuple[int, int]:
    """``(is_briscola, is_lead)`` for a suit — mutually exclusive flags."""
    is_briscola = int(suit == briscola)
    is_lead     = int(suit == lead and suit != briscola)
    return is_briscola, is_lead


def _hand_features(hand: List[dict], briscola: str, lead: str) -> Dict[str, int]:
    """Role-relative hand encoding: 30 cols vs 40 absolute."""
    feat = _HAND_TEMPLATE.copy()
    for c in hand:
        r = c["rank"]
        ib, il = _suit_role(c["suit"], briscola, lead)
        if ib:
            feat[f"hand_briscola_{r}"] = 1
        elif il:
            feat[f"hand_lead_{r}"] = 1
        else:
            feat[f"hand_other_{r}_count"] += 1
    return feat


def _history_features(played: Dict[str, tuple], my_team: int) -> dict:
    feat = _HISTORY_TEMPLATE.copy()
    for key, (seat, turn, decl) in played.items():
        feat[f"hist_{key}_is_my_team"] = int(_TEAM[seat] == my_team)
        feat[f"hist_{key}_turn"] = turn
        feat[f"hist_{key}_decl"] = decl
    return feat


def _suit_status_features(seat: int, lead_suit: str,
                          played: Dict[str, tuple]) -> dict:
    """Decode partner / opponent suit status from declarations in round history.

    ``volo`` is permanent within a round and overrides earlier declarations.
    """
    partner_seat   = (seat + 2) % 4
    opp_left_seat  = (seat + 1) % 4
    opp_right_seat = (seat + 3) % 4

    def _status(target_seat: int) -> str:
        decls = [
            (turn, decl)
            for key, (s, turn, decl) in played.items()
            if s == target_seat and key.rsplit("_", 1)[0] == lead_suit and decl
        ]
        if not decls:
            return "unknown"
        if any(d == "volo" for _, d in decls):
            return "void"
        _, latest = max(decls, key=lambda x: x[0])
        return "has" if latest == "striscio" else "busso"

    return {
        "partner_suit_status":   _status(partner_seat),
        "opp_left_suit_status":  _status(opp_left_seat),
        "opp_right_suit_status": _status(opp_right_seat),
    }


def _rows_to_table(rows: list) -> pa.Table:
    """Convert a list of row dicts to a typed PyArrow Table."""
    df = pd.DataFrame(rows, columns=_FIELDNAMES)
    for col, dtype in _DTYPE_MAP.items():
        if col in df.columns:
            df[col] = df[col].astype(dtype)
    return pa.Table.from_pandas(df, preserve_index=False)


# ── Event tracker ──────────────────────────────────────────────────────────────

class GameTracker:
    """Convert broadcast events → tabular rows. Fills turn/round outcomes retroactively."""

    def __init__(self, game_id: str):
        self.game_id = game_id
        self._round_num = 0
        self._turns_done = 0
        self._briscola: Optional[str] = None
        self._briscola_selector: Optional[int] = None
        self._total_scores: Dict[int, int] = {1: 0, 2: 0}
        self._round_scores: Dict[int, float] = {1: 0.0, 2: 0.0}
        self._round_history: Dict[str, tuple] = {}
        self._pending_turn: List[dict] = []
        self._pending_round: List[dict] = []
        self.rows: List[dict] = []

    def on_event(self, msg: dict) -> None:
        t = msg["type"]
        d = msg.get("data", {})

        if t == "briscola_set":
            self._round_num += 1
            self._turns_done = 0
            self._briscola = d["suit"]
            self._briscola_selector = d["by_seat"]
            self._round_scores = {1: 0.0, 2: 0.0}
            self._round_history = {}

        elif t == "card_played":
            table       = d["table"]
            play_order  = len(table) - 1
            lead_suit   = table[0]["card"]["suit"]
            card        = d["card"]
            prev        = table[:play_order]

            current_team = _TEAM[d["seat"]]
            cib, cil = _suit_role(card["suit"], self._briscola, lead_suit)

            def _tslot(i):
                if len(prev) <= i:
                    return {"rank": -1, "is_briscola": -1, "is_lead": -1, "is_my_team": -1}
                ib, il = _suit_role(prev[i]["card"]["suit"], self._briscola, lead_suit)
                return {"rank": prev[i]["card"]["rank"], "is_briscola": ib, "is_lead": il,
                        "is_my_team": int(_TEAM[prev[i]["seat"]] == current_team)}

            t0, t1, t2 = _tslot(0), _tslot(1), _tslot(2)

            row: dict = {
                "game_id": self.game_id,
                "round_num": self._round_num,
                "turn_num": self._turns_done + 1,
                "play_order": play_order,
                "seat": d["seat"],
                "team": current_team,
                "briscola_suit": self._briscola,
                "briscola_selector_is_my_team": int(_TEAM[self._briscola_selector] == current_team),
                "card_rank": card["rank"],
                "card_is_briscola": cib,
                "card_is_lead": cil,
                "is_lead": int(play_order == 0),
                "lead_suit": lead_suit,
                "declaration": d.get("declaration") or "",
                "table_0_rank": t0["rank"], "table_0_is_briscola": t0["is_briscola"],
                "table_0_is_lead": t0["is_lead"], "table_0_is_my_team": t0["is_my_team"],
                "table_1_rank": t1["rank"], "table_1_is_briscola": t1["is_briscola"],
                "table_1_is_lead": t1["is_lead"], "table_1_is_my_team": t1["is_my_team"],
                "table_2_rank": t2["rank"], "table_2_is_briscola": t2["is_briscola"],
                "table_2_is_lead": t2["is_lead"], "table_2_is_my_team": t2["is_my_team"],
                "round_score_t1": round(self._round_scores[1], 2),
                "round_score_t2": round(self._round_scores[2], 2),
                "total_score_t1": self._total_scores[1],
                "total_score_t2": self._total_scores[2],
                **_hand_features(d.get("hand_before", []), self._briscola, lead_suit),
                **_history_features(self._round_history, current_team),
                **_suit_status_features(d["seat"], lead_suit, self._round_history),
                "turn_winner_seat": None,
                "turn_winner_team": None,
                "turn_pts": None,
                "round_pts_t1": None,
                "round_pts_t2": None,
                "round_pts_player_team": None,
                "round_pts_diff": None,
                "future_pts_diff": None,
            }

            self._round_history[f"{card['suit']}_{card['rank']}"] = (
                d["seat"], self._turns_done + 1, d.get("declaration") or ""
            )
            self._pending_turn.append(row)

        elif t == "turn_result":
            for row in self._pending_turn:
                row["turn_winner_seat"] = d["winner_seat"]
                row["turn_winner_team"] = d["winner_team"]
                row["turn_pts"] = d["points"]
            self._round_scores = {k: v for k, v in d["round_scores"].items()}
            self._pending_round.extend(self._pending_turn)
            self._pending_turn.clear()
            self._turns_done += 1

        elif t == "round_end":
            rpts = d["round_scores"]
            for row in self._pending_round:
                team = row["team"]
                opp  = 3 - team
                final_diff = rpts[team] - rpts[opp]
                # round_score_t1/t2 snapshot points from previously-completed turns →
                # subtract to get points earned from this turn onwards (the local
                # per-play reward signal).
                pre_turn_diff = (row["round_score_t1"] - row["round_score_t2"]) if team == 1 \
                                else (row["round_score_t2"] - row["round_score_t1"])
                row["round_pts_t1"]          = rpts[1]
                row["round_pts_t2"]          = rpts[2]
                row["round_pts_player_team"] = rpts[team]
                row["round_pts_diff"]        = final_diff
                row["future_pts_diff"]       = int(final_diff - pre_turn_diff)
            self.rows.extend(self._pending_round)
            self._pending_round.clear()
            self._total_scores = {k: v for k, v in d["total_scores"].items()}


# ── Inference-row column indices (cached as locals) ────────────────────────────
# Avoids 4 dict lookups per candidate row inside the hot prediction loop.

_CI_CARD_RANK    = _COL_IDX["card_rank"]
_CI_CARD_IB      = _COL_IDX["card_is_briscola"]
_CI_CARD_IL      = _COL_IDX["card_is_lead"]
_CI_DECL         = _COL_IDX["declaration"]
_CI_ROUND        = _COL_IDX["round_num"]
_CI_TURN         = _COL_IDX["turn_num"]
_CI_ORDER        = _COL_IDX["play_order"]
_CI_TEAM         = _COL_IDX["team"]
_CI_BSUIT        = _COL_IDX["briscola_suit"]
_CI_BSEL         = _COL_IDX["briscola_selector_is_my_team"]
_CI_ISLEAD       = _COL_IDX["is_lead"]
_CI_LEADSUIT     = _COL_IDX["lead_suit"]
_CI_RS1          = _COL_IDX["round_score_t1"]
_CI_RS2          = _COL_IDX["round_score_t2"]
_CI_TS1          = _COL_IDX["total_score_t1"]
_CI_TS2          = _COL_IDX["total_score_t2"]
_CI_PSTAT        = _COL_IDX["partner_suit_status"]
_CI_LSTAT        = _COL_IDX["opp_left_suit_status"]
_CI_RSTAT        = _COL_IDX["opp_right_suit_status"]
_CI_HAND_BRISCOLA = [_COL_IDX[f"hand_briscola_{r}"]      for r in range(1, 11)]
_CI_HAND_LEAD     = [_COL_IDX[f"hand_lead_{r}"]          for r in range(1, 11)]
_CI_HAND_OTHER    = [_COL_IDX[f"hand_other_{r}_count"]   for r in range(1, 11)]
_CI_TABLE_RANK    = [_COL_IDX[f"table_{i}_rank"]         for i in range(3)]
_CI_TABLE_IB      = [_COL_IDX[f"table_{i}_is_briscola"]  for i in range(3)]
_CI_TABLE_IL      = [_COL_IDX[f"table_{i}_is_lead"]      for i in range(3)]
_CI_TABLE_MT      = [_COL_IDX[f"table_{i}_is_my_team"]   for i in range(3)]

# Per-history-card column indices, indexed by card id (0..39).
_CI_HIST_MT   = np.zeros(40, dtype=np.int32)
_CI_HIST_TURN = np.zeros(40, dtype=np.int32)
_CI_HIST_DECL = np.zeros(40, dtype=np.int32)
for _suit_idx, _suit_name in enumerate(_SUITS):
    for _rank_idx in range(10):
        _cid = _suit_idx * 10 + _rank_idx
        _CI_HIST_MT[_cid]   = _COL_IDX[f"hist_{_suit_name}_{_rank_idx + 1}_is_my_team"]
        _CI_HIST_TURN[_cid] = _COL_IDX[f"hist_{_suit_name}_{_rank_idx + 1}_turn"]
        _CI_HIST_DECL[_cid] = _COL_IDX[f"hist_{_suit_name}_{_rank_idx + 1}_decl"]


# ── Game state ─────────────────────────────────────────────────────────────────

class _GameState:
    """Mutable per-game state (one instance per simulated game)."""
    __slots__ = ("hands", "total_scores", "round_scores", "round_history",
                 "briscola", "briscola_selector", "first_of_turn",
                 "table_tuples", "table_dicts", "maraffa_forced", "done",
                 "game_id", "tracker")

    def __init__(self, game_id: str = "", tracker: Optional[GameTracker] = None) -> None:
        self.hands: Dict[int, List[Card]] = {s: [] for s in _SEATS}
        self.total_scores: Dict[int, int] = {1: 0, 2: 0}
        self.round_scores: Dict[int, float] = {1: 0.0, 2: 0.0}
        self.round_history: Dict[str, tuple] = {}
        self.briscola: Optional[Suit] = None
        self.briscola_selector: Optional[int] = None
        self.first_of_turn: int = 0
        self.table_tuples: List[Tuple[int, Card]] = []
        self.table_dicts: List[dict] = []
        self.maraffa_forced: bool = False
        self.done: bool = False
        self.game_id: str = game_id
        self.tracker: Optional[GameTracker] = tracker


# ── Simulator ──────────────────────────────────────────────────────────────────

class Simulator:
    """Cross-game batched Marafone simulator.

    ``model_path=None`` → random self-play (uniform over legal moves), no
    XGBoost calls. Used to bootstrap v1.

    With a model, every decision point gathers candidate feature rows from all
    active games and runs **one** ``xgb.predict`` batch — collapses the
    per-game inference cost ~1000-fold.
    """

    def __init__(self, model_path: Optional[Path], epsilon: float = 0.0,
                 exploration_top_k: int = 3):
        self.random_mode = model_path is None
        self.epsilon = float(epsilon)
        self.exploration_top_k = max(2, int(exploration_top_k))
        self._rng: random.Random = random.Random()  # re-seeded per run()

        if self.random_mode:
            self.agent = None
            self._booster = None
            self._feature_sel: Optional[np.ndarray] = None
            self._feat_names = _COL_NAMES
            self._feat_types = _COL_TYPES
            return

        self.agent = MLAgent(model_path)
        self._booster = self.agent.model.get_booster()
        model_names = self._booster.feature_names
        model_types = self._booster.feature_types
        if model_names == _COL_NAMES:
            self._feature_sel = None
            self._feat_names = _COL_NAMES
            self._feat_types = _COL_TYPES
        else:
            self._feature_sel = np.array([_COL_IDX[n] for n in model_names], dtype=np.int32)
            self._feat_names = model_names
            self._feat_types = model_types

    # ── ε-greedy pick ─────────────────────────────────────────────────────────

    def _pick_index(self, preds_slice: np.ndarray) -> int:
        n = len(preds_slice)
        if n <= 1 or self.epsilon <= 0.0 or self._rng.random() >= self.epsilon:
            return int(preds_slice.argmax())
        k = min(self.exploration_top_k, n)
        top_k_idx = np.argpartition(-preds_slice, k - 1)[:k]
        return int(self._rng.choice(top_k_idx.tolist()))

    # ── Inference ─────────────────────────────────────────────────────────────

    def _predict_matrix(self, arr: np.ndarray) -> np.ndarray:
        if self._feature_sel is not None:
            arr = arr[:, self._feature_sel]
        dmat = xgb.DMatrix(arr, feature_names=self._feat_names, feature_types=self._feat_types)
        return self._booster.predict(dmat)

    def _batched_predict(self, rows: List[np.ndarray]) -> np.ndarray:
        arr = np.stack(rows) if rows else np.empty((0, len(_COL_NAMES)), dtype=np.float32)
        return self._predict_matrix(arr)

    # ── Context builders ──────────────────────────────────────────────────────

    def _build_ctx(self, state: _GameState, seat: int,
                   round_num: int, turn_num: int) -> dict:
        return {
            "seat": seat,
            "round_num": round_num,
            "turn_num": turn_num,
            "briscola_selector_seat": state.briscola_selector,
            "table_cards": list(state.table_tuples),
            "round_scores": {1: round(state.round_scores[1], 2),
                             2: round(state.round_scores[2], 2)},
            "total_scores": dict(state.total_scores),
            "hand": state.hands[seat],
        }

    @staticmethod
    def _seat_at_position(state: _GameState, position: int) -> int:
        return (state.first_of_turn + position) % 4

    # ── Briscola selection (batched across games) ─────────────────────────────

    def _select_briscolas(self, states: List[_GameState], round_num: int) -> None:
        if self.random_mode:
            suits = list(Suit)
            for state in states:
                if state.done:
                    continue
                state.briscola = self._rng.choice(suits)
            return

        rows: List[np.ndarray] = []
        slices: List[List[Tuple[int, int]]] = []
        targets: List[_GameState] = []

        for state in states:
            if state.done:
                continue
            targets.append(state)
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
                            self.agent._build_np_row(
                                card, decl, suit, ctx, force_lead=True
                            )
                        )
                per_suit.append((lo, len(rows)))
            slices.append(per_suit)

        if not rows:
            return
        preds = self._batched_predict(rows)

        for state, per_suit in zip(targets, slices):
            suit_values = np.array(
                [preds[lo:hi].max() if hi > lo else -np.inf for (lo, hi) in per_suit],
                dtype=np.float32,
            )
            state.briscola = list(Suit)[int(suit_values.argmax())]

    # ── Card selection per position ───────────────────────────────────────────

    def _select_cards_per_position(
        self, states: List[_GameState], round_num: int, turn_num: int, position: int
    ) -> Dict[int, Tuple[Card, Optional[str]]]:
        if self.random_mode:
            return self._random_decisions(states, position)

        all_rows: List[np.ndarray] = []
        slices: List[Tuple[int, int]] = []
        candidates: List[List[Tuple[Card, Optional[str]]]] = []
        game_indices: List[int] = []

        is_lead_pos = (position == 0)
        cum_rows = 0

        for gi, state in enumerate(states):
            if state.done:
                continue
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
                # Group candidates by suit → one base row per distinct suit.
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
        preds = self._predict_matrix(arr)

        decisions: Dict[int, Tuple[Card, Optional[str]]] = {}
        for gi, cands, (lo, hi) in zip(game_indices, candidates, slices):
            pick = self._pick_index(preds[lo:hi])
            decisions[gi] = cands[pick]
        return decisions

    def _random_decisions(
        self, states: List[_GameState], position: int
    ) -> Dict[int, Tuple[Card, Optional[str]]]:
        is_lead_pos = (position == 0)
        decisions: Dict[int, Tuple[Card, Optional[str]]] = {}
        for gi, state in enumerate(states):
            if state.done:
                continue
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

    # ── Feature row builders (fast path) ──────────────────────────────────────

    def _build_base_row(
        self,
        state: _GameState,
        seat: int,
        round_num: int,
        turn_num: int,
        lead_suit_value: str,
        is_lead_pos: bool,
    ) -> np.ndarray:
        """Shared portion of the feature row for one (game, seat) decision point.

        Candidate-specific cells (card_rank, card_is_briscola, card_is_lead,
        declaration) stay at template defaults and get patched per-candidate.
        """
        row = _ROW_TEMPLATE.copy()
        my_team = _TEAM_OF[seat]
        briscola_str = state.briscola.value
        table = state.table_tuples
        play_order = len(table)

        row[_CI_ROUND]    = round_num
        row[_CI_TURN]     = turn_num
        row[_CI_ORDER]    = play_order
        row[_CI_TEAM]     = float(my_team)
        row[_CI_BSUIT]    = _SUIT_ENC[briscola_str]
        bss = state.briscola_selector
        if bss is not None:
            row[_CI_BSEL] = float(_TEAM_OF[bss] == my_team)
        row[_CI_ISLEAD]   = 1.0 if is_lead_pos else 0.0
        row[_CI_LEADSUIT] = _SUIT_ENC[lead_suit_value]

        for i in range(min(3, len(table))):
            s_seat, c = table[i]
            cs = c.suit.value
            ib = int(cs == briscola_str)
            il = int(cs == lead_suit_value and cs != briscola_str)
            row[_CI_TABLE_RANK[i]] = c.rank
            row[_CI_TABLE_IB[i]]   = ib
            row[_CI_TABLE_IL[i]]   = il
            row[_CI_TABLE_MT[i]]   = float(_TEAM_OF[s_seat] == my_team)

        row[_CI_RS1] = round(state.round_scores[1], 2)
        row[_CI_RS2] = round(state.round_scores[2], 2)
        row[_CI_TS1] = state.total_scores[1]
        row[_CI_TS2] = state.total_scores[2]

        for c in state.hands[seat]:
            cs = c.suit.value
            if cs == briscola_str:
                row[_CI_HAND_BRISCOLA[c.rank - 1]] = 1.0
            elif cs == lead_suit_value:
                row[_CI_HAND_LEAD[c.rank - 1]] = 1.0
            else:
                row[_CI_HAND_OTHER[c.rank - 1]] += 1.0

        for key, (hs, ht, hd) in state.round_history.items():
            suit_str, rank_str = key.rsplit("_", 1)
            suit_idx = _SUITS.index(suit_str)
            cid = suit_idx * 10 + (int(rank_str) - 1)
            row[_CI_HIST_MT[cid]]   = float(_TEAM_OF[hs] == my_team)
            row[_CI_HIST_TURN[cid]] = float(ht)
            if hd:
                row[_CI_HIST_DECL[cid]] = _DECL_ENC.get(hd, np.nan)

        def _status(target_seat: int) -> float:
            found: List[Tuple[int, str]] = []
            for key, (hs, ht, hd) in state.round_history.items():
                if hs == target_seat and hd:
                    suit_str = key.rsplit("_", 1)[0]
                    if suit_str == lead_suit_value:
                        found.append((ht, hd))
            if not found:
                return _STATUS_ENC["unknown"]
            if any(d == "volo" for _, d in found):
                return _STATUS_ENC["void"]
            _, latest = max(found, key=lambda x: x[0])
            return _STATUS_ENC["has" if latest == "striscio" else "busso"]

        row[_CI_PSTAT] = _status((seat + 2) % 4)
        row[_CI_LSTAT] = _status((seat + 1) % 4)
        row[_CI_RSTAT] = _status((seat + 3) % 4)
        return row

    @staticmethod
    def _expand_candidates(
        base: np.ndarray,
        cands: List[Tuple[Card, Optional[str]]],
        briscola_str: str,
        lead_suit_value: str,
    ) -> np.ndarray:
        """Tile ``base (N_COLS,)`` to ``(K, N_COLS)`` and patch candidate cells."""
        K = len(cands)
        rows = np.broadcast_to(base, (K, base.shape[0])).copy()
        for i, (card, decl) in enumerate(cands):
            cs = card.suit.value
            ib = 1 if cs == briscola_str else 0
            il = 1 if (cs == lead_suit_value and cs != briscola_str) else 0
            rows[i, _CI_CARD_RANK] = card.rank
            rows[i, _CI_CARD_IB]   = ib
            rows[i, _CI_CARD_IL]   = il
            rows[i, _CI_DECL]      = _DECL_ENC[decl] if decl else np.nan
        return rows

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(
        self,
        n_games: int,
        seed: Optional[int] = None,
        output_path: Optional[Path] = None,
        flush_every_rounds: int = 5,
        progress_every: int = 0,
    ) -> np.ndarray:
        """Simulate ``n_games``; return ``(n_games, 2)`` int16 final totals.

        If ``output_path`` is set, also stream a per-play Parquet dataset.
        """
        rng = random.Random(seed)
        self._rng = random.Random(None if seed is None else (seed ^ 0x9E3779B9))
        emit_rows = output_path is not None
        states = [
            _GameState(
                game_id=f"G{i:07d}",
                tracker=GameTracker(f"G{i:07d}") if emit_rows else None,
            )
            for i in range(n_games)
        ]
        round_num = 0
        rounds_since_flush = 0

        writer: Optional[pq.ParquetWriter] = None
        if emit_rows:
            output_path.parent.mkdir(parents=True, exist_ok=True)

        def _flush_rows() -> None:
            nonlocal writer
            buf: List[dict] = []
            for s in states:
                if s.tracker is not None and s.tracker.rows:
                    buf.extend(s.tracker.rows)
                    s.tracker.rows = []
            if not buf:
                return
            table = _rows_to_table(buf)
            if writer is None:
                writer = pq.ParquetWriter(str(output_path), table.schema, compression="snappy")
            writer.write_table(table)

        try:
            while not all(s.done for s in states):
                round_num += 1

                # ── Deal & determine selector ────────────────────────────────
                for state in states:
                    if state.done:
                        continue
                    deck = Deck()
                    rng.shuffle(deck.cards)
                    for s in _SEATS:
                        state.hands[s] = deck.cards[s * 10:(s + 1) * 10]

                    if state.briscola_selector is None:
                        for s in _SEATS:
                            if KEY_CARD in state.hands[s]:
                                state.briscola_selector = s
                                break

                    state.round_history = {}
                    state.round_scores = {1: 0.0, 2: 0.0}
                    state.table_tuples = []
                    state.table_dicts = []
                    state.maraffa_forced = False

                if self.agent is not None:
                    self.agent.reset_round()

                # ── Briscola (batched) ───────────────────────────────────────
                self._select_briscolas(states, round_num)

                # Maraffa bonus + forced lead + emit briscola_set
                for state in states:
                    if state.done:
                        continue
                    hand = state.hands[state.briscola_selector]
                    mar = [c for c in hand if c.suit == state.briscola and c.rank in (1, 2, 3)]
                    if len(mar) == 3:
                        state.total_scores[_TEAM[state.briscola_selector]] += 3
                        state.maraffa_forced = True
                    state.first_of_turn = state.briscola_selector

                    if state.tracker is not None:
                        state.tracker.on_event({"type": "briscola_set", "data": {
                            "suit": state.briscola.value,
                            "by_seat": state.briscola_selector,
                            "by_name": "",
                        }})

                # ── 10 turns ─────────────────────────────────────────────────
                for turn_idx in range(10):
                    turn_num = turn_idx + 1
                    for state in states:
                        if not state.done:
                            state.table_tuples = []
                            state.table_dicts = []

                    for position in range(4):
                        decisions = self._select_cards_per_position(
                            states, round_num, turn_num, position
                        )

                        for gi, (card, decl) in decisions.items():
                            state = states[gi]
                            seat = self._seat_at_position(state, position)
                            declaration = decl if position == 0 else None

                            # Snapshot hand BEFORE removing the card.
                            if state.tracker is not None:
                                hand_before = [
                                    {"suit": c.suit.value, "rank": c.rank}
                                    for c in state.hands[seat]
                                ]

                            state.hands[seat].remove(card)
                            key = f"{card.suit.value}_{card.rank}"
                            state.round_history[key] = (seat, turn_num, declaration or "")
                            state.table_tuples.append((seat, card))
                            card_dict = {"suit": card.suit.value, "rank": card.rank}
                            state.table_dicts.append({"seat": seat, "card": card_dict})

                            if state.tracker is not None:
                                state.tracker.on_event({"type": "card_played", "data": {
                                    "seat": seat,
                                    "card": card_dict,
                                    "declaration": declaration,
                                    "table": state.table_dicts,
                                    "hand_before": hand_before,
                                }})

                        for state in states:
                            state.maraffa_forced = False

                    # ── Turn winner & points ─────────────────────────────────
                    for state in states:
                        if state.done:
                            continue
                        winner_seat = determine_turn_winner(state.table_tuples, state.briscola)
                        winner_team = _TEAM[winner_seat]
                        pts = sum(RANK_TO_POINTS[c.rank] for _, c in state.table_tuples)
                        state.round_scores[winner_team] += pts
                        state.first_of_turn = winner_seat

                        if state.tracker is not None:
                            state.tracker.on_event({"type": "turn_result", "data": {
                                "winner_seat": winner_seat,
                                "winner_team": winner_team,
                                "winner_name": "",
                                "points": round(pts, 2),
                                "round_scores": {
                                    1: round(state.round_scores[1], 2),
                                    2: round(state.round_scores[2], 2),
                                },
                            }})

                # ── Last-trick bonus, floor, totals ──────────────────────────
                for state in states:
                    if state.done:
                        continue
                    state.round_scores[_TEAM[state.first_of_turn]] += 1
                    s1 = floor(state.round_scores[1])
                    s2 = floor(state.round_scores[2])
                    state.total_scores[1] += int(s1)
                    state.total_scores[2] += int(s2)

                    if state.tracker is not None:
                        state.tracker.on_event({"type": "round_end", "data": {
                            "round": round_num,
                            "round_scores": {1: int(s1), 2: int(s2)},
                            "total_scores": dict(state.total_scores),
                        }})

                    if max(state.total_scores.values()) >= GAME_WIN_THRESHOLD:
                        state.done = True
                    else:
                        state.briscola_selector = (state.briscola_selector + 1) % 4

                rounds_since_flush += 1
                if emit_rows and rounds_since_flush >= flush_every_rounds:
                    _flush_rows()
                    rounds_since_flush = 0

                if progress_every and round_num % progress_every == 0:
                    n_active = sum(1 for s in states if not s.done)
                    logger.info("round %d done — %d/%d games still active",
                                round_num, n_active, n_games)

            if emit_rows:
                _flush_rows()
        finally:
            if writer is not None:
                writer.close()

        out = np.zeros((n_games, 2), dtype=np.int16)
        for i, s in enumerate(states):
            out[i, 0] = s.total_scores[1]
            out[i, 1] = s.total_scores[2]
        return out


# ── Public entry point ─────────────────────────────────────────────────────────

def simulate(
    n_games: int,
    model_path: Optional[Path] = None,
    epsilon: float = 0.0,
    seed: Optional[int] = None,
    output_path: Optional[Path] = None,
) -> np.ndarray:
    """Run ``n_games`` self-play games. Returns ``(n_games, 2)`` final totals.

    Args:
        n_games:     number of games to simulate.
        model_path:  trained ``.joblib`` for ML self-play. ``None`` → random
                     self-play (uniform over legal moves; no XGBoost calls).
        epsilon:     ε-greedy exploration rate (ML mode only). 0 = argmax.
        seed:        RNG seed for reproducible deals.
        output_path: if given, stream per-play features as a Parquet dataset.
    """
    if model_path is None:
        logger.info("Random self-play — %d games", n_games)
    else:
        logger.info("ML self-play — %d games  model=%s  ε=%.2f",
                    n_games, model_path, epsilon)
    if output_path is not None:
        logger.info("Per-play Parquet → %s", output_path)

    sim = Simulator(model_path, epsilon=epsilon)
    t0 = time.perf_counter()
    totals = sim.run(
        n_games=n_games,
        seed=seed,
        output_path=output_path,
        flush_every_rounds=5,
        progress_every=1,
    )
    dt = time.perf_counter() - t0
    team1_wins = int((totals[:, 0] > totals[:, 1]).sum())
    logger.info(
        "Done in %.1fs (%.1f ms/game) — team1=%d team2=%d  means t1=%.2f t2=%.2f",
        dt, 1e3 * dt / max(1, n_games),
        team1_wins, n_games - team1_wins,
        float(totals[:, 0].mean()), float(totals[:, 1].mean()),
    )
    return totals
