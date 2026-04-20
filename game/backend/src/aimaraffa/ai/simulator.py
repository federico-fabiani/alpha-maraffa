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

import json as _json
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


# ── Rollout booster helper ─────────────────────────────────────────────────────

def _make_cpu_booster(booster: xgb.Booster) -> xgb.Booster:
    """Return a CPU-only copy of *booster* for fast rollout inference.

    Rollout predictions are tiny (1-5 rows). Creating a DMatrix and
    triggering a GPU transfer for each one costs ~5-20 ms per call.
    A CPU booster + ``inplace_predict`` avoids both overheads entirely.
    """
    cpu = xgb.Booster()
    cpu.load_model(bytearray(booster.save_raw("ubj")))
    cfg = _json.loads(cpu.save_config())
    cfg["learner"]["generic_param"]["device"] = "cpu"
    cpu.load_config(_json.dumps(cfg))
    return cpu


# ── Constants ──────────────────────────────────────────────────────────────────

_SUITS = ["bastoni", "denara", "spade", "coppe"]
_RANKS = list(range(1, 11))
_SEATS = (0, 1, 2, 3)
_TEAM  = {0: 1, 1: 2, 2: 1, 3: 2}

_DEFAULT_POLICY_LABEL = "random"


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
    + ["decision_id", "is_executed_action", "action_source"]
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
    "decision_id":                  "int32",
    "is_executed_action":           "int8",
    "action_source":                "category",
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
        self._decision_counter: int = 0

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
                "decision_id": self._decision_counter,
                "is_executed_action": 1,
                "action_source": "policy",
            }
            self._decision_counter += 1

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
                 "seat_policy",
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
        self.seat_policy: Dict[int, str] = {}
        self.game_id: str = game_id
        self.tracker: Optional[GameTracker] = tracker


