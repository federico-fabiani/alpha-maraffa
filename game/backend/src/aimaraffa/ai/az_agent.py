"""AlphaZero-style ISMCTS-driven agent for tournament + live play.

Wraps an ``AZPolicyValue`` model and runs ISMCTS at every decision.
Implements the ``BaseAgent`` interface so it drops into the existing
tournament harness and the websocket game loop.

Two performance modes
---------------------
* ``mcts_simulations > 0`` — full ISMCTS at every decision.  Strongest
  play.  ~50–200 ms per decision on CPU depending on width.
* ``mcts_simulations == 0`` — pure-policy greedy: argmax over masked
  logits, no search.  Useful for fast eval of the network alone.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import torch

from aimaraffa.agents.base import BaseAgent
from aimaraffa.engine import Card, Suit

from .belief        import BeliefState
from .fast_engine   import (
    NUM_SEATS, HAND_SIZE, GameState,
    DECL_NONE, DECL_BUSSO, DECL_STRISCIO, DECL_VOLO,
    card_id_from_engine, engine_card_from_id, suit_from_id, suit_id,
    seat_to_play,
)
from .az_features   import (
    encode_state, legal_action_mask, action_index, split_action,
)
from .az_model      import AZPolicyValue
from .ismcts        import ISMCTS, make_torch_eval_fn
from . import config_az as cfg


_DECL_INT_TO_STR = {DECL_NONE: None, DECL_BUSSO: "busso", DECL_STRISCIO: "striscio", DECL_VOLO: "volo"}
_DECL_STR_TO_INT = {None: DECL_NONE, "busso": DECL_BUSSO, "striscio": DECL_STRISCIO, "volo": DECL_VOLO}


class AZAgent(BaseAgent):
    """ISMCTS + neural net agent.

    Parameters
    ----------
    model_path : path to a ``.pt`` checkpoint produced by ``az_train``.
    device     : torch device for inference ("cpu" or "cuda").
    n_simulations / n_determinizations / c_puct : ISMCTS knobs.
    use_search : when False, use pure policy network (no MCTS).
    """

    def __init__(
        self,
        model_path:         Path,
        device:             str = "cpu",
        n_simulations:      int = cfg.EVAL_N_SIMULATIONS,
        n_determinizations: int = cfg.EVAL_N_DETERMINIZATIONS,
        c_puct:             float = cfg.EVAL_C_PUCT,
        use_search:         bool  = True,
        seed:               Optional[int] = None,
    ):
        self.model      = AZPolicyValue.load(Path(model_path), device=device)
        self.device     = device
        self.use_search = use_search
        self.n_sims     = n_simulations
        self.n_dets     = n_determinizations
        self.c_puct     = c_puct
        self._eval_fn   = make_torch_eval_fn(self.model, device=device)
        self._mcts: Optional[ISMCTS] = None
        if use_search:
            self._mcts = ISMCTS(
                self._eval_fn,
                c_puct             = c_puct,
                n_simulations      = n_simulations,
                n_determinizations = n_determinizations,
                dirichlet_eps      = 0.0,   # no noise at eval
                seed               = seed,
            )

        # Live state mirror (for record_card / live game loop integration).
        self._state: GameState = GameState()
        self._round_started = False
        self._briscola_selected = False

    # ── BaseAgent contract ────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "az"

    def reset_round(self) -> None:
        self._state = GameState()
        self._round_started = False
        self._briscola_selected = False

    def record_card(
        self,
        card:        Card,
        seat:        int,
        turn_num:    int,
        declaration: Optional[str],
    ) -> None:
        # Live state catches up here; we treat the websocket / tournament
        # as authoritative for what was played, since we may not have
        # observed our own decisions through this path (the harness calls
        # select_card to get the move, then record_card for everyone).
        from .fast_engine import apply_card

        cid = card_id_from_engine(card)
        is_lead = (self._state.table_pos == 0)
        decl = _DECL_STR_TO_INT.get(declaration, DECL_NONE) if is_lead else DECL_NONE
        apply_card(self._state, seat, cid, decl)

    def select_briscola(self, ctx: dict) -> Suit:
        """Briscola selection.

        At round 1 the slow harness deals into engine.Card lists; we
        rebuild a fast-engine state from ctx['hand'] and the seat.  We
        currently delegate to a hand-built rule (longest suit, cricca
        bonus) implemented inside HeuristicAgent to avoid having a
        learned briscola head.  This matches what the BC pipeline did.
        """
        from aimaraffa.agents.heuristic_agent import HeuristicAgent
        return HeuristicAgent().select_briscola(ctx)

    def select_card(self, ctx: dict, briscola: Suit) -> Tuple[Card, Optional[str]]:
        """Run ISMCTS (or greedy net) and return the chosen ``(card, decl)``.

        We rebuild the fast-engine ``GameState`` from ``ctx`` rather than
        relying on ``record_card`` for our own move — that path is
        called *after* ``select_card``, so the local mirror is one step
        behind from our POV.
        """
        seat = ctx["seat"]
        # Sync local state with ctx (in case we missed updates).
        self._sync_state_from_ctx(ctx, briscola)

        belief = BeliefState.from_state(self._state, seat)
        mask   = legal_action_mask(self._state, seat)

        if self.use_search and self._mcts is not None:
            dist, _ = self._mcts.search(self._state, root_seat=seat, belief=belief)
            action_idx = int(np.argmax(dist))
        else:
            feats = encode_state(self._state, seat, belief)
            with torch.inference_mode():
                logits, _ = self._eval_fn(feats[None].astype(np.float32),
                                          mask[None].astype(bool))
            action_idx = int(torch.softmax(logits[0], dim=-1).argmax())

        cid, decl = split_action(action_idx)
        # Sanity: if MCTS returned an illegal due to broken belief, fall back to mask argmax.
        if not mask[action_idx]:
            legal = np.flatnonzero(mask)
            if legal.size == 0:
                # Should never happen — pick anything from hand.
                hand_arr = self._state.hands[seat]
                hand_arr = hand_arr[hand_arr >= 0]
                cid = int(hand_arr[0])
                decl = DECL_NONE
            else:
                action_idx = int(legal[0])
                cid, decl = split_action(action_idx)

        card = engine_card_from_id(cid)
        return card, _DECL_INT_TO_STR.get(decl, None)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _sync_state_from_ctx(self, ctx: dict, briscola: Suit) -> None:
        """Fill self._state from a tournament-harness ctx if not already in sync.

        Tournament harness calls ``record_card`` for *all* plays (including
        ours), so by the time ``select_card`` is called for the next play,
        our internal state is already up-to-date.  This method just sets
        the briscola and selector once at round start, in case the harness
        skipped the briscola_selection notification.
        """
        if not self._briscola_selected and briscola is not None:
            self._state.briscola = suit_id(briscola)
            sel = ctx.get("briscola_selector_seat")
            if sel is not None:
                self._state.briscola_selector = int(sel)
                if self._state.first_of_turn == 0 and self._state.turn_num == 0 and self._state.table_pos == 0:
                    self._state.first_of_turn = int(sel)
            # Set our own hand from ctx['hand'] — the harness gives it canonical.
            seat = ctx["seat"]
            hand_engine = ctx.get("hand", [])
            self._state.hands[seat][:] = -1
            for i, c in enumerate(hand_engine[:HAND_SIZE]):
                self._state.hands[seat][i] = card_id_from_engine(c)
            self._state.n_cards[seat] = len(hand_engine)
            self._briscola_selected = True

        # Always trust ctx['hand'] for our own seat (the harness keeps it accurate).
        seat = ctx["seat"]
        hand_engine = ctx.get("hand", [])
        self._state.hands[seat][:] = -1
        for i, c in enumerate(hand_engine[:HAND_SIZE]):
            self._state.hands[seat][i] = card_id_from_engine(c)
        self._state.n_cards[seat] = len(hand_engine)
