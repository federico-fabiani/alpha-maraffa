"""Single-Observer Information-Set MCTS with neural priors for Marafone.

Reference: Cowling, Powley & Whitehouse — "Information Set Monte Carlo
Tree Search" (2012).

Algorithm
---------
For each search call from a root state ``s_root`` and root seat:

    Repeat ``n_simulations`` times:
        1. **Determinize**: sample a consistent opponent-hand assignment
           given the current belief.
        2. **Selection**: descend the tree by PUCT, restricted to actions
           legal in the current determinization.
        3. **Expansion**: at the first state with no node yet, create one;
           query the neural net for (prior, value) and store.  Children
           created lazily on selection.
        4. **Simulation/eval**: leaf value ← net value (no random rollout).
        5. **Backup**: add z to every node along the path; flip sign at
           opponent moves so each node always sees value from *its own
           player-to-move's* perspective.

The visit-distribution at the root over **legal actions in s_root** is
the policy target for distillation.

PUCT formula
------------
    a* = argmax_a   Q(s,a) + c_puct · P(s,a) · sqrt(N(s)) / (1 + N(s,a))

where Q is averaged value (root_seat's perspective remapped to whose
turn it is), P is the network prior, N(s) is parent visits, N(s,a) is
edge visits.

Notes
-----
* Value is in [-1, +1] from the perspective of *the seat about to act*.
  At backup we flip when the team changes to keep this consistent.
* When the simulation reaches a terminal (round_complete), the leaf
  value is computed deterministically from the floor scores.

Compactness
-----------
Tree is a dict ``nodes[key] -> Node``.  Keys uniquely identify a state
within the SO-IS sense from root_seat's perspective:
    key = (
        turn_num,
        table_pos,
        first_of_turn,
        played_mask,             # 40-bit
        last_table_cards_packed, # 32-bit
    )
This collides across different *opponent hands* — exactly what SO-ISMCTS
wants: cards played and table position fully define what root_seat
observes.

Action node
-----------
Each node stores arrays:
    P[N_ACTIONS]   prior probabilities
    N[N_ACTIONS]   visit counts
    W[N_ACTIONS]   accumulated value sum
    legal_seen[N_ACTIONS]  bool, whether this action ever appeared legal
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import torch

from .belief         import BeliefState, determinize, state_from_determinization
from .fast_engine    import (
    NUM_CARDS, NUM_SEATS, HAND_SIZE,
    CARD_TO_SUIT, CARD_POINTS3, SEAT_TO_TEAM,
    DECL_NONE, DECL_BUSSO, DECL_STRISCIO, DECL_VOLO,
    GameState, copy_state, apply_card, seat_to_play,
    legal_card_actions, valid_declarations, lead_suit, ROUND_TOTAL_POINTS3,
)
from .az_features    import (
    STATE_DIM, N_ACTIONS, action_index, split_action,
    legal_action_mask, encode_state,
)


# ── Node ───────────────────────────────────────────────────────────────────────

@dataclass
class _Node:
    P:          np.ndarray   # float32 [N_ACTIONS] — prior probabilities (post-mask)
    N:          np.ndarray   # int32   [N_ACTIONS] — visit counts
    W:          np.ndarray   # float64 [N_ACTIONS] — accumulated value sum
    legal_seen: np.ndarray   # bool    [N_ACTIONS] — actions seen legal in any det
    visits:    int = 0       # total visits to this node


def _state_key(s: GameState) -> Tuple:
    """Information-set key: what the root seat observes."""
    # Pack table_cards (4 × int8 in [-1,39]): shift +1 to [0,40], pack as 6-bit each.
    tc = s.table_cards
    packed = (int(tc[0]) + 1) | ((int(tc[1]) + 1) << 6) | ((int(tc[2]) + 1) << 12) | ((int(tc[3]) + 1) << 18)
    return (
        int(s.turn_num),
        int(s.table_pos),
        int(s.first_of_turn),
        int(s.played_mask),
        packed,
        int(s.last_declaration),
        int(s.briscola),
        int(s.briscola_selector),
        bool(s.maraffa_forced),
    )


# ── ISMCTS ─────────────────────────────────────────────────────────────────────

class ISMCTS:
    """Single-observer ISMCTS with batched neural-net leaf evaluation.

    Designed for *self-play search* where the agent runs ISMCTS once per
    decision, then samples / argmaxes over the resulting visit
    distribution.

    Parameters
    ----------
    eval_fn
        Callable ``(state_feats[B, STATE_DIM], legal_mask[B, N_ACTIONS])
        → (logits[B, N_ACTIONS], value[B])``.  Pure function of features
        and mask; no globals.  Returned tensors should be on CPU.
    c_puct
        Exploration constant.
    n_simulations
        Tree expansions per search call.
    n_determinizations
        How often to redraw opponent hands within one search.  Cards are
        re-sampled every ``n_simulations / n_determinizations`` sims.
    dirichlet_alpha, dirichlet_eps
        Root-prior noise parameters.  Set ``dirichlet_eps=0`` to disable
        (used at evaluation time).
    """

    def __init__(
        self,
        eval_fn:            Callable,
        c_puct:             float = 1.5,
        n_simulations:      int   = 64,
        n_determinizations: int   = 16,
        dirichlet_alpha:    float = 0.3,
        dirichlet_eps:      float = 0.0,
        seed:               Optional[int] = None,
    ):
        self.eval_fn            = eval_fn
        self.c_puct             = c_puct
        self.n_sims             = n_simulations
        self.n_determinizations = max(1, n_determinizations)
        self.dirichlet_alpha    = dirichlet_alpha
        self.dirichlet_eps      = dirichlet_eps
        self.rng                = np.random.default_rng(seed)

    # ── Public API ────────────────────────────────────────────────────────────

    def search(
        self,
        root_state: GameState,
        root_seat:  int,
        belief:     Optional[BeliefState] = None,
    ) -> Tuple[np.ndarray, float]:
        """Return ``(visit_distribution[N_ACTIONS], root_value)``.

        ``visit_distribution`` is L1-normalised over legal root actions.
        Use it as a policy target (cross-entropy with pre-softmax logits
        masked to legal actions) or sample from it for action selection.
        ``root_value`` is the average root value from root_seat's POV.
        """
        if belief is None:
            belief = BeliefState.from_state(root_state, root_seat)

        nodes: Dict[Tuple, _Node] = {}
        root_key  = _state_key(root_state)
        sims_per_det = max(1, self.n_sims // self.n_determinizations)

        for det_i in range(self.n_determinizations):
            try:
                sampled = determinize(belief, self.rng)
            except Exception:
                continue
            for _ in range(sims_per_det):
                det_state = state_from_determinization(root_state, sampled, root_seat)
                self._simulate(det_state, root_seat, nodes, is_root=True, root_key=root_key)

        # Build visit distribution from root node.
        if root_key not in nodes:
            # No simulations completed — return a uniform legal distribution.
            mask = legal_action_mask(root_state, seat_to_play(root_state))
            dist = mask.astype(np.float32)
            dist = dist / dist.sum() if dist.sum() > 0 else dist
            return dist, 0.0

        root = nodes[root_key]
        N    = root.N.astype(np.float64)
        if N.sum() == 0:
            mask = legal_action_mask(root_state, seat_to_play(root_state))
            dist = mask.astype(np.float32)
            dist = dist / dist.sum() if dist.sum() > 0 else dist
            return dist, 0.0
        dist = (N / N.sum()).astype(np.float32)

        # Average value at root.
        total_W = float(root.W.sum())
        total_N = float(N.sum())
        root_value = total_W / total_N if total_N > 0 else 0.0

        return dist, root_value

    # ── Inner ─────────────────────────────────────────────────────────────────

    def _simulate(
        self,
        state:    GameState,
        root_seat: int,
        nodes:    Dict[Tuple, _Node],
        is_root:  bool,
        root_key: Optional[Tuple] = None,
    ) -> float:
        """One simulation. Returns leaf-value from root_seat's POV."""
        path: List[Tuple[Tuple, int, int]] = []   # (node_key, action_idx, mover_seat)
        cur = state

        while not cur.round_complete:
            mover = seat_to_play(cur)
            key   = _state_key(cur) if not (is_root and not path) else root_key
            mask  = legal_action_mask(cur, mover)

            if key not in nodes:
                # Expansion + leaf eval.
                feats = encode_state(cur, mover).astype(np.float32)
                logits_t, value_t = self.eval_fn(
                    feats[None], mask[None].astype(bool)
                )
                logits = logits_t[0].numpy() if hasattr(logits_t, "numpy") else np.asarray(logits_t[0])
                v_leaf = float(value_t[0].item() if hasattr(value_t[0], "item") else value_t[0])

                # Softmax → priors. Mask already applied by eval_fn (illegal = -inf).
                logits = logits - logits.max()
                p = np.exp(logits)
                p = p * mask
                if p.sum() <= 0:
                    p = mask.astype(np.float32) / max(1, mask.sum())
                else:
                    p = p / p.sum()

                # Add Dirichlet noise at root for exploration during self-play.
                if is_root and not path and self.dirichlet_eps > 0:
                    legal_idx = np.flatnonzero(mask)
                    if legal_idx.size > 1:
                        noise = self.rng.dirichlet([self.dirichlet_alpha] * legal_idx.size)
                        p[legal_idx] = (1 - self.dirichlet_eps) * p[legal_idx] + self.dirichlet_eps * noise

                nodes[key] = _Node(
                    P          = p.astype(np.float32),
                    N          = np.zeros(N_ACTIONS, dtype=np.int32),
                    W          = np.zeros(N_ACTIONS, dtype=np.float64),
                    legal_seen = mask.copy(),
                )

                # Backup using NN value (from mover's perspective).
                self._backup(path, v_leaf, mover, root_seat, nodes)
                return self._terminal_value(state, root_seat) if state.round_complete else v_leaf

            # Existing node — PUCT selection over actions legal in *this* determinization.
            node = nodes[key]
            node.legal_seen |= mask    # union: this action seen legal at least once
            action = self._select_action(node, mask)
            if action < 0:
                # No legal action (shouldn't happen) — abort sim.
                break

            path.append((key, action, mover))
            card, decl = split_action(action)
            apply_card(cur, mover, card, decl)
            is_root = False

        # Reached terminal (round complete).
        v_term = self._terminal_value(cur, root_seat)
        self._backup(path, v_term, root_seat, root_seat, nodes)
        return v_term

    def _select_action(self, node: _Node, legal_mask: np.ndarray) -> int:
        """PUCT over actions legal in current determinization."""
        legal_idx = np.flatnonzero(legal_mask)
        if legal_idx.size == 0:
            return -1
        N_total = max(1, int(node.N[legal_idx].sum()))
        sqrt_n  = math.sqrt(N_total)

        N_a = node.N[legal_idx].astype(np.float64)
        W_a = node.W[legal_idx]
        P_a = node.P[legal_idx]
        Q_a = np.where(N_a > 0, W_a / np.maximum(N_a, 1), 0.0)
        U_a = self.c_puct * P_a * sqrt_n / (1.0 + N_a)
        scores = Q_a + U_a
        best_local = int(np.argmax(scores))
        return int(legal_idx[best_local])

    def _backup(
        self,
        path:      List[Tuple[Tuple, int, int]],
        v_leaf:    float,
        leaf_mover: int,
        root_seat: int,
        nodes:     Dict[Tuple, _Node],
    ) -> None:
        """Backup leaf_value along path.

        Q at each node is stored *from the perspective of the seat to
        move at that node*.  So we flip the sign whenever the team
        changes between the leaf-mover and the path-mover.
        """
        for key, action, mover in path:
            node = nodes[key]
            same_team = (int(SEAT_TO_TEAM[mover]) == int(SEAT_TO_TEAM[leaf_mover]))
            v = v_leaf if same_team else -v_leaf
            node.N[action] += 1
            node.W[action] += v
            node.visits    += 1

    def _terminal_value(self, state: GameState, root_seat: int) -> float:
        """Round-end value in [-1, +1] from ``root_seat``'s perspective.

        Map raw (root_team_thirds - opp_thirds) ∈ [-35, +35] to [-1, 1].
        """
        my_team  = int(SEAT_TO_TEAM[root_seat])
        opp_team = 1 - my_team
        diff3    = int(state.raw_scores[my_team] - state.raw_scores[opp_team])
        return max(-1.0, min(1.0, diff3 / float(ROUND_TOTAL_POINTS3)))


# ── Convenience wrapper for the network ────────────────────────────────────────

def make_torch_eval_fn(model, device: str = "cpu") -> Callable:
    """Build a callable suitable for ISMCTS.eval_fn from a torch policy.

    Returns a function ``(feats[B,F], mask[B,N]) -> (logits[B,N], value[B])``
    on CPU numpy.  Detaches gradients, runs in inference mode.
    """
    model.eval()

    @torch.inference_mode()
    def _eval(feats_np: np.ndarray, mask_np: np.ndarray):
        feats = torch.as_tensor(feats_np, dtype=torch.float32, device=device)
        mask  = torch.as_tensor(mask_np,  dtype=torch.bool,    device=device)
        logits, value = model(feats, mask)
        return logits.detach().cpu(), value.detach().cpu()

    return _eval
