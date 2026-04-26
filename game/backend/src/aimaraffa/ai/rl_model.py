"""Actor-Critic policy network for Maraffa RL (PPO).

Architecture:
  - input_norm (LayerNorm on raw features)
  - input_proj: Linear(n_features → hidden_dim) + GELU
  - N_LAYERS-1 pre-norm residual blocks: h = h + GELU(linear(norm(h)))
  - policy_head: Linear(hidden_dim → 1) applied per-candidate → logits
  - value_head:  mean-pool of trunk outputs → Linear(hidden_dim → 1)

Pre-norm residuals give stable gradient flow through depth without
requiring careful init. Value head pools trunk outputs (learned
representations) which outperforms pooling raw features.

Input for every decision: float32 [n_candidates, n_features] where each row
is one (card, declaration) candidate, encoded via _build_base_row +
_expand_candidates — identical to XGBoost inference.
NaN entries (absent categoricals) are zeroed before processing.

Saving / loading:
  torch.save({"model_state": policy.state_dict(),
               "n_features":  policy.n_features,
               "hidden_dim":  policy.hidden_dim,
               "n_layers":    policy.n_layers}, path)

  policy = MarafonePolicy.load(path, device)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    from . import config_rl as _cfg
    if _cfg.USE_TF32:
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
except Exception:
    pass


class MarafonePolicy(nn.Module):
    """Shared-parameter actor-critic for Maraffa self-play."""

    def __init__(self, n_features: int, hidden_dim: int = 512, n_layers: int = 4):
        super().__init__()
        self.n_features = n_features
        self.hidden_dim = hidden_dim
        self.n_layers   = n_layers

        # Input normalisation — applied once, shared by both heads.
        self.input_norm = nn.LayerNorm(n_features)

        # First layer: project to hidden_dim.
        self.input_proj = nn.Linear(n_features, hidden_dim)

        # Pre-norm residual blocks: each is LayerNorm → Linear → GELU, added
        # to the skip path.  Pre-norm is more stable than post-norm for depth.
        self.res_norms   = nn.ModuleList([nn.LayerNorm(hidden_dim) for _ in range(n_layers - 1)])
        self.res_linears = nn.ModuleList([nn.Linear(hidden_dim, hidden_dim) for _ in range(n_layers - 1)])

        # Policy head: scalar logit per candidate.
        self.policy_head = nn.Linear(hidden_dim, 1)

        # Value head: applied to mean-pooled trunk outputs.
        self.value_head = nn.Linear(hidden_dim, 1)

        self._init_weights()

    def _init_weights(self) -> None:
        for m in self.modules():
            if isinstance(m, nn.Linear):
                gain = 0.01 if m is self.policy_head else 1.0
                nn.init.orthogonal_(m.weight, gain=gain)
                nn.init.zeros_(m.bias)

    # ── Core forward ───────────────────────────────────────────────────────────

    def forward(
        self,
        candidates: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Evaluate a batch of candidate sets.

        Args:
            candidates: ``[B, K, F]`` or ``[K, F]`` float32 — candidate features.
                        NaN cells (missing categoricals) are replaced with 0.
            mask:       ``[B, K]`` bool, True = valid candidate (for padded batches).
                        When None every position is treated as valid.

        Returns:
            logits: ``[B, K]`` or ``[K]`` — raw policy scores (pre-softmax).
            value:  ``[B]`` or scalar — state-value estimate V(s).
        """
        x = candidates.nan_to_num(0.0)
        x = self.input_norm(x)                                    # [..., K, F]

        # Trunk: project then N-1 pre-norm residual blocks.
        h = F.gelu(self.input_proj(x))                            # [..., K, H]
        for norm, linear in zip(self.res_norms, self.res_linears):
            h = h + F.gelu(linear(norm(h)))                       # residual

        # Policy: per-candidate logit.
        logits = self.policy_head(h).squeeze(-1)                  # [..., K]
        if mask is not None:
            logits = logits.masked_fill(~mask, -1e9)

        # Value: mean-pool trunk outputs over valid candidates → scalar.
        if mask is not None:
            h_valid  = h * mask.unsqueeze(-1).float()
            counts   = mask.float().sum(-1, keepdim=True).clamp(min=1.0)
            h_pooled = h_valid.sum(-2) / counts                   # [B, H]
        else:
            h_pooled = h.mean(-2) if h.dim() == 3 else h.mean(0) # [B, H] or [H]
        value = self.value_head(h_pooled).squeeze(-1)             # [B] or scalar

        return logits, value

    # ── Convenience wrappers ───────────────────────────────────────────────────

    @torch.no_grad()
    def act_greedy(self, candidates: torch.Tensor) -> int:
        """Argmax action selection for deterministic play (tournament / eval)."""
        logits, _ = self.forward(candidates)
        return int(logits.argmax().item())

    def act_sample(
        self, candidates: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Sample one action; return ``(action_idx, log_prob, value)``."""
        logits, value = self.forward(candidates)
        dist   = torch.distributions.Categorical(logits=logits)
        action = dist.sample()
        return action, dist.log_prob(action), value

    def evaluate_actions(
        self,
        candidates: torch.Tensor,
        actions:    torch.Tensor,
        mask:       Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Re-evaluate stored actions for the PPO loss.

        Returns ``(log_prob, value, entropy)`` — all differentiable.
        """
        logits, value = self.forward(candidates, mask)
        dist     = torch.distributions.Categorical(logits=logits)
        log_prob = dist.log_prob(actions)
        entropy  = dist.entropy()
        return log_prob, value, entropy

    # ── Serialisation ──────────────────────────────────────────────────────────

    def export_onnx(self, path: Path) -> None:
        """Export to ONNX for production inference (no torch at runtime).

        Input  "candidates": float32 [K, n_features]  — K is dynamic
        Output "logits":     float32 [K]
               "value":      float32 scalar
        """
        import logging
        self.eval()
        dummy = torch.zeros(4, self.n_features)
        torch.onnx.export(
            self,
            (dummy,),
            str(path),
            input_names  = ["candidates"],
            output_names = ["logits", "value"],
            dynamic_axes = {
                "candidates": {0: "n_candidates"},
                "logits":     {0: "n_candidates"},
            },
            opset_version = 17,
            dynamo        = False,
        )
        logging.getLogger(__name__).info("ONNX exported: %s", path)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "model_state": self.state_dict(),
            "n_features":  self.n_features,
            "hidden_dim":  self.hidden_dim,
            "n_layers":    self.n_layers,
        }, path)

    @classmethod
    def load(cls, path: Path, device: str = "cpu", compile: bool | None = None) -> "MarafonePolicy":
        ckpt   = torch.load(path, map_location=device, weights_only=False)
        policy = cls(
            n_features = ckpt["n_features"],
            hidden_dim = ckpt["hidden_dim"],
            n_layers   = ckpt["n_layers"],
        )
        policy.load_state_dict(ckpt["model_state"])
        policy.to(device)
        policy.eval()

        try:
            from . import config_rl as _cfg
            should_compile = _cfg.USE_COMPILE if compile is None else compile
        except Exception:
            should_compile = compile or False

        if should_compile and device != "cpu" and hasattr(torch, "compile"):
            policy = torch.compile(policy, mode="reduce-overhead")

        return policy
