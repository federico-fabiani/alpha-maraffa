"""PPO training loop for Maraffa RL.

Entry point: ``train(src_model_path, model_out, iteration, ...)``

Algorithm
---------
1.  Collect ``N_EPISODES_PER_ITER`` games via ``rl_env.run_episode``.
    ``HEURISTIC_OPPONENT_FRAC`` of games pit the policy against a
    HeuristicAgent; the rest are pure self-play.
2.  Compute per-episode GAE advantages + discounted returns.
3.  Run ``PPO_EPOCHS`` passes of mini-batch PPO with clipped policy loss,
    clipped value loss, entropy bonus, and gradient norm clipping.
4.  Save the updated checkpoint.

Rollout collection is parallelised across ``N_WORKERS`` processes via
``multiprocessing.Pool`` with "spawn" context.  Workers receive only CPU
weights (no CUDA tensors) and run ``run_episode`` with ``device="cpu"``.
The main process aggregates, computes advantages, and runs all gradient
steps (on GPU when DEVICE="cuda").

Variable-length action sets
---------------------------
Each decision has a different ``n_cands``.  During the PPO update we group
decisions into mini-batches, pad to ``max(n_cands)`` in each batch, and
supply a boolean mask so the policy head ignores padded slots.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import random
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.amp import GradScaler

from aimaraffa.agents.heuristic_agent import HeuristicAgent
from aimaraffa.agents.ml_agent import _COL_NAMES

from . import config_rl as cfg
from .rl_env import DecisionRecord, run_episode
from .rl_model import MarafonePolicy

logger = logging.getLogger(__name__)

N_FEATURES = len(_COL_NAMES)


# ── Worker process ─────────────────────────────────────────────────────────────

def _worker_collect(args: tuple) -> List[Tuple[List[DecisionRecord], int]]:
    """Run N episodes and return ``[(records, episode_len), ...]``.

    Runs entirely on CPU — no CUDA in worker processes.
    """
    state_dict, n_features, hidden_dim, n_layers, n_episodes, use_heuristic, seed = args

    policy = MarafonePolicy(n_features, hidden_dim, n_layers)
    policy.load_state_dict(state_dict)
    policy.eval()

    rng      = random.Random(seed)
    opponent = HeuristicAgent() if use_heuristic else None
    results  = []
    for _ in range(n_episodes):
        ep  = run_episode(policy, device="cpu", opponent=opponent, rng=rng)
        results.append((ep, len(ep)))
    return results


# ── GAE computation ────────────────────────────────────────────────────────────

def _compute_gae(
    rewards: List[float],
    values:  List[float],
    gamma:   float,
    lam:     float,
) -> Tuple[List[float], List[float]]:
    """GAE for one episode.  Returns ``(advantages, returns)``."""
    n        = len(rewards)
    gae      = 0.0
    adv      = [0.0] * n
    ret      = [0.0] * n
    next_val = 0.0  # bootstrapped value past end of episode = 0

    for t in reversed(range(n)):
        delta  = rewards[t] + gamma * next_val - values[t]
        gae    = delta + gamma * lam * gae
        adv[t] = gae
        ret[t] = gae + values[t]
        next_val = values[t]

    return adv, ret


# ── PPO mini-batch update ──────────────────────────────────────────────────────

def _ppo_update(
    policy:     MarafonePolicy,
    optimizer:  optim.Optimizer,
    records:    List[DecisionRecord],
    advantages: np.ndarray,
    returns:    np.ndarray,
    device:     str,
    scaler:     Optional[GradScaler] = None,
) -> dict:
    """``PPO_EPOCHS`` passes of clipped PPO over the collected batch.

    Returns a dict of averaged scalar metrics.
    """
    use_amp = (
        scaler is not None
        and device.startswith("cuda")
        and cfg.USE_AMP
    )
    amp_dtype = torch.bfloat16 if cfg.AMP_DTYPE == "bfloat16" else torch.float16
    autocast_ctx = (
        torch.amp.autocast(device_type="cuda", dtype=amp_dtype)
        if use_amp else torch.amp.autocast(device_type="cpu", enabled=False)
    )

    n       = len(records)
    old_lps = np.array([r.log_prob for r in records], dtype=np.float32)

    adv_mean = advantages.mean()
    adv_std  = max(float(advantages.std()), 1e-8)
    advantages = (advantages - adv_mean) / adv_std

    metrics: dict = {k: [] for k in ("policy_loss", "value_loss", "entropy", "total_loss", "kl")}

    # Pre-build pinned CPU tensors for fast H2D transfer when using CUDA.
    pin = device.startswith("cuda")

    policy.train()
    for _epoch in range(cfg.PPO_EPOCHS):
        idx_perm = np.random.permutation(n)

        for start in range(0, n, cfg.MINI_BATCH_SIZE):
            mb_idx = idx_perm[start:start + cfg.MINI_BATCH_SIZE]
            if len(mb_idx) == 0:
                continue

            mb_records = [records[i] for i in mb_idx]

            # Build CPU tensors; pin_memory lets the CUDA DMA engine overlap H2D.
            mb_adv_cpu    = torch.tensor(advantages[mb_idx], dtype=torch.float32)
            mb_ret_cpu    = torch.tensor(returns[mb_idx],    dtype=torch.float32)
            mb_old_lp_cpu = torch.tensor(old_lps[mb_idx],   dtype=torch.float32)
            mb_act_cpu    = torch.tensor([r.action for r in mb_records], dtype=torch.long)

            max_k = max(r.n_cands for r in mb_records)
            B, F  = len(mb_records), N_FEATURES

            padded_cpu = torch.zeros(B, max_k, F, dtype=torch.float32)
            mask_cpu   = torch.zeros(B, max_k,    dtype=torch.bool)

            for bi, rec in enumerate(mb_records):
                k = rec.n_cands
                padded_cpu[bi, :k, :] = torch.from_numpy(rec.feats[:k]).float()
                mask_cpu[bi, :k]      = True

            if pin:
                padded_cpu = padded_cpu.pin_memory()
                mask_cpu   = mask_cpu.pin_memory()
                mb_adv_cpu = mb_adv_cpu.pin_memory()
                mb_ret_cpu = mb_ret_cpu.pin_memory()
                mb_old_lp_cpu = mb_old_lp_cpu.pin_memory()
                mb_act_cpu    = mb_act_cpu.pin_memory()

            padded    = padded_cpu.to(device, non_blocking=True)
            mask      = mask_cpu.to(device, non_blocking=True)
            mb_adv    = mb_adv_cpu.to(device, non_blocking=True)
            mb_ret    = mb_ret_cpu.to(device, non_blocking=True)
            mb_old_lp = mb_old_lp_cpu.to(device, non_blocking=True)
            mb_actions = mb_act_cpu.to(device, non_blocking=True)

            # Clamp actions to valid range (briscola actions are 0–3, always valid).
            mb_actions = mb_actions.clamp(max=max_k - 1)

            with autocast_ctx:
                log_prob, value, entropy = policy.evaluate_actions(padded, mb_actions, mask)

                ratio  = torch.exp(log_prob - mb_old_lp)
                surr1  = ratio * mb_adv
                surr2  = ratio.clamp(1.0 - cfg.CLIP_EPS, 1.0 + cfg.CLIP_EPS) * mb_adv
                p_loss = -torch.min(surr1, surr2).mean()
                v_loss = 0.5 * (value - mb_ret).pow(2).mean()
                e_loss = -entropy.mean()
                loss   = p_loss + cfg.VALUE_COEF * v_loss + cfg.ENTROPY_COEF * e_loss

            optimizer.zero_grad(set_to_none=True)
            if use_amp:
                scaler.scale(loss).backward()
                scaler.unscale_(optimizer)
                nn.utils.clip_grad_norm_(policy.parameters(), cfg.MAX_GRAD_NORM)
                scaler.step(optimizer)
                scaler.update()
            else:
                loss.backward()
                nn.utils.clip_grad_norm_(policy.parameters(), cfg.MAX_GRAD_NORM)
                optimizer.step()

            with torch.no_grad():
                kl = (mb_old_lp - log_prob).mean().item()

            metrics["policy_loss"].append(p_loss.item())
            metrics["value_loss"].append(v_loss.item())
            metrics["entropy"].append(-e_loss.item())
            metrics["total_loss"].append(loss.item())
            metrics["kl"].append(kl)

    policy.eval()
    return {k: float(np.mean(v)) if v else 0.0 for k, v in metrics.items()}


# ── Main training function ─────────────────────────────────────────────────────

def train(
    src_model_path: Optional[Path],
    model_out:      Path,
    iteration:      int,
    *,
    device:              str   = cfg.DEVICE,
    n_episodes_per_iter: int   = cfg.N_EPISODES_PER_ITER,
    n_workers:           int   = cfg.N_WORKERS,
    heuristic_frac:      float = cfg.HEURISTIC_OPPONENT_FRAC,
    warmup_iters:        int   = cfg.WARMUP_ITERS,
) -> None:
    """Train one PPO iteration and save the checkpoint.

    Args:
        src_model_path: Previous ``.pt`` checkpoint (warm-start) or None
                        (fresh policy from scratch).
        model_out:      Destination path for the updated checkpoint.
        iteration:      1-based index used for learning-rate warmup.
    """
    # ── CUDA/precision setup ───────────────────────────────────────────────────
    is_cuda = device.startswith("cuda")
    if is_cuda and cfg.USE_TF32:
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32        = True
        logger.info("TF32 enabled.")
    if is_cuda:
        torch.backends.cudnn.benchmark = True  # auto-tune conv kernels

    # ── Load / initialise policy ───────────────────────────────────────────────
    if src_model_path is not None and src_model_path.exists():
        logger.info("Warm-starting from: %s", src_model_path)
        # Don't compile for training — compile is for eval/inference only.
        policy = MarafonePolicy.load(src_model_path, device=device, compile=False)
    else:
        logger.info("Fresh policy (n_features=%d, hidden=%d, layers=%d)",
                    N_FEATURES, cfg.HIDDEN_DIM, cfg.N_LAYERS)
        policy = MarafonePolicy(N_FEATURES, cfg.HIDDEN_DIM, cfg.N_LAYERS).to(device)

    if iteration <= warmup_iters:
        warmup_factor = min(1.0, 0.1 + 0.9 * (iteration - 1) / max(1, warmup_iters - 1))
        lr = cfg.LEARNING_RATE * warmup_factor
        logger.info("Iteration %d  lr=%.2e  (warmup_factor=%.2f, fused_adam=%s)",
                    iteration, lr, warmup_factor, is_cuda)
    else:
        decay_steps = iteration - warmup_iters
        lr = max(cfg.LR_MIN, cfg.LEARNING_RATE * (cfg.LR_DECAY_GAMMA ** decay_steps))
        logger.info("Iteration %d  lr=%.2e  (decay_step=%d, fused_adam=%s)",
                    iteration, lr, decay_steps, is_cuda)
    optimizer = optim.Adam(policy.parameters(), lr=lr, eps=1e-5, fused=is_cuda)

    # GradScaler for AMP.  BF16 doesn't need scaling but FP16 does; we create
    # it unconditionally and let _ppo_update decide whether to use it.
    scaler = GradScaler("cuda", enabled=(is_cuda and cfg.USE_AMP and cfg.AMP_DTYPE == "float16"))

    # ── Build worker task list ─────────────────────────────────────────────────
    n_heuristic = max(1, int(n_episodes_per_iter * heuristic_frac))
    n_selfplay  = n_episodes_per_iter - n_heuristic
    logger.info("Collecting %d episodes (%d self-play + %d vs heuristic) on %d workers …",
                n_episodes_per_iter, n_selfplay, n_heuristic, n_workers)

    # Detach weights from GPU before forking.
    cpu_state = {k: v.detach().cpu() for k, v in policy.state_dict().items()}
    base_seed = random.randint(0, 2 ** 31)

    tasks: List[tuple] = []
    for wi in range(n_workers):
        n_sp = n_selfplay   // n_workers + (1 if wi < n_selfplay   % n_workers else 0)
        n_h  = n_heuristic  // n_workers + (1 if wi < n_heuristic  % n_workers else 0)
        if n_sp > 0:
            tasks.append((cpu_state, N_FEATURES, cfg.HIDDEN_DIM, cfg.N_LAYERS,
                          n_sp, False, base_seed + wi))
        if n_h > 0:
            tasks.append((cpu_state, N_FEATURES, cfg.HIDDEN_DIM, cfg.N_LAYERS,
                          n_h, True, base_seed + n_workers + wi))

    # ── Collect rollouts ───────────────────────────────────────────────────────
    all_records:   List[DecisionRecord] = []
    episode_lens:  List[int]            = []

    if n_workers > 1:
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=min(n_workers, len(tasks))) as pool:
            raw_batches = pool.map(_worker_collect, tasks)
        for batch in raw_batches:
            for ep_records, ep_len in batch:
                all_records.extend(ep_records)
                episode_lens.append(ep_len)
    else:
        for task in tasks:
            for ep_records, ep_len in _worker_collect(task):
                all_records.extend(ep_records)
                episode_lens.append(ep_len)

    n_decisions = len(all_records)
    logger.info("Collected %d decisions across %d episodes.", n_decisions, len(episode_lens))
    if n_decisions == 0:
        raise RuntimeError("No decisions collected — episode runner returned empty.")

    # ── GAE per episode ────────────────────────────────────────────────────────
    all_advantages: List[float] = []
    all_returns:    List[float] = []
    cursor = 0
    for ep_len in episode_lens:
        if ep_len == 0:
            cursor += ep_len
            continue
        ep_recs = all_records[cursor:cursor + ep_len]
        rewards  = [r.reward for r in ep_recs]
        values   = [r.value  for r in ep_recs]
        adv, ret = _compute_gae(rewards, values, cfg.GAMMA, cfg.GAE_LAMBDA)
        all_advantages.extend(adv)
        all_returns.extend(ret)
        cursor += ep_len

    advantages_np = np.array(all_advantages, dtype=np.float32)
    returns_np    = np.array(all_returns,    dtype=np.float32)

    # Normalize returns so value head targets ~N(0,1).
    # Without this, value loss stays high (10+) and advantage estimates are noisy.
    ret_mean = returns_np.mean()
    ret_std  = max(float(returns_np.std()), 1e-8)
    returns_np = (returns_np - ret_mean) / ret_std

    # ── PPO update ─────────────────────────────────────────────────────────────
    metrics = _ppo_update(policy, optimizer, all_records, advantages_np, returns_np, device, scaler)
    logger.info(
        "PPO — policy_loss=%.4f  value_loss=%.4f  entropy=%.4f  kl=%.4f",
        metrics["policy_loss"], metrics["value_loss"],
        metrics["entropy"],     metrics["kl"],
    )

    # ── Save ───────────────────────────────────────────────────────────────────
    # torch.compile wraps the module; unwrap to access .save().
    raw_policy = getattr(policy, "_orig_mod", policy)
    raw_policy.save(model_out)
    logger.info("Saved: %s", model_out)
