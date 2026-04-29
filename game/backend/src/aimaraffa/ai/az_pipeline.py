"""End-to-end iteration: self-play → distillation → tournament → promotion.

Run via:
    python -m aimaraffa.ai.az_pipeline --iters 5
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import config_az as cfg
from .az_train       import ReplayBuffer, train_iteration
from .az_versions    import (
    list_versions, latest_version, next_version_dir, promote,
)
from .az_tournament  import az_tournament
from .az_model       import AZPolicyValue


logger = logging.getLogger(__name__)


# Persistent in-memory replay across iterations within a single batch invocation.
_REPLAY = ReplayBuffer(max_iters=cfg.REPLAY_BUFFER_ITERS)


def run_one_iteration(
    *,
    n_rounds:       int = cfg.N_ROUNDS_PER_ITER,
    n_workers:      int = cfg.N_WORKERS,
    heuristic_team: Optional[int] = None,
    tourney_games:  int = cfg.TOURNEY_GAMES,
    tourney_seed:   int = cfg.TOURNEY_SEED,
    device:         str = cfg.DEVICE,
) -> dict:
    """Run a single iteration: train new version, evaluate, promote if better."""
    src_num, src_path = latest_version()
    src_label = f"az_v{src_num}" if src_num > 0 else "scratch"
    dst_name, dst_dir = next_version_dir()
    model_out = dst_dir / cfg.AZ_MODEL_FILENAME

    logger.info("=" * 60)
    logger.info(" Source         : %s", src_label)
    logger.info(" Target         : %s", dst_name)
    logger.info(" Self-play      : %d rounds × %d sims × %d dets",
                n_rounds, cfg.SP_N_SIMULATIONS, cfg.SP_N_DETERMINIZATIONS)
    logger.info(" Heuristic team : %s", heuristic_team)
    logger.info(" Replay         : last %d iters", cfg.REPLAY_BUFFER_ITERS)
    logger.info(" Eval (round)   : %d × %d sims",
                cfg.EVAL_N_SIMULATIONS, cfg.EVAL_N_DETERMINIZATIONS)
    logger.info("=" * 60)

    # ── Train ─────────────────────────────────────────────────────────────────
    train_metrics = train_iteration(
        src_model_path = src_path,
        model_out      = model_out,
        iteration      = src_num + 1,
        replay         = _REPLAY,
        n_rounds       = n_rounds,
        n_workers      = n_workers,
        heuristic_team = heuristic_team,
        device         = device,
    )

    # ── Export ONNX for production inference ─────────────────────────────────
    try:
        cpu_model = AZPolicyValue.load(model_out, device="cpu")
        cpu_model.export_onnx(dst_dir / cfg.AZ_ONNX_FILENAME)
    except Exception as e:
        logger.warning("ONNX export failed: %s", e)

    # ── Tournament vs heuristic ──────────────────────────────────────────────
    logger.info("Tournament %s vs heuristic …", dst_name)
    res = az_tournament(
        model_a = model_out,
        model_b = "heuristic",
        games   = tourney_games,
        seed    = tourney_seed,
    )
    logger.info(
        "  WR=%.1f%%  CI=[%.1f%%, %.1f%%]  margin=%+.2f  decisive=%d/%d  dt=%.1fs",
        100 * res["win_rate_a"], 100 * res["ci95_lo"], 100 * res["ci95_hi"],
        res["avg_margin_a"], res["a_wins"] + res["b_wins"], res["games"],
        res["duration_sec"],
    )

    promoted = res["ci95_lo"] >= cfg.PROMOTE_MIN_CI_LOWER and res["win_rate_a"] > 0.5
    if promoted:
        promote(dst_name, dst_dir)

    return {
        "version":   dst_name,
        "promoted":  promoted,
        "tourney":   res,
        "train":     train_metrics,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--iters",          type=int, default=1)
    p.add_argument("--rounds",         type=int, default=cfg.N_ROUNDS_PER_ITER)
    p.add_argument("--workers",        type=int, default=cfg.N_WORKERS)
    p.add_argument("--heuristic-team", type=int, default=None,
                   help="1 or 2 → that team plays heuristic (curriculum mode); None = pure self-play")
    p.add_argument("--tourney-games",  type=int, default=cfg.TOURNEY_GAMES)
    p.add_argument("--device",         type=str, default=cfg.DEVICE)
    p.add_argument("--log-level",      type=str, default="INFO")
    args = p.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    for i in range(args.iters):
        logger.info("Iteration %d / %d", i + 1, args.iters)
        run_one_iteration(
            n_rounds       = args.rounds,
            n_workers      = args.workers,
            heuristic_team = args.heuristic_team,
            tourney_games  = args.tourney_games,
            device         = args.device,
        )


if __name__ == "__main__":
    main()
