"""Distillation training loop for AlphaZero-style Marafone.

Loss = CE(logits, pi_target) + α · MSE(value, z)

The cross-entropy is implemented as
    L_pol = - Σ_i  pi_target_i  · log_softmax(logits_i)
applied with masked logits (illegal positions set to -1e9 → softmax 0)
so legality is enforced at the loss level.

Public entry point
------------------
``train_iteration(src_model_path, model_out, replay, ...)`` runs
self-play data collection (parallel), appends to a rolling replay
window, and runs N epochs of the supervised distillation update.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.amp import GradScaler

from . import config_az as cfg
from .az_features  import STATE_DIM, N_ACTIONS
from .az_model     import AZPolicyValue
from .az_selfplay  import AZRecord, play_selfplay_round
from .ismcts       import make_torch_eval_fn

logger = logging.getLogger(__name__)


# ── Worker process: generate a chunk of self-play rounds ──────────────────────

def _worker_selfplay(args: tuple) -> List[Tuple[np.ndarray, np.ndarray, np.ndarray, float]]:
    """Run ``n_rounds`` self-play rounds and return flat tuples ready to stack.

    Workers run on CPU only (no CUDA in spawn workers).
    """
    (state_dict, hidden_dim, n_layers, state_dim, n_actions,
     n_rounds, sim_kwargs, heuristic_team, seed) = args

    model = AZPolicyValue(state_dim=state_dim, hidden_dim=hidden_dim,
                          n_layers=n_layers, n_actions=n_actions)
    model.load_state_dict(state_dict)
    model.eval()
    eval_fn = make_torch_eval_fn(model, device="cpu")

    rng_np = np.random.default_rng(seed)
    rng_py = random.Random(seed + 1)

    out: List[Tuple[np.ndarray, np.ndarray, np.ndarray, float]] = []
    for ri in range(n_rounds):
        sel = ri % 4
        recs = play_selfplay_round(
            eval_fn,
            briscola_selector       = sel,
            opponent_heuristic_team = heuristic_team,
            rng_np                  = rng_np,
            rng_py                  = rng_py,
            **sim_kwargs,
        )
        for r in recs:
            out.append((r.state_feats, r.legal_mask, r.pi_target, float(r.z)))
    return out


# ── Replay buffer (in-memory, list of tuples) ──────────────────────────────────

@dataclass
class ReplayBuffer:
    """Rolling window of last K iterations of self-play data."""
    iterations: List[List[Tuple[np.ndarray, np.ndarray, np.ndarray, float]]] = field(default_factory=list)
    max_iters:  int = cfg.REPLAY_BUFFER_ITERS

    def push(self, iter_data: List[Tuple[np.ndarray, np.ndarray, np.ndarray, float]]) -> None:
        self.iterations.append(iter_data)
        while len(self.iterations) > self.max_iters:
            self.iterations.pop(0)

    def all_records(self) -> List[Tuple[np.ndarray, np.ndarray, np.ndarray, float]]:
        out: List[Tuple[np.ndarray, np.ndarray, np.ndarray, float]] = []
        for it in self.iterations:
            out.extend(it)
        return out


# ── Training step ──────────────────────────────────────────────────────────────

def _train_epoch(
    model:     AZPolicyValue,
    optimizer: optim.Optimizer,
    data:      List[Tuple[np.ndarray, np.ndarray, np.ndarray, float]],
    device:    str,
    scaler:    Optional[GradScaler],
    epoch:     int,
) -> dict:
    """One pass over data with mini-batches.  Returns averaged metrics."""
    is_cuda = device.startswith("cuda")
    use_amp = scaler is not None and is_cuda and cfg.USE_AMP
    amp_dtype = torch.bfloat16 if cfg.AMP_DTYPE == "bfloat16" else torch.float16
    autocast_ctx = (
        torch.amp.autocast(device_type="cuda", dtype=amp_dtype)
        if use_amp else torch.amp.autocast(device_type="cpu", enabled=False)
    )

    n = len(data)
    perm = np.random.permutation(n)

    metrics = {"policy_loss": [], "value_loss": [], "total_loss": []}

    model.train()
    for start in range(0, n, cfg.MINI_BATCH_SIZE):
        mb_idx = perm[start:start + cfg.MINI_BATCH_SIZE]
        if len(mb_idx) == 0:
            continue
        mb = [data[i] for i in mb_idx]

        feats_np = np.stack([r[0] for r in mb], axis=0)             # [B, F]
        mask_np  = np.stack([r[1] for r in mb], axis=0)             # [B, A]
        pi_np    = np.stack([r[2] for r in mb], axis=0)             # [B, A]
        z_np     = np.array([r[3] for r in mb], dtype=np.float32)   # [B]

        feats = torch.from_numpy(feats_np).to(device, non_blocking=is_cuda)
        mask  = torch.from_numpy(mask_np).to(device, non_blocking=is_cuda)
        pi_t  = torch.from_numpy(pi_np).to(device, non_blocking=is_cuda)
        z_t   = torch.from_numpy(z_np).to(device, non_blocking=is_cuda)

        with autocast_ctx:
            logits, value = model(feats, mask)
            log_probs = F.log_softmax(logits, dim=-1)
            policy_loss = -(pi_t * log_probs).sum(dim=-1).mean()
            value_loss  = F.mse_loss(value, z_t)
            loss = policy_loss + cfg.VALUE_LOSS_COEF * value_loss

        optimizer.zero_grad(set_to_none=True)
        if use_amp and cfg.AMP_DTYPE == "float16":
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            nn.utils.clip_grad_norm_(model.parameters(), cfg.GRAD_CLIP_NORM)
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), cfg.GRAD_CLIP_NORM)
            optimizer.step()

        metrics["policy_loss"].append(float(policy_loss.detach()))
        metrics["value_loss"].append(float(value_loss.detach()))
        metrics["total_loss"].append(float(loss.detach()))

    return {k: float(np.mean(v)) if v else 0.0 for k, v in metrics.items()}


# ── Public entry point ─────────────────────────────────────────────────────────

def train_iteration(
    src_model_path:    Optional[Path],
    model_out:         Path,
    iteration:         int,
    replay:            ReplayBuffer,
    *,
    n_rounds:          int   = cfg.N_ROUNDS_PER_ITER,
    n_workers:         int   = cfg.N_WORKERS,
    heuristic_team:    Optional[int] = None,
    device:            str   = cfg.DEVICE,
) -> dict:
    """Run one full iteration: self-play → replay-append → train epochs → save.

    Returns metrics dict suitable for logging.
    """
    is_cuda = device.startswith("cuda")
    if is_cuda and cfg.USE_TF32:
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32        = True
        torch.backends.cudnn.benchmark         = True

    # ── Load / init model ─────────────────────────────────────────────────────
    if src_model_path is not None and src_model_path.exists():
        logger.info("Warm-starting from: %s", src_model_path)
        model = AZPolicyValue.load(src_model_path, device=device)
    else:
        logger.info("Fresh policy.")
        model = AZPolicyValue(
            hidden_dim = cfg.HIDDEN_DIM,
            n_layers   = cfg.N_LAYERS,
        ).to(device)

    optimizer = optim.AdamW(
        model.parameters(),
        lr           = cfg.LEARNING_RATE,
        weight_decay = cfg.WEIGHT_DECAY,
        eps          = 1e-5,
        fused        = is_cuda,
    )
    scaler = GradScaler("cuda", enabled=(is_cuda and cfg.USE_AMP and cfg.AMP_DTYPE == "float16"))

    # ── Self-play ─────────────────────────────────────────────────────────────
    cpu_state = {k: v.detach().cpu() for k, v in model.state_dict().items()}
    sim_kwargs = dict(
        n_simulations      = cfg.SP_N_SIMULATIONS,
        n_determinizations = cfg.SP_N_DETERMINIZATIONS,
        c_puct             = cfg.SP_C_PUCT,
        dirichlet_alpha    = cfg.SP_DIRICHLET_ALPHA,
        dirichlet_eps      = cfg.SP_DIRICHLET_EPS,
        temperature        = cfg.SP_TEMPERATURE,
        temp_falloff_turn  = cfg.SP_TEMP_FALLOFF_TURN,
    )

    base_seed = random.randint(0, 2**31 - 1)
    chunks: List[tuple] = []
    rounds_per_worker = max(1, n_rounds // n_workers)
    extra = n_rounds - rounds_per_worker * n_workers
    for wi in range(n_workers):
        n_w = rounds_per_worker + (1 if wi < extra else 0)
        if n_w == 0:
            continue
        chunks.append((
            cpu_state, cfg.HIDDEN_DIM, cfg.N_LAYERS,
            STATE_DIM, N_ACTIONS,
            n_w, sim_kwargs, heuristic_team, base_seed + wi,
        ))

    logger.info("Self-play: %d rounds across %d workers …", n_rounds, len(chunks))
    iter_data: List[Tuple[np.ndarray, np.ndarray, np.ndarray, float]] = []
    if n_workers > 1:
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=len(chunks)) as pool:
            for chunk_records in pool.imap_unordered(_worker_selfplay, chunks):
                iter_data.extend(chunk_records)
    else:
        for chunk in chunks:
            iter_data.extend(_worker_selfplay(chunk))

    logger.info("Collected %d decision records.", len(iter_data))
    replay.push(iter_data)
    train_data = replay.all_records()
    logger.info("Replay buffer: %d records across %d iterations.", len(train_data), len(replay.iterations))

    # ── Training epochs ───────────────────────────────────────────────────────
    metrics_all: dict = {}
    for ep in range(1, cfg.N_EPOCHS + 1):
        m = _train_epoch(model, optimizer, train_data, device, scaler, ep)
        logger.info("Epoch %d/%d  policy=%.4f  value=%.4f  total=%.4f",
                    ep, cfg.N_EPOCHS, m["policy_loss"], m["value_loss"], m["total_loss"])
        metrics_all = m

    # ── Save ──────────────────────────────────────────────────────────────────
    model.save(model_out)
    logger.info("Saved: %s", model_out)
    return {
        "n_records":      len(iter_data),
        "buffer_records": len(train_data),
        **metrics_all,
    }
