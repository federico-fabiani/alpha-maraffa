"""Compact policy/value network for Marafone AlphaZero-style training.

Architecture
------------
    state_features [STATE_DIM=284]
       ↓
    LayerNorm
       ↓
    Linear → GELU → LayerNorm   (hidden_dim)
       ↓
    [N_LAYERS-1] residual blocks: h = h + GELU(Linear(LayerNorm(h)))
       ↓
    s_emb [hidden_dim]
       ↓
    ┌──────────────┐         ┌──────────────────┐
    │ policy_head  │         │ value_head       │
    │ Linear→GELU  │         │ Linear→GELU      │
    │ Linear(N=160)│         │ Linear(1) tanh   │
    └──────────────┘         └──────────────────┘
       ↓                          ↓
    logits [160]                value ∈ [-1, 1]

Loss (distillation)
-------------------
    L = CE_masked(logits, π_target) + α * MSE(tanh(value), z)

where π_target is the visit-distribution from MCTS (only over legal
actions; mask logits of illegal actions to −∞ before softmax) and
``z`` is the round-end normalised margin in [-1, +1].

Total params ≈ 250k–400k depending on hidden_dim.  Trains in seconds on
GPU per epoch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from .az_features import STATE_DIM, N_ACTIONS


class AZPolicyValue(nn.Module):
    """Two-headed policy/value network for Marafone.

    Args
    ----
    state_dim : input feature dimension (default ``STATE_DIM``).
    hidden_dim : width of trunk.
    n_layers : number of residual blocks after the input projection.
    n_actions : output dimension of policy head (default 160).
    """

    def __init__(
        self,
        state_dim:  int = STATE_DIM,
        hidden_dim: int = 256,
        n_layers:   int = 4,
        n_actions:  int = N_ACTIONS,
    ):
        super().__init__()
        self.state_dim   = state_dim
        self.hidden_dim  = hidden_dim
        self.n_layers    = n_layers
        self.n_actions   = n_actions

        self.input_norm = nn.LayerNorm(state_dim)
        self.input_proj = nn.Linear(state_dim, hidden_dim)

        self.res_norms   = nn.ModuleList([nn.LayerNorm(hidden_dim) for _ in range(n_layers - 1)])
        self.res_linears = nn.ModuleList([nn.Linear(hidden_dim, hidden_dim) for _ in range(n_layers - 1)])

        self.policy_pre  = nn.Linear(hidden_dim, hidden_dim)
        self.policy_head = nn.Linear(hidden_dim, n_actions)

        self.value_pre   = nn.Linear(hidden_dim, hidden_dim)
        self.value_head  = nn.Linear(hidden_dim, 1)

        self._init_weights()

    def _init_weights(self) -> None:
        for m in self.modules():
            if isinstance(m, nn.Linear):
                if m is self.policy_head:
                    gain = 0.01
                elif m is self.value_head:
                    gain = 1.0
                else:
                    gain = 1.0
                nn.init.orthogonal_(m.weight, gain=gain)
                nn.init.zeros_(m.bias)

    def trunk(self, x: torch.Tensor) -> torch.Tensor:
        h = self.input_norm(x.nan_to_num(0.0))
        h = F.gelu(self.input_proj(h))
        for norm, lin in zip(self.res_norms, self.res_linears):
            h = h + F.gelu(lin(norm(h)))
        return h

    def forward(
        self,
        state_feats: torch.Tensor,
        legal_mask:  Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Return (logits[B, N_ACTIONS], value[B] ∈ [-1, 1]).

        When ``legal_mask`` is given (bool[B, N_ACTIONS]), illegal
        positions are filled with -1e9 so a softmax over the result is
        zero on them.
        """
        h = self.trunk(state_feats)

        ph = F.gelu(self.policy_pre(h))
        logits = self.policy_head(ph)
        if legal_mask is not None:
            logits = logits.masked_fill(~legal_mask, -1e9)

        vh = F.gelu(self.value_pre(h))
        value = torch.tanh(self.value_head(vh).squeeze(-1))

        return logits, value

    # ── Serialisation ──────────────────────────────────────────────────────────

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "model_state": self.state_dict(),
            "state_dim":   self.state_dim,
            "hidden_dim":  self.hidden_dim,
            "n_layers":    self.n_layers,
            "n_actions":   self.n_actions,
        }, path)

    @classmethod
    def load(cls, path: Path, device: str = "cpu") -> "AZPolicyValue":
        ckpt = torch.load(path, map_location=device, weights_only=False)
        m = cls(
            state_dim  = ckpt["state_dim"],
            hidden_dim = ckpt["hidden_dim"],
            n_layers   = ckpt["n_layers"],
            n_actions  = ckpt["n_actions"],
        )
        m.load_state_dict(ckpt["model_state"])
        m.to(device)
        m.eval()
        return m

    def export_onnx(self, path: Path) -> None:
        """Export to ONNX. Inputs: state_feats [B, STATE_DIM], legal_mask [B, N_ACTIONS]."""
        self.eval()
        dummy_s = torch.zeros(1, self.state_dim, dtype=torch.float32)
        dummy_m = torch.ones (1, self.n_actions, dtype=torch.bool)
        torch.onnx.export(
            self,
            (dummy_s, dummy_m),
            str(path),
            input_names  = ["state_feats", "legal_mask"],
            output_names = ["logits", "value"],
            dynamic_axes = {
                "state_feats": {0: "batch"},
                "legal_mask":  {0: "batch"},
                "logits":      {0: "batch"},
                "value":       {0: "batch"},
            },
            opset_version = 17,
            dynamo        = False,
        )
