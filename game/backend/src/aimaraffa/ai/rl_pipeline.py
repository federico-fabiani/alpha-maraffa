"""End-to-end RL training iteration: train → tournament → promote.

Mirrors pipeline.py but for the PPO-based RL stack.

Stages
------
[1/3] PPO training (rl_train.train)
[2/3] Tournament against champion (rl_tournament.rl_tournament)
[3/3] Promote if CI lower bound ≥ threshold
"""

from __future__ import annotations

import logging
import re

from . import config_rl as cfg
from .rl_train import train as rl_train
from .rl_tournament import rl_tournament
from .tournament import format_report
from .rl_versions import (
    latest_rl_version,
    next_rl_version_dir,
    rl_production_version,
    promoted_rl_versions,
    rl_promote,
)
from .config_rl import RL_PRODUCTION_MODEL_PATH, RL_PRODUCTION_ONNX_PATH, RL_ONNX_FILENAME, RL_PRODUCTION_POINTER

logger = logging.getLogger(__name__)


def run() -> None:
    """Execute one full RL pipeline iteration."""
    src_num, src_model = latest_rl_version()

    if src_model is None:
        src_label = "scratch (no prior checkpoint)"
    elif src_num == 0:
        src_label = "production (legacy)"
    else:
        src_label = f"rl_v{src_num}"

    dst_name, dst_dir = next_rl_version_dir()
    model_path  = dst_dir / cfg.RL_MODEL_FILENAME
    report_path = dst_dir / cfg.RL_REPORT_FILENAME

    # Iteration number for LR warmup = version index of the new model.
    # Extract integer from dst_name ("rl_v<N>").
    iteration = int(re.search(r"\d+", dst_name).group())

    logger.info("=" * 60)
    logger.info(" Source version : %s", src_label)
    logger.info(" Target version : %s  (%s)", dst_name, dst_dir)
    logger.info(" Episodes       : %d", cfg.N_EPISODES_PER_ITER)
    logger.info(" Heuristic frac : %.0f%%", cfg.HEURISTIC_OPPONENT_FRAC * 100)
    logger.info(" PPO epochs     : %d  |  mini-batch: %d", cfg.PPO_EPOCHS, cfg.MINI_BATCH_SIZE)
    logger.info(" Tournament     : %d games", cfg.TOURNEY_GAMES)
    logger.info(" Promote CI ≥   : %.3f", cfg.PROMOTE_MIN_CI_LOWER)
    logger.info("=" * 60)

    logger.info("[1/3] PPO training (%s → %s)", src_label, dst_name)
    rl_train(
        src_model_path = src_model,
        model_out      = model_path,
        iteration      = iteration,
        device         = cfg.DEVICE,
    )

    # Export ONNX for production inference (no torch dependency at runtime).
    from .rl_model import MarafonePolicy
    _policy = MarafonePolicy.load(model_path, device="cpu", compile=False)
    onnx_path = dst_dir / cfg.RL_ONNX_FILENAME
    _policy.export_onnx(onnx_path)
    del _policy

    # Always evaluate vs heuristic — keeps the metric stable and aligned with
    # the training objective (75% heuristic games).  Using the latest promoted
    # RL model as champion caused Goodhart's Law collapse: the policy optimised
    # to beat one specific opponent and forgot general card-playing skill.
    champ_ref   = "heuristic"
    champ_label = "heuristic"

    logger.info("[2/3] Tournament %s vs heuristic", dst_name)
    res = rl_tournament(
        model_a = model_path,
        model_b = champ_ref,
        games   = cfg.TOURNEY_GAMES,
        seed    = cfg.TOURNEY_SEED,
    )
    report = format_report(dst_name, champ_label, res)

    log_path = dst_dir / "tournament_vs_heuristic.txt"
    log_path.write_text(report, encoding="utf-8")
    print(report)

    # Promote whenever this version beats heuristic AND beats the previous
    # best heuristic win-rate.  Best-ever is stored as a float in the pointer
    # file alongside the version name (version\nwin_rate).
    prev_best_wr = 0.0
    if RL_PRODUCTION_POINTER.exists():
        lines = RL_PRODUCTION_POINTER.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) >= 2:
            try:
                prev_best_wr = float(lines[1])
            except ValueError:
                prev_best_wr = 0.0

    current_wr = res["win_rate_a"]   # fraction in [0, 1]
    ci_lo      = res["ci95_lo"]

    if ci_lo >= cfg.PROMOTE_MIN_CI_LOWER and current_wr > prev_best_wr:
        rl_promote(dst_name, dst_dir)
        # Append best win-rate to pointer so next iteration can compare.
        RL_PRODUCTION_POINTER.write_text(
            f"{dst_name}\n{current_wr:.6f}\n", encoding="utf-8"
        )
        logger.info(
            "PROMOTED %s → %s  (CI lower %.3f ≥ %.3f, WR %.1f%% > prev best %.1f%%).",
            dst_name, RL_PRODUCTION_MODEL_PATH,
            ci_lo, cfg.PROMOTE_MIN_CI_LOWER,
            current_wr * 100, prev_best_wr * 100,
        )
    else:
        logger.info(
            "NOT promoted: %s WR=%.1f%% CI_lo=%.3f prev_best=%.1f%%.",
            dst_name, current_wr * 100, ci_lo, prev_best_wr * 100,
        )
