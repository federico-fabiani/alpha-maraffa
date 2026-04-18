"""ML-based bot: uses a trained XGBoost model to evaluate every legal move."""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb

from aimaraffa.engine import Card, Suit, get_valid_cards, get_valid_declarations

logger = logging.getLogger(__name__)

_SUITS            = ["bastoni", "denara", "spade", "coppe"]
_RANKS            = list(range(1, 11))
_SUIT_CATS        = ["bastoni", "coppe", "denara", "spade"]
_DECL_CATS        = ["busso", "striscio", "volo"]
_SUIT_STATUS_CATS = ["busso", "has", "unknown", "void"]
_TEAM_OF          = {0: 1, 1: 2, 2: 1, 3: 2}


class MLAgent:
    """
    Stateful ML bot that mirrors the per-play feature schema used during training.

    Lifecycle per game:
      - reset_round()         called at the start of every round
      - record_card(...)      called after every card is played (all seats)
      - select_briscola(ctx)  called when this bot must choose the briscola suit
      - select_card(ctx, briscola)  called when this bot must play a card
    """

    def __init__(self, model_path: Path):
        self.model = joblib.load(model_path)
        self._history: Dict[str, tuple] = {}  # "suit_rank" → (seat, turn_num, decl)
        logger.info("MLAgent: model loaded from %s", model_path)

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
        """
        Choose the best briscola suit by averaging model predictions across all
        possible first-card plays for each candidate suit.
        """
        hand = ctx["hand"]
        best_suit, best_val = None, float("-inf")

        for suit in Suit:
            rows = []
            for card in hand:
                hand_after = [c for c in hand if c != card]
                for decl in get_valid_declarations(hand_after, card.suit):
                    rows.append(self._build_row(card, decl, suit, ctx,
                                                force_lead=True))
            preds = self._predict(rows)
            val = float(np.mean(preds))
            logger.debug("  briscola %s → avg_diff=%.3f", suit.value, val)
            if val > best_val:
                best_val, best_suit = val, suit

        logger.debug("select_briscola → %s", best_suit.value)
        return best_suit

    def select_card(self, ctx: dict, briscola: Suit) -> Tuple[Card, Optional[str]]:
        """
        Evaluate every (valid_card × valid_declaration) combination and return the best.
        Declarations are only valid when leading; striscio/volo depend on hand state.
        """
        hand        = ctx["hand"]
        table_cards = ctx.get("table_cards", [])
        lead_suit   = table_cards[0][1].suit if table_cards else None
        valid       = get_valid_cards(hand, lead_suit)
        is_lead     = len(table_cards) == 0

        candidates = []
        for card in valid:
            if is_lead:
                hand_after = [c for c in hand if c != card]
                decls = get_valid_declarations(hand_after, card.suit)
            else:
                decls = [None]
            for decl in decls:
                candidates.append((card, decl))

        rows  = [self._build_row(c, d, briscola, ctx) for c, d in candidates]
        preds = self._predict(rows)

        best_idx           = int(np.argmax(preds))
        best_card, best_decl = candidates[best_idx]
        logger.debug("select_card → %s  decl=%s  score=%.3f",
                     best_card, best_decl, preds[best_idx])
        return best_card, best_decl

    # ── Feature construction ───────────────────────────────────────────────────

    def _build_row(self, card: Card, declaration: Optional[str],
                   briscola: Suit, ctx: dict,
                   force_lead: bool = False) -> dict:
        """Build one inference feature row matching the training schema exactly."""
        seat        = ctx["seat"]
        my_team     = _TEAM_OF[seat]
        table_cards = [] if force_lead else ctx.get("table_cards", [])
        play_order  = len(table_cards)
        briscola_str = briscola.value
        lead_str    = (table_cards[0][1].suit.value if table_cards
                       else card.suit.value)         # lead = our card when play_order==0

        def role(s: str) -> Tuple[int, int]:
            return int(s == briscola_str), int(s == lead_str and s != briscola_str)

        cib, cil = role(card.suit.value)

        # Table slots: team-relative (1=my team, 0=opponent, None=empty)
        def tslot(i) -> Tuple:
            if i >= len(table_cards):
                return None, None, None, None
            s, c = table_cards[i]
            ib, il = role(c.suit.value)
            return c.rank, ib, il, int(_TEAM_OF[s] == my_team)

        t0r, t0ib, t0il, t0im = tslot(0)
        t1r, t1ib, t1il, t1im = tslot(1)
        t2r, t2ib, t2il, t2im = tslot(2)

        # Hand relative features — hand_before includes candidate card (matches training)
        hb = {f"hand_briscola_{r}": 0 for r in _RANKS}
        hl = {f"hand_lead_{r}":     0 for r in _RANKS}
        ho = {f"hand_other_{r}_count": 0 for r in _RANKS}
        for c in ctx["hand"]:
            ib_c, il_c = role(c.suit.value)
            if ib_c:
                hb[f"hand_briscola_{c.rank}"] = 1
            elif il_c:
                hl[f"hand_lead_{c.rank}"] = 1
            else:
                ho[f"hand_other_{c.rank}_count"] += 1

        # History: team-relative (1=my team, 0=opponent, -1=not played)
        hfeat: dict = {f"hist_{s}_{r}_is_my_team": -1 for s in _SUITS for r in _RANKS}
        hfeat.update({f"hist_{s}_{r}_turn": -1 for s in _SUITS for r in _RANKS})
        hfeat.update({f"hist_{s}_{r}_decl": "" for s in _SUITS for r in _RANKS})
        for key, (hs, ht, hd) in self._history.items():
            hfeat[f"hist_{key}_is_my_team"] = int(_TEAM_OF[hs] == my_team)
            hfeat[f"hist_{key}_turn"] = ht
            hfeat[f"hist_{key}_decl"] = hd

        # Suit status features: declarative signals from partner and opponents
        partner_seat   = (seat + 2) % 4
        opp_left_seat  = (seat + 1) % 4
        opp_right_seat = (seat + 3) % 4

        def _suit_status(target_seat: int) -> str:
            decls = [
                (ht, hd)
                for key, (hs, ht, hd) in self._history.items()
                if hs == target_seat and key.rsplit("_", 1)[0] == lead_str and hd
            ]
            if not decls:
                return "unknown"
            if any(d == "volo" for _, d in decls):
                return "void"
            _, latest = max(decls, key=lambda x: x[0])
            return "has" if latest == "striscio" else "busso"

        rs = ctx.get("round_scores",  {1: 0.0, 2: 0.0})
        ts = ctx.get("total_scores",  {1: 0,   2: 0})

        bss = ctx.get("briscola_selector_seat")
        bss_is_my_team = int(_TEAM_OF[bss] == my_team) if bss is not None else -1

        return {
            "round_num":                  ctx.get("round_num", 1),
            "turn_num":                   ctx.get("turn_num", 1),
            "play_order":                 play_order,
            "seat":                       seat,
            "team":                       my_team,
            "briscola_suit":              briscola_str,
            "briscola_selector_is_my_team": bss_is_my_team,
            "card_rank":                  card.rank,
            "card_is_briscola":           cib,
            "card_is_lead":               cil,
            "is_lead":                    int(play_order == 0),
            "lead_suit":                  lead_str,
            "declaration":                declaration,           # None → NaN via encoding
            "table_0_rank":          t0r, "table_0_is_briscola": t0ib,
            "table_0_is_lead":       t0il, "table_0_is_my_team": t0im,
            "table_1_rank":          t1r, "table_1_is_briscola": t1ib,
            "table_1_is_lead":       t1il, "table_1_is_my_team": t1im,
            "table_2_rank":          t2r, "table_2_is_briscola": t2ib,
            "table_2_is_lead":       t2il, "table_2_is_my_team": t2im,
            "round_score_t1":        rs[1], "round_score_t2": rs[2],
            "total_score_t1":        ts[1], "total_score_t2": ts[2],
            **hb, **hl, **ho,
            **hfeat,
            "partner_suit_status":   _suit_status(partner_seat),
            "opp_left_suit_status":  _suit_status(opp_left_seat),
            "opp_right_suit_status": _suit_status(opp_right_seat),
        }

    def _predict(self, rows: List[dict]) -> np.ndarray:
        """Encode rows and run inference, passing enable_categorical explicitly."""
        df = pd.DataFrame(rows)

        for col in ["briscola_suit", "lead_suit"]:
            df[col] = pd.Categorical(df[col], categories=_SUIT_CATS)

        decl_cols = ["declaration"] + [c for c in df.columns if c.endswith("_decl")]
        for col in decl_cols:
            df[col] = pd.Categorical(df[col], categories=_DECL_CATS)

        for col in ["partner_suit_status", "opp_left_suit_status", "opp_right_suit_status"]:
            if col in df.columns:
                df[col] = pd.Categorical(df[col], categories=_SUIT_STATUS_CATS)

        # table_*_rank, *_is_briscola, *_is_lead, *_is_my_team may be None → float NaN
        for col in [c for c in df.columns if c.startswith("table_")]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        dmat = xgb.DMatrix(df, enable_categorical=True)
        return self.model.get_booster().predict(dmat)
