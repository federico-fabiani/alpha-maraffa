"""ML-based bot: uses a trained XGBoost model to evaluate every legal move."""

import logging
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import xgboost as xgb

from aimaraffa.agents.base import BaseAgent
from aimaraffa.engine import Card, Suit, get_valid_cards, get_valid_declarations

logger = logging.getLogger(__name__)

# ── Categorical encoding ───────────────────────────────────────────────────────
# Integer codes must match the pd.Categorical(categories=...) order used in training.

_SUITS   = ["bastoni", "denara", "spade", "coppe"]   # history column ordering
_RANKS   = list(range(1, 11))
_TEAM_OF = {0: 1, 1: 2, 2: 1, 3: 2}

_SUIT_ENC   = {"bastoni": 0.0, "coppe": 1.0, "denara": 2.0, "spade": 3.0}
_DECL_ENC   = {"busso": 0.0, "striscio": 1.0, "volo": 2.0}
_STATUS_ENC = {"busso": 0.0, "has": 1.0, "unknown": 2.0, "void": 3.0}

# ── Feature schema ─────────────────────────────────────────────────────────────
# Columns in the exact order produced by _FIELDNAMES minus _DROP in simulate_game.py.
# 'q' = quantitative, 'c' = categorical (XGBoost native categorical splits).

_SCHEMA: List[Tuple[str, str]] = (
    [
        ("round_num",                    "q"),
        ("turn_num",                     "q"),
        ("play_order",                   "q"),
        ("team",                         "q"),   # present in pre-v2 models; ignored by v2+
        ("briscola_suit",                "c"),
        ("briscola_selector_is_my_team", "q"),
        ("card_rank",                    "q"),
        ("card_is_briscola",             "q"),
        ("card_is_lead",                 "q"),
        ("is_lead",                      "q"),
        ("lead_suit",                    "c"),
        ("declaration",                  "c"),
        ("table_0_rank",                 "q"),
        ("table_0_is_briscola",          "q"),
        ("table_0_is_lead",              "q"),
        ("table_0_is_my_team",           "q"),
        ("table_1_rank",                 "q"),
        ("table_1_is_briscola",          "q"),
        ("table_1_is_lead",              "q"),
        ("table_1_is_my_team",           "q"),
        ("table_2_rank",                 "q"),
        ("table_2_is_briscola",          "q"),
        ("table_2_is_lead",              "q"),
        ("table_2_is_my_team",           "q"),
        ("round_score_t1",               "q"),
        ("round_score_t2",               "q"),
        ("total_score_t1",               "q"),
        ("total_score_t2",               "q"),
    ] +
    [(f"hand_briscola_{r}",    "q") for r in _RANKS] +
    [(f"hand_lead_{r}",        "q") for r in _RANKS] +
    [(f"hand_other_{r}_count", "q") for r in _RANKS] +
    [(f"hist_{s}_{r}_is_my_team", "q") for s in _SUITS for r in _RANKS] +
    [(f"hist_{s}_{r}_turn",       "q") for s in _SUITS for r in _RANKS] +
    [(f"hist_{s}_{r}_decl",       "c") for s in _SUITS for r in _RANKS] +
    [
        ("partner_suit_status",   "c"),
        ("opp_left_suit_status",  "c"),
        ("opp_right_suit_status", "c"),
    ]
)

_COL_NAMES: List[str]     = [name  for name, _     in _SCHEMA]
_COL_TYPES: List[str]     = [ftype for _,    ftype in _SCHEMA]
_COL_IDX:   Dict[str, int] = {name: i for i, name in enumerate(_COL_NAMES)}
_N_COLS = len(_COL_NAMES)

# Pre-built template — copied once per candidate row, avoids rebuilding defaults
_ROW_TEMPLATE: np.ndarray = np.full(_N_COLS, np.nan, dtype=np.float32)
for _r in _RANKS:
    _ROW_TEMPLATE[_COL_IDX[f"hand_briscola_{_r}"]]    = 0.0
    _ROW_TEMPLATE[_COL_IDX[f"hand_lead_{_r}"]]        = 0.0
    _ROW_TEMPLATE[_COL_IDX[f"hand_other_{_r}_count"]] = 0.0
for _s in _SUITS:
    for _r in _RANKS:
        _ROW_TEMPLATE[_COL_IDX[f"hist_{_s}_{_r}_is_my_team"]] = -1.0
        _ROW_TEMPLATE[_COL_IDX[f"hist_{_s}_{_r}_turn"]]       = -1.0
        # hist_*_decl stays NaN — not played → missing category
for _col in ("partner_suit_status", "opp_left_suit_status", "opp_right_suit_status"):
    _ROW_TEMPLATE[_COL_IDX[_col]] = _STATUS_ENC["unknown"]