def _normalize_policy_mix(seat_policy_mix: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
    total = 0.0
    normalized: List[Tuple[str, float]] = []
    for label, weight in seat_policy_mix:
        weight_f = float(weight)
        if weight_f <= 0.0:
            continue
        normalized.append((label, weight_f))
        total += weight_f
    if not normalized or total <= 0.0:
        raise ValueError("seat_policy_mix must contain at least one positive weight")
    return [(label, weight / total) for label, weight in normalized]


def _sample_policy_label(rng: random.Random, normalized_mix: List[Tuple[str, float]]) -> str:
    pick = rng.random()
    cumulative = 0.0
    for label, weight in normalized_mix:
        cumulative += weight
        if pick <= cumulative:
            return label
    return normalized_mix[-1][0]


def _policy_mix_has_learned_model(
    policy_models: Dict[str, Optional[Path]],
    seat_policy_mix: List[Tuple[str, float]],
) -> bool:
    """Return True when at least one label in the active mix has a real model."""
    return any(policy_models.get(label) is not None for label, _ in seat_policy_mix)


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
                 exploration_top_k: int = 3, *,
                 counterfactual: bool = False,
                 counterfactual_prob: float = 0.3,
                 counterfactual_alts: int = 2,
                 counterfactual_rollouts: int = 1):
        self.random_mode = model_path is None
        self.epsilon = float(epsilon)
        self.exploration_top_k = max(2, int(exploration_top_k))
        self._counterfactual = bool(counterfactual)
        self._cfact_prob = float(counterfactual_prob)
        self._cfact_alts = max(1, int(counterfactual_alts))
        self._cfact_rollouts = max(1, int(counterfactual_rollouts))
        self._cf_elapsed = 0.0  # cumulative seconds spent on CF rollouts
        self._cf_count = 0      # total CF rollouts executed
        self._rng: random.Random = random.Random()  # re-seeded per run()

        if self.random_mode:
            self.agent = None
            self._booster = None
            self._rollout_booster = None
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
        # CPU-only copy for rollout inference (avoids GPU transfer on tiny arrays).
        self._rollout_booster = _make_cpu_booster(self._booster)

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

    def _prepare_states(self, states: List[_GameState]) -> None:
        """Hook for subclasses that need per-game initialization before the run."""

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

    # ── Counterfactual rollout helpers ────────────────────────────────────────

    @staticmethod
    def _clone_state(state: _GameState) -> _GameState:
        """Lightweight copy of game state for counterfactual rollouts."""
        cs = _GameState.__new__(_GameState)
        cs.hands = {s: list(cards) for s, cards in state.hands.items()}
        cs.total_scores = dict(state.total_scores)
        cs.round_scores = dict(state.round_scores)
        cs.round_history = dict(state.round_history)
        cs.briscola = state.briscola
        cs.briscola_selector = state.briscola_selector
        cs.first_of_turn = state.first_of_turn
        cs.table_tuples = list(state.table_tuples)
        cs.table_dicts = []
        cs.maraffa_forced = state.maraffa_forced
        cs.done = state.done
        cs.seat_policy = dict(state.seat_policy)
        cs.game_id = state.game_id
        cs.tracker = None
        return cs

    def _rollout_predict_matrix(
        self, arr: np.ndarray,
        state: Optional[_GameState] = None,
        seat: Optional[int] = None,
    ) -> np.ndarray:
        """Fast CPU inference for counterfactual rollouts (avoids GPU round-trip)."""
        if self._rollout_booster is None:
            return np.zeros(arr.shape[0], dtype=np.float32)
        if self._feature_sel is not None:
            arr = arr[:, self._feature_sel]
        return self._rollout_booster.inplace_predict(arr, validate_features=False)

    def _rollout_single_decision(
        self,
        state: _GameState,
        seat: int,
        round_num: int,
        turn_num: int,
        position: int,
    ) -> Tuple[Card, Optional[str]]:
        """Pick one card for *seat* during a counterfactual rollout."""
        hand = state.hands[seat]
        lead_suit = state.table_tuples[0][1].suit if state.table_tuples else None
        is_lead = (position == 0)

        if state.maraffa_forced and seat == state.briscola_selector and lead_suit is None:
            forced = Card(state.briscola, 1)
            decls = get_valid_declarations(
                [c for c in hand if c != forced], forced.suit)
            return forced, self._rng.choice(decls)

        valid = get_valid_cards(hand, lead_suit)
        if is_lead:
            cands: List[Tuple[Card, Optional[str]]] = []
            for card in valid:
                after = [c for c in hand if c != card]
                for d in get_valid_declarations(after, card.suit):
                    cands.append((card, d))
        else:
            cands = [(c, None) for c in valid]

        if len(cands) <= 1:
            return cands[0] if cands else (valid[0], None)

        if self.random_mode:
            return self._rng.choice(cands)

        # Model-based: build rows, predict, argmax (greedy in rollout).
        briscola_str = state.briscola.value
        all_rows: List[np.ndarray] = []
        if is_lead:
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
            cands = ordered
        else:
            lead_value = lead_suit.value  # type: ignore[union-attr]
            base = self._build_base_row(
                state, seat, round_num, turn_num,
                lead_suit_value=lead_value, is_lead_pos=False,
            )
            rows = self._expand_candidates(base, cands, briscola_str, lead_value)
            all_rows.append(rows)

        arr = np.concatenate(all_rows) if len(all_rows) > 1 else all_rows[0]
        preds = self._rollout_predict_matrix(arr, state, seat)
        return cands[int(preds.argmax())]

    def _rollout_round_remainder(
        self,
        state: _GameState,
        round_num: int,
        current_turn: int,
        next_position: int,
    ) -> dict:
        """Play out the rest of a round on a cloned state.

        Returns ``{"round_scores": {1: int, 2: int},
                   "turn_winner": int, "turn_pts": float}``.
        """
        cf_turn_winner: Optional[int] = None
        cf_turn_pts: Optional[float] = None

        for turn_idx in range(current_turn - 1, 10):
            turn_num_t = turn_idx + 1
            if turn_num_t > current_turn:
                state.table_tuples = []
                state.maraffa_forced = False
                start_pos = 0
            else:
                start_pos = next_position

            for position in range(start_pos, 4):
                seat = self._seat_at_position(state, position)
                card, decl = self._rollout_single_decision(
                    state, seat, round_num, turn_num_t, position,
                )
                declaration = decl if position == 0 else None
                state.hands[seat].remove(card)
                key = f"{card.suit.value}_{card.rank}"
                state.round_history[key] = (seat, turn_num_t, declaration or "")
                state.table_tuples.append((seat, card))

            winner_seat = determine_turn_winner(state.table_tuples, state.briscola)
            winner_team = _TEAM[winner_seat]
            pts = sum(RANK_TO_POINTS[c.rank] for _, c in state.table_tuples)
            state.round_scores[winner_team] += pts
            state.first_of_turn = winner_seat

            if turn_num_t == current_turn:
                cf_turn_winner = winner_seat
                cf_turn_pts = pts

        state.round_scores[_TEAM[state.first_of_turn]] += 1
        return {
            "round_scores": {
                1: int(floor(state.round_scores[1])),
                2: int(floor(state.round_scores[2])),
            },
            "turn_winner": cf_turn_winner,
            "turn_pts": cf_turn_pts,
        }

    def _sample_alternatives(
        self,
        state: _GameState,
        seat: int,
        round_num: int,
        turn_num: int,
        position: int,
        alternatives: List[Tuple[Card, Optional[str]]],
        n: int,
    ) -> List[Tuple[Card, Optional[str], str]]:
        """Pick *n* alternative actions.  Returns ``(card, decl, source)``."""
        if len(alternatives) <= n:
            return [(c, d, "exhaustive") for c, d in alternatives]

        if self.random_mode:
            sampled = self._rng.sample(alternatives, n)
            return [(c, d, "random") for c, d in sampled]

        # Rank by model.  Take top-(n-1) + 1 random; if n==1, take top-1.
        briscola_str = state.briscola.value
        lead_suit = state.table_tuples[0][1].suit if state.table_tuples else None
        is_lead = (position == 0)

        all_rows: List[np.ndarray] = []
        if is_lead:
            by_suit: Dict[str, List[Tuple[Card, Optional[str]]]] = {}
            for cand in alternatives:
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
            alternatives = ordered
        else:
            lead_value = lead_suit.value  # type: ignore[union-attr]
            base = self._build_base_row(
                state, seat, round_num, turn_num,
                lead_suit_value=lead_value, is_lead_pos=False,
            )
            rows = self._expand_candidates(base, alternatives, briscola_str, lead_value)
            all_rows.append(rows)

        arr = np.concatenate(all_rows) if len(all_rows) > 1 else all_rows[0]
        preds = self._rollout_predict_matrix(arr, state, seat)

        n_topk = max(1, n - 1)
        k_safe = min(n_topk, len(preds) - 1)
        topk_idx = set(np.argpartition(-preds, k_safe)[:n_topk].tolist())
        result: List[Tuple[Card, Optional[str], str]] = [
            (alternatives[i][0], alternatives[i][1], "topk")
            for i in sorted(topk_idx)
        ]

        if n > 1:
            remaining = [i for i in range(len(alternatives)) if i not in topk_idx]
            if remaining:
                ri = self._rng.choice(remaining)
                result.append((alternatives[ri][0], alternatives[ri][1], "random"))

        return result[:n]

    def _build_cf_row(
        self,
        state: _GameState,
        seat: int,
        round_num: int,
        turn_num: int,
        position: int,
        card: Card,
        declaration: Optional[str],
        rollout: dict,
        decision_id: int,
        source: str,
    ) -> dict:
        """Build a complete dataset row for a counterfactual action."""
        briscola_str = state.briscola.value
        table = state.table_tuples
        lead_suit = table[0][1].suit.value if table else card.suit.value
        team = _TEAM[seat]
        opp = 3 - team
        cib, cil = _suit_role(card.suit.value, briscola_str, lead_suit)

        def _tslot(i: int) -> dict:
            if len(table) <= i:
                return {"rank": -1, "is_briscola": -1,
                        "is_lead": -1, "is_my_team": -1}
            s, c = table[i]
            ib, il = _suit_role(c.suit.value, briscola_str, lead_suit)
            return {"rank": c.rank, "is_briscola": ib, "is_lead": il,
                    "is_my_team": int(_TEAM[s] == team)}

        t0, t1, t2 = _tslot(0), _tslot(1), _tslot(2)

        hand_before = [{"suit": c.suit.value, "rank": c.rank}
                       for c in state.hands[seat]]

        rscores = rollout["round_scores"]
        final_diff = rscores[team] - rscores[opp]
        pre_turn_diff = (round(state.round_scores[team], 2)
                         - round(state.round_scores[opp], 2))
        tw = rollout["turn_winner"]

        return {
            "game_id": state.game_id,
            "round_num": round_num,
            "turn_num": turn_num,
            "play_order": position,
            "seat": seat,
            "team": team,
            "briscola_suit": briscola_str,
            "briscola_selector_is_my_team": int(
                _TEAM[state.briscola_selector] == team),
            "card_rank": card.rank,
            "card_is_briscola": cib,
            "card_is_lead": cil,
            "is_lead": int(position == 0),
            "lead_suit": lead_suit,
            "declaration": declaration or "",
            "table_0_rank": t0["rank"],
            "table_0_is_briscola": t0["is_briscola"],
            "table_0_is_lead": t0["is_lead"],
            "table_0_is_my_team": t0["is_my_team"],
            "table_1_rank": t1["rank"],
            "table_1_is_briscola": t1["is_briscola"],
            "table_1_is_lead": t1["is_lead"],
            "table_1_is_my_team": t1["is_my_team"],
            "table_2_rank": t2["rank"],
            "table_2_is_briscola": t2["is_briscola"],
            "table_2_is_lead": t2["is_lead"],
            "table_2_is_my_team": t2["is_my_team"],
            "round_score_t1": round(state.round_scores[1], 2),
            "round_score_t2": round(state.round_scores[2], 2),
            "total_score_t1": state.total_scores[1],
            "total_score_t2": state.total_scores[2],
            **_hand_features(hand_before, briscola_str, lead_suit),
            **_history_features(state.round_history, team),
            **_suit_status_features(seat, lead_suit, state.round_history),
            "turn_winner_seat": tw if tw is not None else -1,
            "turn_winner_team": _TEAM[tw] if tw is not None else -1,
            "turn_pts": rollout["turn_pts"] if rollout["turn_pts"] is not None else 0,
            "round_pts_t1": rscores[1],
            "round_pts_t2": rscores[2],
            "round_pts_player_team": rscores[team],
            "round_pts_diff": final_diff,
            "future_pts_diff": int(final_diff - pre_turn_diff),
            "decision_id": decision_id,
            "is_executed_action": 0,
            "action_source": source,
        }

    def _generate_counterfactuals(
        self,
        states: List[_GameState],
        decisions: Dict[int, Tuple[Card, Optional[str]]],
        round_num: int,
        turn_num: int,
        position: int,
    ) -> None:
        """Sample alternative actions, run rollouts, and append CF rows."""
        is_lead = (position == 0)
        t_start = time.perf_counter()
        n_rollouts_done = 0

        for gi, (chosen_card, chosen_decl) in decisions.items():
            state = states[gi]
            if state.tracker is None:
                continue
            if self._rng.random() >= self._cfact_prob:
                continue

            seat = self._seat_at_position(state, position)
            hand = state.hands[seat]
            lead_suit = (state.table_tuples[0][1].suit
                         if state.table_tuples else None)

            # Skip forced plays — no meaningful alternative.
            if (state.maraffa_forced and seat == state.briscola_selector
                    and lead_suit is None):
                continue

            # Enumerate legal candidates.
            valid = get_valid_cards(hand, lead_suit)
            if is_lead:
                all_cands: List[Tuple[Card, Optional[str]]] = []
                for card in valid:
                    after = [c for c in hand if c != card]
                    for d in get_valid_declarations(after, card.suit):
                        all_cands.append((card, d))
            else:
                all_cands = [(c, None) for c in valid]

            alternatives = [
                (c, d) for c, d in all_cands
                if not (c == chosen_card and d == chosen_decl)
            ]
            if not alternatives:
                continue

            alt_actions = self._sample_alternatives(
                state, seat, round_num, turn_num, position,
                alternatives, self._cfact_alts,
            )

            decision_id = state.tracker._decision_counter

            for alt_card, alt_decl, source in alt_actions:
                # Run N rollouts and average the round scores.
                accumulated: Dict[int, float] = {1: 0.0, 2: 0.0}
                last_tw: Optional[int] = None
                last_tp: Optional[float] = None
                for _ in range(self._cfact_rollouts):
                    cf_state = self._clone_state(state)
                    cf_seat = self._seat_at_position(cf_state, position)
                    declaration = alt_decl if is_lead else None
                    cf_state.hands[cf_seat].remove(alt_card)
                    key = f"{alt_card.suit.value}_{alt_card.rank}"
                    cf_state.round_history[key] = (
                        cf_seat, turn_num, declaration or "")
                    cf_state.table_tuples.append((cf_seat, alt_card))

                    rollout = self._rollout_round_remainder(
                        cf_state, round_num, turn_num, position + 1,
                    )
                    accumulated[1] += rollout["round_scores"][1]
                    accumulated[2] += rollout["round_scores"][2]
                    last_tw = rollout["turn_winner"]
                    last_tp = rollout["turn_pts"]
                    n_rollouts_done += 1

                avg_rollout = {
                    "round_scores": {
                        1: int(round(accumulated[1] / self._cfact_rollouts)),
                        2: int(round(accumulated[2] / self._cfact_rollouts)),
                    },
                    "turn_winner": last_tw,
                    "turn_pts": last_tp,
                }

                row = self._build_cf_row(
                    state, seat, round_num, turn_num, position,
                    alt_card, declaration, avg_rollout, decision_id, source,
                )
                state.tracker.rows.append(row)

        elapsed = time.perf_counter() - t_start
        self._cf_elapsed += elapsed
        self._cf_count += n_rollouts_done

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(
        self,
        n_games: int,
        seed: Optional[int] = None,
        output_path: Optional[Path] = None,
        flush_every_rounds: int = 5,
        progress_every: int = 0,
        game_id_offset: int = 0,
    ) -> np.ndarray:
        """Simulate ``n_games``; return ``(n_games, 2)`` int16 final totals.

        If ``output_path`` is set, also stream a per-play Parquet dataset.
        ``game_id_offset`` shifts game IDs so parallel workers produce unique IDs.
        """
        rng = random.Random(seed)
        self._rng = random.Random(None if seed is None else (seed ^ 0x9E3779B9))
        emit_rows = output_path is not None
        states = [
            _GameState(
                game_id=f"G{i + game_id_offset:07d}",
                tracker=GameTracker(f"G{i + game_id_offset:07d}") if emit_rows else None,
            )
            for i in range(n_games)
        ]
        self._prepare_states(states)
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

                        # Counterfactual: sample alternative actions before
                        # the chosen card is applied to the state.
                        if self._counterfactual and emit_rows:
                            self._generate_counterfactuals(
                                states, decisions, round_num, turn_num, position,
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


class PolicyMixSimulator(Simulator):
    """Simulator variant that samples the acting seat's policy from a configured mix."""

    def __init__(
        self,
        policy_models: Dict[str, Optional[Path]],
        seat_policy_mix: List[Tuple[str, float]],
        epsilon: float = 0.0,
        exploration_top_k: int = 3, *,
        counterfactual: bool = False,
        counterfactual_prob: float = 0.3,
        counterfactual_alts: int = 2,
        counterfactual_rollouts: int = 1,
    ):
        self.random_mode = False
        self.epsilon = float(epsilon)
        self.exploration_top_k = max(2, int(exploration_top_k))
        self._counterfactual = bool(counterfactual)
        self._cfact_prob = float(counterfactual_prob)
        self._cfact_alts = max(1, int(counterfactual_alts))
        self._cfact_rollouts = max(1, int(counterfactual_rollouts))
        self._cf_elapsed = 0.0
        self._cf_count = 0
        self._rng: random.Random = random.Random()
        self._policy_models = dict(policy_models)
        self._seat_policy_mix = _normalize_policy_mix(seat_policy_mix)
        self._agents: Dict[str, MLAgent] = {}
        self._kits: Dict[str, tuple] = {}

        for label, model_path in self._policy_models.items():
            if model_path is None:
                continue
            agent = MLAgent(model_path)
            booster = agent.model.get_booster()
            names = booster.feature_names
            types = booster.feature_types
            sel = None
            if names != _COL_NAMES:
                sel = np.array([_COL_IDX[name] for name in names], dtype=np.int32)
            self._agents[label] = agent
            self._kits[label] = (booster, sel, names, types)

        self._feature_agent: Optional[MLAgent] = next(iter(self._agents.values()), None)
        # Base Simulator.run() calls self.agent.reset_round() between rounds.
        self.agent = self._feature_agent

        # CPU-only rollout kits: (cpu_booster, sel) — avoids GPU transfer on
        # the tiny per-decision arrays used in counterfactual rollouts.
        self._rollout_kits: Dict[str, Tuple[xgb.Booster, Optional[np.ndarray]]] = {
            label: (_make_cpu_booster(booster), sel)
            for label, (booster, sel, _names, _types) in self._kits.items()
        }

    def _prepare_states(self, states: List[_GameState]) -> None:
        for state in states:
            state.seat_policy = {
                seat: _sample_policy_label(self._rng, self._seat_policy_mix)
                for seat in _SEATS
            }

    def _policy_key_for_seat(self, state: _GameState, seat: int) -> str:
        return state.seat_policy.get(seat, _DEFAULT_POLICY_LABEL)

    def _predict_with_kit(self, key: str, arr: np.ndarray) -> np.ndarray:
        booster, sel, names, types = self._kits[key]
        if sel is not None:
            arr = arr[:, sel]
        dmat = xgb.DMatrix(arr, feature_names=names, feature_types=types)
        return booster.predict(dmat)

    def _rollout_predict_matrix(
        self, arr: np.ndarray,
        state: Optional[_GameState] = None,
        seat: Optional[int] = None,
    ) -> np.ndarray:
        """Policy-aware fast CPU inference for counterfactual rollouts.

        Uses the CPU rollout kit for the policy assigned to *seat* in the
        cloned state — same policy population as the parent trajectory, but
        with ``inplace_predict`` on CPU to avoid GPU transfer overhead on
        the tiny per-decision arrays.
        """
        key: Optional[str] = None
        if state is not None and seat is not None:
            key = self._policy_key_for_seat(state, seat)
        if key and key in self._rollout_kits:
            rb, sel = self._rollout_kits[key]
        else:
            # Fallback: first available CPU kit (or zeros when no model).
            for rb, sel in self._rollout_kits.values():
                break
            else:
                return np.zeros(arr.shape[0], dtype=np.float32)
        if sel is not None:
            arr = arr[:, sel]
        return rb.inplace_predict(arr, validate_features=False)

    def _select_briscolas(self, states: List[_GameState], round_num: int) -> None:
        groups: Dict[str, List[_GameState]] = {}
        suits = list(Suit)
        for state in states:
            if state.done:
                continue
            key = self._policy_key_for_seat(state, state.briscola_selector)
            groups.setdefault(key, []).append(state)

        for key, group in groups.items():
            if key not in self._kits or self._feature_agent is None:
                for state in group:
                    state.briscola = self._rng.choice(suits)
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

            preds = self._predict_with_kit(key, np.stack(rows))
            for state, per_suit in zip(group, slices):
                suit_values = np.array(
                    [preds[lo:hi].max() if hi > lo else -np.inf for (lo, hi) in per_suit],
                    dtype=np.float32,
                )
                state.briscola = suits[int(suit_values.argmax())]

    def _select_cards_per_position(
        self, states: List[_GameState], round_num: int, turn_num: int, position: int
    ) -> Dict[int, Tuple[Card, Optional[str]]]:
        decisions: Dict[int, Tuple[Card, Optional[str]]] = {}
        grouped: Dict[str, List[Tuple[int, _GameState]]] = {}
        for gi, state in enumerate(states):
            if state.done:
                continue
            seat = self._seat_at_position(state, position)
            key = self._policy_key_for_seat(state, seat)
            grouped.setdefault(key, []).append((gi, state))

        for key, indexed_states in grouped.items():
            if key not in self._kits:
                decisions.update(self._random_subset_decisions(indexed_states, position))
                continue
            decisions.update(
                self._decide_for_subset(indexed_states, round_num, turn_num, position, key)
            )
        return decisions

    def _decide_for_subset(
        self,
        indexed_states: List[Tuple[int, _GameState]],
        round_num: int, turn_num: int, position: int,
        key: str,
    ) -> Dict[int, Tuple[Card, Optional[str]]]:
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
                    suit_value = cand[0].suit.value
                    by_suit.setdefault(suit_value, []).append(cand)
                ordered: List[Tuple[Card, Optional[str]]] = []
                for suit_value, group in by_suit.items():
                    base = self._build_base_row(
                        state, seat, round_num, turn_num,
                        lead_suit_value=suit_value, is_lead_pos=True,
                    )
                    rows = self._expand_candidates(base, group, briscola_str, suit_value)
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
            pick = self._pick_index(preds[lo:hi])
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


# ── Public entry point ─────────────────────────────────────────────────────────

def simulate(
    n_games: int,
    model_path: Optional[Path] = None,
    epsilon: float = 0.0,
    exploration_top_k: int = 3,
    seed: Optional[int] = None,
    output_path: Optional[Path] = None,
    policy_models: Optional[Dict[str, Optional[Path]]] = None,
    seat_policy_mix: Optional[List[Tuple[str, float]]] = None,
    counterfactual: bool = False,
    counterfactual_prob: float = 0.3,
    counterfactual_alts: int = 2,
    counterfactual_rollouts: int = 1,
    n_workers: int = 1,
    _game_id_offset: int = 0,
) -> np.ndarray:
    """Run ``n_games`` self-play games. Returns ``(n_games, 2)`` final totals.

    Args:
        n_games:     number of games to simulate.
        model_path:  trained ``.joblib`` for ML self-play. ``None`` → random
                     self-play (uniform over legal moves; no XGBoost calls).
        epsilon:     ε-greedy exploration rate (ML mode only). 0 = argmax.
        exploration_top_k: number of high-value moves eligible during ε exploration.
        seed:        RNG seed for reproducible deals.
        output_path: if given, stream per-play features as a Parquet dataset.
        policy_models: optional label → model mapping used for mixed-policy training.
        seat_policy_mix: optional seat-level sampling distribution over policy labels.
        counterfactual: if ``True``, sample alternative actions and estimate their
                        value via round-remainder rollouts.
        counterfactual_prob: probability of sampling alternatives per decision.
        counterfactual_alts: number of alternative actions per sampled decision.
        counterfactual_rollouts: number of rollouts per alternative (averaged).
        n_workers:   number of parallel worker processes. Each worker simulates an
                     independent chunk; results are merged before returning.
                     Requires ``n_workers == 1`` inside a worker (no nesting).
        _game_id_offset: internal — start offset for ``game_id`` labels. Used by
                         multiprocessing workers to ensure unique IDs across chunks.
    """
    # ── Parallel dispatch ─────────────────────────────────────────────────────
    if n_workers > 1 and n_games > 1:
        import multiprocessing as _mp

        n_workers = min(n_workers, n_games)
        chunk_size = n_games // n_workers
        chunk_args: List[dict] = []
        offset = _game_id_offset
        for wi in range(n_workers):
            ng = chunk_size if wi < n_workers - 1 else n_games - (offset - _game_id_offset)
            chunk_out: Optional[str] = None
            if output_path is not None:
                chunk_out = str(
                    output_path.with_name(f"_chunk{wi:04d}_{output_path.name}")
                )
            chunk_args.append({
                "n_games": ng,
                "game_id_offset": offset,
                "seed": None if seed is None else (seed + wi * 999_983),
                "output_path": chunk_out,
                "model_path": str(model_path) if model_path is not None else None,
                "epsilon": epsilon,
                "exploration_top_k": exploration_top_k,
                "policy_models": (
                    {k: (str(v) if v is not None else None) for k, v in policy_models.items()}
                    if policy_models is not None else None
                ),
                "seat_policy_mix": (
                    list(seat_policy_mix) if seat_policy_mix is not None else None
                ),
                "counterfactual": counterfactual,
                "counterfactual_prob": counterfactual_prob,
                "counterfactual_alts": counterfactual_alts,
                "counterfactual_rollouts": counterfactual_rollouts,
            })
            offset += ng

        ctx = _mp.get_context("spawn")
        logger.info(
            "Parallel simulation — %d workers × ~%d games each",
            n_workers, chunk_size,
        )
        t0 = time.perf_counter()
        with ctx.Pool(n_workers) as pool:
            results = pool.map(_simulate_chunk, chunk_args)

        totals = np.concatenate([np.array(r, dtype=np.int16) for r in results])

        if output_path is not None:
            chunk_paths = [c["output_path"] for c in chunk_args if c["output_path"]]
            tables = [pq.read_table(p) for p in chunk_paths]
            merged = pa.concat_tables(tables)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(merged, str(output_path), compression="snappy")
            for p in chunk_paths:
                Path(p).unlink(missing_ok=True)

        dt = time.perf_counter() - t0
        team1_wins = int((totals[:, 0] > totals[:, 1]).sum())
        logger.info(
            "Done (parallel) in %.1fs (%.1f ms/game) — %d workers — "
            "team1=%d team2=%d  means t1=%.2f t2=%.2f",
            dt, 1e3 * dt / max(1, n_games), n_workers,
            team1_wins, n_games - team1_wins,
            float(totals[:, 0].mean()), float(totals[:, 1].mean()),
        )
        return totals

    # ── Single-process path ───────────────────────────────────────────────────
    cf_kw = dict(counterfactual=counterfactual,
                 counterfactual_prob=counterfactual_prob,
                 counterfactual_alts=counterfactual_alts,
                 counterfactual_rollouts=counterfactual_rollouts)
    if seat_policy_mix is not None:
        resolved_policy_models = {label: None for label, _ in seat_policy_mix}
        if policy_models is not None:
            resolved_policy_models.update(policy_models)
        if _policy_mix_has_learned_model(resolved_policy_models, seat_policy_mix):
            logger.info(
                "Mixed-policy self-play — %d games  ε=%.2f  mix=%s  cf=%s",
                n_games, epsilon, seat_policy_mix, counterfactual,
            )
            sim = PolicyMixSimulator(
                policy_models=resolved_policy_models,
                seat_policy_mix=seat_policy_mix,
                epsilon=epsilon,
                exploration_top_k=exploration_top_k,
                **cf_kw,
            )
        else:
            logger.info(
                "Mixed-policy self-play requested, but all labels resolve to random; "
                "using random self-play fast path for %d games  cf=%s",
                n_games, counterfactual,
            )
            sim = Simulator(
                None,
                epsilon=epsilon,
                exploration_top_k=exploration_top_k,
                **cf_kw,
            )
    elif model_path is None:
        logger.info("Random self-play — %d games  cf=%s", n_games, counterfactual)
        sim = Simulator(model_path, epsilon=epsilon,
                        exploration_top_k=exploration_top_k, **cf_kw)
    else:
        logger.info("ML self-play — %d games  model=%s  ε=%.2f  cf=%s",
                    n_games, model_path, epsilon, counterfactual)
        sim = Simulator(model_path, epsilon=epsilon,
                        exploration_top_k=exploration_top_k, **cf_kw)
    if output_path is not None:
        logger.info("Per-play Parquet → %s", output_path)

    t0 = time.perf_counter()
    totals = sim.run(
        n_games=n_games,
        seed=seed,
        output_path=output_path,
        flush_every_rounds=5,
        progress_every=1,
        game_id_offset=_game_id_offset,
    )
    dt = time.perf_counter() - t0
    team1_wins = int((totals[:, 0] > totals[:, 1]).sum())
    logger.info(
        "Done in %.1fs (%.1f ms/game) — team1=%d team2=%d  means t1=%.2f t2=%.2f",
        dt, 1e3 * dt / max(1, n_games),
        team1_wins, n_games - team1_wins,
        float(totals[:, 0].mean()), float(totals[:, 1].mean()),
    )
    if counterfactual and sim._cf_count > 0:
        cf_pct = 100.0 * sim._cf_elapsed / max(dt, 1e-9)
        logger.info(
            "Counterfactual: %d rollouts in %.1fs (%.0f%% of total, "
            "%.2f ms/rollout)",
            sim._cf_count, sim._cf_elapsed, cf_pct,
            1e3 * sim._cf_elapsed / sim._cf_count,
        )
    return totals


# ── Multiprocessing worker ─────────────────────────────────────────────────────
# Must be a top-level function — not nested — so Python's ``spawn`` start method
# can pickle it on Windows.

def _simulate_chunk(kwargs: dict) -> list:
    """Worker entry point: reconstruct args, call simulate(), return totals list.

    All model loading happens inside the spawned process.  Nothing is shared
    with the parent — each worker loads its own copy of the model.
    """
    from pathlib import Path as _Path

    out          = kwargs.get("output_path")
    model_path   = kwargs.get("model_path")
    policy_models_raw = kwargs.get("policy_models")

    policy_models: Optional[Dict[str, Optional[Path]]] = None
    if policy_models_raw is not None:
        policy_models = {
            label: (_Path(p) if p is not None else None)
            for label, p in policy_models_raw.items()
        }

    totals = simulate(
        n_games             = kwargs["n_games"],
        model_path          = _Path(model_path) if model_path is not None else None,
        epsilon             = kwargs.get("epsilon", 0.0),
        exploration_top_k   = kwargs.get("exploration_top_k", 3),
        seed                = kwargs.get("seed"),
        output_path         = _Path(out) if out is not None else None,
        policy_models       = policy_models,
        seat_policy_mix     = kwargs.get("seat_policy_mix"),
        counterfactual      = kwargs.get("counterfactual", False),
        counterfactual_prob = kwargs.get("counterfactual_prob", 0.3),
        counterfactual_alts = kwargs.get("counterfactual_alts", 2),
        counterfactual_rollouts = kwargs.get("counterfactual_rollouts", 1),
        n_workers           = 1,                         # no recursive spawning
        _game_id_offset     = kwargs.get("game_id_offset", 0),
    )
    return totals.tolist()
