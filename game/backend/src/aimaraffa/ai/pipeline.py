"""End-to-end training iteration: dataset → train → analyze → tournament → promote."""

from __future__ import annotations

import logging
import re

from . import analyze, config, simulator, train, tournament
from .versions import (
    latest_version,
    next_version_dir,
    production_version,
    promote,
    recent_versions,
)

logger = logging.getLogger(__name__)


def _resolve_training_policy_models() -> dict[str, object]:
    recent = recent_versions(limit=3)
    model_map = {
        "latest": recent[0][1] if len(recent) >= 1 else None,
        "prev1": recent[1][1] if len(recent) >= 2 else None,
        "prev2": recent[2][1] if len(recent) >= 3 else None,
        "random": None,
    }
    return model_map


def run() -> None:
    src_num, src_model = latest_version()
    if src_model is None:
        src_label = "random"
    elif src_num == 0:
        src_label = "production (legacy, no v<N>)"
    else:
        src_label = f"v{src_num}"

    dst_name, dst_dir = next_version_dir()
    dataset_path  = dst_dir / config.DATASET_FILENAME
    model_path    = dst_dir / config.MODEL_FILENAME
    importance    = dst_dir / config.IMPORTANCE_FILENAME
    analysis_data = dst_dir / config.ANALYSIS_FILENAME
    report_path   = dst_dir / config.REPORT_FILENAME

    logger.info("=" * 60)
    logger.info(" Source version : %s", src_label)
    logger.info(" Target version : %s  (%s)", dst_name, dst_dir)
    logger.info(" Dataset games  : %d  (ε=%.2f)", config.DATASET_GAMES, config.DATASET_EPSILON)
    logger.info(" Dataset policy mix : %s", config.DATASET_POLICY_MIX)
    logger.info(" Counterfactual : %s  (p=%.2f, alts=%d, rollouts=%d, weight=%.2f)",
                config.COUNTERFACTUAL_ENABLED, config.COUNTERFACTUAL_PROBABILITY,
                config.COUNTERFACTUAL_ALTERNATIVES, config.COUNTERFACTUAL_ROLLOUTS,
                config.COUNTERFACTUAL_WEIGHT)
    logger.info(" Analysis games : %d  (ε=0.0)", config.ANALYSIS_GAMES)
    logger.info(" Tourney games  : %d", config.TOURNEY_GAMES)
    logger.info("=" * 60)

    logger.info("[1/5] Generate training dataset")
    policy_models = _resolve_training_policy_models()
    simulator.simulate(
        n_games=config.DATASET_GAMES,
        model_path=src_model,
        epsilon=config.DATASET_EPSILON,
        exploration_top_k=config.DATASET_EXPLORATION_TOP_K,
        policy_models=policy_models,
        seat_policy_mix=config.DATASET_POLICY_MIX,
        output_path=dataset_path,
        counterfactual=config.COUNTERFACTUAL_ENABLED,
        counterfactual_prob=config.COUNTERFACTUAL_PROBABILITY,
        counterfactual_alts=config.COUNTERFACTUAL_ALTERNATIVES,
        counterfactual_rollouts=config.COUNTERFACTUAL_ROLLOUTS,
    )

    logger.info("[2/5] Train model")
    train.train(dataset_path, model_path, importance)

    logger.info("[3/5] Generate analysis dataset (ε=0 self-play of %s)", dst_name)
    simulator.simulate(
        n_games=config.ANALYSIS_GAMES,
        model_path=model_path,
        epsilon=0.0,
        exploration_top_k=config.DATASET_EXPLORATION_TOP_K,
        output_path=analysis_data,
    )

    logger.info("[4/5] Analyze model")
    analyze.analyze(analysis_data, model_path, report_path)

    logger.info("[5/5] Tournament %s vs %s", dst_name, src_label)
    if src_model is None:
        # First model ever — auto-promote, nothing to play against.
        promote(dst_name, dst_dir)
        logger.info("PROMOTED %s → %s (bootstrap, no source to compare).",
                    dst_name, config.PRODUCTION_MODEL_PATH)
        return

    res = tournament.tournament(model_path, src_model,
                                games=config.TOURNEY_GAMES, seed=config.TOURNEY_SEED)
    report = tournament.format_report(dst_name, src_label, res)
    log_safe = re.sub(r'[<>:"/\\|?*,()]+', '_', src_label).strip('_')
    log_path = dst_dir / f"tournament_vs_{log_safe.replace(' ', '_')}.txt"
    log_path.write_text(report, encoding="utf-8")
    print(report)

    if res["ci95_lo"] >= config.PROMOTE_MIN_CI_LOWER:
        promote(dst_name, dst_dir)
        logger.info("PROMOTED %s → %s  (CI lower %.3f ≥ %.3f).",
                    dst_name, config.PRODUCTION_MODEL_PATH,
                    res["ci95_lo"], config.PROMOTE_MIN_CI_LOWER)
    else:
        prod = production_version() or "(none)"
        logger.info("NOT promoted: %s win-rate=%.1f%% "
                    "(CI lower %.3f < %.3f). Production stays at %s.",
                    dst_name, res["win_rate_a"] * 100,
                    res["ci95_lo"], config.PROMOTE_MIN_CI_LOWER, prod)