class MLAgent(BaseAgent):
    """
    Stateful ML bot that mirrors the per-play feature schema used during training.

    Lifecycle per round:
      - reset_round()               called at the start of every round
      - record_card(...)            called after every card is played (all seats)
      - select_briscola(ctx)        called when this bot must choose the briscola suit
      - select_card(ctx, briscola)  called when this bot must play a card
    """

    @property
    def name(self) -> str:
        return "ml"

    def __init__(self, model_path: Path, epsilon: float = 0.0,
                 exploration_top_k: int = 3, seed: Optional[int] = None):
        """
        Args:
          epsilon: with probability ε, pick uniformly among the top-K candidates
                   instead of argmax (ε-greedy exploration for self-play diversity).
          exploration_top_k: K for the top-K sampling pool (min(K, n_valid)).
          seed:    seed for the exploration RNG. None → system entropy.
        """
        self.model = joblib.load(model_path)
        self.epsilon = float(epsilon)
        self.exploration_top_k = max(2, int(exploration_top_k))
        self._rng = random.Random(seed)
        self._history: Dict[str, tuple] = {}  # "suit_rank" → (seat, turn_num, decl)
        logger.info("MLAgent: model loaded from %s (epsilon=%.2f)", model_path, self.epsilon)

    # ── Round state management ─────────────────────────────────────────────────

    def reset_round(self) -> None:
        self._history = {}

    def record_card(self, card: Card, seat: int,
                    turn_num: int, declaration: Optional[str]) -> None:
        self._history[f"{card.suit.value}_{card.rank}"] = (
            seat, turn_num, declaration or ""
        )

    # ── Public selectors ───────────────────────────────────────────────────────

    def select_briscola(self, ctx: dict) -> Suit:
        """Choose the briscola whose best opening line has the highest predicted value."""
        hand = ctx["hand"]
        best_suit, best_val = None, float("-inf")

        for suit in Suit:
            rows = []
            for card in hand:
                hand_after = [c for c in hand if c != card]
                for decl in get_valid_declarations(hand_after, card.suit):
                    rows.append(self._build_np_row(card, decl, suit, ctx, force_lead=True))
            val = float(np.max(self._predict(rows)))
            logger.debug("  briscola %s → best_opening_diff=%.3f", suit.value, val)
            if val > best_val:
                best_val, best_suit = val, suit

        logger.debug("select_briscola → %s", best_suit.value)
        return best_suit

    def select_card(self, ctx: dict, briscola: Suit) -> Tuple[Card, Optional[str]]:
        """Evaluate every (valid_card × valid_declaration) and return the best."""
        hand        = ctx["hand"]
        table_cards = ctx.get("table_cards", [])
        lead_suit   = table_cards[0][1].suit if table_cards else None
        valid       = get_valid_cards(hand, lead_suit)
        is_lead     = len(table_cards) == 0

        candidates = []
        for card in valid:
            decls = (get_valid_declarations([c for c in hand if c != card], card.suit)
                     if is_lead else [None])
            for decl in decls:
                candidates.append((card, decl))

        preds = self._predict([self._build_np_row(c, d, briscola, ctx)
                               for c, d in candidates])
        pick = self._pick_index(preds)
        best_card, best_decl = candidates[pick]
        logger.debug("select_card → %s  decl=%s  score=%.3f  (argmax=%d, picked=%d)",
                     best_card, best_decl, float(preds[pick]),
                     int(np.argmax(preds)), pick)
        return best_card, best_decl

    # ── ε-greedy sampling ──────────────────────────────────────────────────────

    def _pick_index(self, preds: np.ndarray) -> int:
        """Return argmax, or (with prob ε) a random pick from the top-K predictions."""
        n = len(preds)
        if n <= 1 or self.epsilon <= 0.0 or self._rng.random() >= self.epsilon:
            return int(np.argmax(preds))
        k = min(self.exploration_top_k, n)
        # -preds ⇒ smallest = best; take first K indices by partition
        top_k_idx = np.argpartition(-preds, k - 1)[:k]
        return int(self._rng.choice(top_k_idx.tolist()))

    # ── Feature construction ───────────────────────────────────────────────────

    def _build_np_row(self, card: Card, declaration: Optional[str],
                      briscola: Suit, ctx: dict,
                      force_lead: bool = False) -> np.ndarray:
        """Build one inference row as a pre-encoded float32 numpy array."""
        row = _ROW_TEMPLATE.copy()
        ri  = _COL_IDX  # local alias for speed

        seat         = ctx["seat"]
        my_team      = _TEAM_OF[seat]
        table_cards  = [] if force_lead else ctx.get("table_cards", [])
        row[ri["team"]] = float(my_team)
        play_order   = len(table_cards)
        briscola_str = briscola.value
        lead_str     = (table_cards[0][1].suit.value if table_cards else card.suit.value)

        def role(s: str) -> Tuple[int, int]:
            return int(s == briscola_str), int(s == lead_str and s != briscola_str)

        cib, cil = role(card.suit.value)

        # ── Scalars ────────────────────────────────────────────────────────────
        row[ri["round_num"]]    = ctx.get("round_num", 1)
        row[ri["turn_num"]]     = ctx.get("turn_num",  1)
        row[ri["play_order"]]   = play_order
        row[ri["briscola_suit"]] = _SUIT_ENC.get(briscola_str, np.nan)

        bss = ctx.get("briscola_selector_seat")
        row[ri["briscola_selector_is_my_team"]] = (
            float(_TEAM_OF[bss] == my_team) if bss is not None else np.nan
        )

        row[ri["card_rank"]]        = card.rank
        row[ri["card_is_briscola"]] = cib
        row[ri["card_is_lead"]]     = cil
        row[ri["is_lead"]]          = float(play_order == 0)
        row[ri["lead_suit"]]        = _SUIT_ENC.get(lead_str, np.nan)
        row[ri["declaration"]]      = _DECL_ENC[declaration] if declaration else np.nan

        # ── Table slots ────────────────────────────────────────────────────────
        for i, (s, c) in enumerate(table_cards[:3]):
            ib, il = role(c.suit.value)
            row[ri[f"table_{i}_rank"]]        = c.rank
            row[ri[f"table_{i}_is_briscola"]] = ib
            row[ri[f"table_{i}_is_lead"]]     = il
            row[ri[f"table_{i}_is_my_team"]]  = float(_TEAM_OF[s] == my_team)

        # ── Scores ─────────────────────────────────────────────────────────────
        rs = ctx.get("round_scores", {1: 0.0, 2: 0.0})
        ts = ctx.get("total_scores", {1: 0,   2: 0})
        row[ri["round_score_t1"]] = rs[1]
        row[ri["round_score_t2"]] = rs[2]
        row[ri["total_score_t1"]] = ts[1]
        row[ri["total_score_t2"]] = ts[2]

        # ── Hand ───────────────────────────────────────────────────────────────
        for c in ctx["hand"]:
            ib_c, il_c = role(c.suit.value)
            if ib_c:
                row[ri[f"hand_briscola_{c.rank}"]] = 1.0
            elif il_c:
                row[ri[f"hand_lead_{c.rank}"]] = 1.0
            else:
                row[ri[f"hand_other_{c.rank}_count"]] += 1.0

        # ── History ────────────────────────────────────────────────────────────
        for key, (hs, ht, hd) in self._history.items():
            row[ri[f"hist_{key}_is_my_team"]] = float(_TEAM_OF[hs] == my_team)
            row[ri[f"hist_{key}_turn"]]       = float(ht)
            if hd:
                row[ri[f"hist_{key}_decl"]] = _DECL_ENC.get(hd, np.nan)

        # ── Suit status ────────────────────────────────────────────────────────
        def _status(target_seat: int) -> float:
            decls = [
                (ht, hd)
                for key, (hs, ht, hd) in self._history.items()
                if hs == target_seat and key.rsplit("_", 1)[0] == lead_str and hd
            ]
            if not decls:
                return _STATUS_ENC["unknown"]
            if any(d == "volo" for _, d in decls):
                return _STATUS_ENC["void"]
            _, latest = max(decls, key=lambda x: x[0])
            return _STATUS_ENC["has" if latest == "striscio" else "busso"]

        row[ri["partner_suit_status"]]   = _status((seat + 2) % 4)
        row[ri["opp_left_suit_status"]]  = _status((seat + 1) % 4)
        row[ri["opp_right_suit_status"]] = _status((seat + 3) % 4)

        return row

    # ── Inference ──────────────────────────────────────────────────────────────

    def _predict(self, rows: List[np.ndarray]) -> np.ndarray:
        """Stack pre-encoded rows and run XGBoost inference — no pandas."""
        arr     = np.stack(rows)
        booster = self.model.get_booster()
        model_names = booster.feature_names
        model_types = booster.feature_types
        if model_names == _COL_NAMES:
            dmat = xgb.DMatrix(arr, feature_names=_COL_NAMES, feature_types=_COL_TYPES)
        else:
            sel   = [_COL_IDX[n] for n in model_names]
            dmat  = xgb.DMatrix(arr[:, sel], feature_names=model_names, feature_types=model_types)
        return booster.predict(dmat)
