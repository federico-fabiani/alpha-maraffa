"""RLAgent — BaseAgent adapter for the RL policy.

Wraps a ``MarafonePolicy`` in the ``BaseAgent`` interface so the RL model
can participate in the existing tournament and live-game infrastructure
without any changes to those components.

Briscola selection: mirrors the XGBoost ``select_briscola`` approach —
build candidate rows for all (suit × card × declaration) triples, score
them with the policy, take max per suit, pick argmax suit.

Card selection: enumerate valid (card, declaration) pairs, build feature
rows, run policy, return argmax (greedy, no sampling during eval).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch

from aimaraffa.engine import Card, Suit, get_valid_cards, get_valid_declarations
from aimaraffa.agents.base import BaseAgent
from aimaraffa.agents.ml_agent import (
    _COL_IDX, _COL_NAMES, _COL_TYPES,
    _DECL_ENC, _ROW_TEMPLATE, _STATUS_ENC, _SUIT_ENC, _TEAM_OF,
)

from .rl_model import MarafonePolicy

logger = logging.getLogger(__name__)

_SUITS = ["bastoni", "denara", "spade", "coppe"]
_RANKS = list(range(1, 11))


class RLAgent(BaseAgent):
    """Greedy-argmax RL agent for tournament / live play."""

    @property
    def name(self) -> str:
        return "rl"

    def __init__(self, model_path: Path, device: str = "cpu"):
        self.device = device
        self.policy = MarafonePolicy.load(model_path, device=device)
        self.policy.eval()
        self._history: Dict[str, tuple] = {}
        logger.info("RLAgent: loaded %s on %s", model_path, device)

    # ── Round lifecycle ────────────────────────────────────────────────────────

    def reset_round(self) -> None:
        self._history = {}

    def record_card(
        self, card: Card, seat: int, turn_num: int, declaration: Optional[str]
    ) -> None:
        self._history[f"{card.suit.value}_{card.rank}"] = (
            seat, turn_num, declaration or ""
        )

    # ── Briscola selection ─────────────────────────────────────────────────────

    def select_briscola(self, ctx: dict) -> Suit:
        hand      = ctx["hand"]
        suits_list = list(Suit)
        best_suit, best_logit = None, float("-inf")

        for suit in suits_list:
            rows: List[np.ndarray] = []
            for card in hand:
                after = [c for c in hand if c != card]
                for decl in get_valid_declarations(after, card.suit):
                    rows.append(self._build_row(card, decl, suit, ctx, force_lead=True))
            if not rows:
                continue
            arr = np.stack(rows)
            t   = torch.from_numpy(arr).float().to(self.device)
            with torch.no_grad():
                logits, _ = self.policy(t)
            top = float(logits.max().item())
            if top > best_logit:
                best_logit, best_suit = top, suit

        if best_suit is None:
            best_suit = suits_list[0]
        logger.debug("RLAgent.select_briscola → %s (logit=%.3f)", best_suit.value, best_logit)
        return best_suit

    # ── Card selection ─────────────────────────────────────────────────────────

    def select_card(self, ctx: dict, briscola: Suit) -> Tuple[Card, Optional[str]]:
        hand        = ctx["hand"]
        table_cards = ctx.get("table_cards", [])
        lead_suit   = table_cards[0][1].suit if table_cards else None
        is_lead     = (len(table_cards) == 0)
        valid       = get_valid_cards(hand, lead_suit)

        candidates: List[Tuple[Card, Optional[str]]] = []
        for card in valid:
            decls = (
                get_valid_declarations([c for c in hand if c != card], card.suit)
                if is_lead else [None]
            )
            for decl in decls:
                candidates.append((card, decl))

        rows = [self._build_row(c, d, briscola, ctx) for c, d in candidates]
        arr  = np.stack(rows)
        t    = torch.from_numpy(arr).float().to(self.device)
        with torch.no_grad():
            logits, _ = self.policy(t)
        pick = int(logits.argmax().item())
        best_card, best_decl = candidates[pick]
        logger.debug("RLAgent.select_card → %s  decl=%s  logit=%.3f",
                     best_card, best_decl, float(logits[pick].item()))
        return best_card, best_decl

    # ── Feature row builder (mirrors ml_agent._build_np_row exactly) ──────────

    def _build_row(
        self,
        card:        Card,
        declaration: Optional[str],
        briscola:    Suit,
        ctx:         dict,
        force_lead:  bool = False,
    ) -> np.ndarray:
        row = _ROW_TEMPLATE.copy()
        ri  = _COL_IDX

        seat          = ctx["seat"]
        my_team       = _TEAM_OF[seat]
        table_cards   = [] if force_lead else ctx.get("table_cards", [])
        play_order    = len(table_cards)
        briscola_str  = briscola.value
        lead_str      = (
            table_cards[0][1].suit.value if table_cards else card.suit.value
        )

        def role(s: str) -> Tuple[int, int]:
            return int(s == briscola_str), int(s == lead_str and s != briscola_str)

        cib, cil = role(card.suit.value)

        row[ri["round_num"]]    = ctx.get("round_num", 1)
        row[ri["turn_num"]]     = ctx.get("turn_num", 1)
        row[ri["play_order"]]   = play_order
        row[ri["team"]]         = float(my_team)
        row[ri["briscola_suit"]] = _SUIT_ENC.get(briscola_str, np.nan)

        bss = ctx.get("briscola_selector_seat")
        if bss is not None:
            row[ri["briscola_selector_is_my_team"]] = float(_TEAM_OF[bss] == my_team)

        row[ri["card_rank"]]        = card.rank
        row[ri["card_is_briscola"]] = cib
        row[ri["card_is_lead"]]     = cil
        row[ri["is_lead"]]          = float(play_order == 0)
        row[ri["lead_suit"]]        = _SUIT_ENC.get(lead_str, np.nan)
        row[ri["declaration"]]      = _DECL_ENC[declaration] if declaration else np.nan

        for i, (s, c) in enumerate(table_cards[:3]):
            ib, il = role(c.suit.value)
            row[ri[f"table_{i}_rank"]]        = c.rank
            row[ri[f"table_{i}_is_briscola"]] = ib
            row[ri[f"table_{i}_is_lead"]]     = il
            row[ri[f"table_{i}_is_my_team"]]  = float(_TEAM_OF[s] == my_team)

        rs = ctx.get("round_scores", {1: 0.0, 2: 0.0})
        ts = ctx.get("total_scores", {1: 0, 2: 0})
        row[ri["round_score_t1"]] = rs[1]
        row[ri["round_score_t2"]] = rs[2]
        row[ri["total_score_t1"]] = ts[1]
        row[ri["total_score_t2"]] = ts[2]

        for c in ctx["hand"]:
            ib_c, il_c = role(c.suit.value)
            if ib_c:
                row[ri[f"hand_briscola_{c.rank}"]] = 1.0
            elif il_c:
                row[ri[f"hand_lead_{c.rank}"]] = 1.0
            else:
                row[ri[f"hand_other_{c.rank}_count"]] += 1.0

        for key, (hs, ht, hd) in self._history.items():
            row[ri[f"hist_{key}_is_my_team"]] = float(_TEAM_OF[hs] == my_team)
            row[ri[f"hist_{key}_turn"]]       = float(ht)
            if hd:
                row[ri[f"hist_{key}_decl"]]   = _DECL_ENC.get(hd, np.nan)

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
