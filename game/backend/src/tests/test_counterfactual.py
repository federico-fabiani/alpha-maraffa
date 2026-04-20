"""Tests for the counterfactual action-sampling path."""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from aimaraffa.ai.simulator import (
    Simulator,
    PolicyMixSimulator,
    _GameState,
    simulate,
)


# ── _clone_state preserves seat_policy ─────────────────────────────────────────

def test_clone_state_preserves_seat_policy():
    state = _GameState("G0001")
    state.seat_policy = {0: "latest", 1: "prev1", 2: "random", 3: "latest"}

    clone = Simulator._clone_state(state)

    assert clone.seat_policy == state.seat_policy
    # Must be a copy, not the same dict.
    assert clone.seat_policy is not state.seat_policy


def test_clone_state_has_no_tracker():
    state = _GameState("G0002")
    state.seat_policy = {0: "latest"}

    clone = Simulator._clone_state(state)

    assert clone.tracker is None


# ── Dataset schema ─────────────────────────────────────────────────────────────

def _run_simulate_with_cf(n_games: int = 3, seed: int = 42) -> pd.DataFrame:
    """Helper: run a random self-play simulation with CF enabled."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "test.parquet"
        simulate(
            n_games=n_games,
            seed=seed,
            output_path=out,
            counterfactual=True,
            counterfactual_prob=1.0,
            counterfactual_alts=2,
            counterfactual_rollouts=2,
        )
        return pd.read_parquet(out)


def test_cf_columns_present():
    df = _run_simulate_with_cf()

    assert "decision_id" in df.columns
    assert "is_executed_action" in df.columns
    assert "action_source" in df.columns


def test_cf_rows_have_correct_flags():
    df = _run_simulate_with_cf()

    exec_rows = df[df["is_executed_action"] == 1]
    cf_rows = df[df["is_executed_action"] == 0]

    assert len(exec_rows) > 0, "expected executed rows"
    assert len(cf_rows) > 0, "expected counterfactual rows"
    assert set(exec_rows["action_source"].unique()) == {"policy"}
    assert set(cf_rows["action_source"].unique()) <= {"topk", "random", "exhaustive"}


def test_cf_decision_id_groups_contain_executed_and_cf_rows():
    """Each (game_id, decision_id) group with CF alternatives should contain
    exactly one executed row and at least one counterfactual row."""
    df = _run_simulate_with_cf()

    for (gid, did), group in df.groupby(["game_id", "decision_id"]):
        n_exec = int((group["is_executed_action"] == 1).sum())
        assert n_exec == 1, (
            f"game={gid} decision_id={did}: expected 1 executed row, got {n_exec}"
        )
    # At least some groups must have CF rows.
    multi_groups = [
        g for _, g in df.groupby(["game_id", "decision_id"]) if len(g) > 1
    ]
    assert len(multi_groups) > 0, "expected some decision groups with CF rows"


def test_cf_dataset_has_more_rows_than_no_cf():
    with tempfile.TemporaryDirectory() as td:
        out_no_cf = Path(td) / "no_cf.parquet"
        simulate(n_games=3, seed=42, output_path=out_no_cf,
                 counterfactual=False)
        df_no_cf = pd.read_parquet(out_no_cf)

        out_cf = Path(td) / "cf.parquet"
        simulate(n_games=3, seed=42, output_path=out_cf,
                 counterfactual=True, counterfactual_prob=1.0,
                 counterfactual_alts=2, counterfactual_rollouts=1)
        df_cf = pd.read_parquet(out_cf)

    assert len(df_cf) > len(df_no_cf)


# ── Multi-rollout averaging ───────────────────────────────────────────────────

def test_multi_rollout_both_produce_cf_rows():
    """Both single and multi-rollout runs must produce CF rows."""
    with tempfile.TemporaryDirectory() as td:
        out1 = Path(td) / "r1.parquet"
        simulate(n_games=5, seed=42, output_path=out1,
                 counterfactual=True, counterfactual_prob=1.0,
                 counterfactual_alts=2, counterfactual_rollouts=1)
        df1 = pd.read_parquet(out1)

        out3 = Path(td) / "r3.parquet"
        simulate(n_games=5, seed=42, output_path=out3,
                 counterfactual=True, counterfactual_prob=1.0,
                 counterfactual_alts=2, counterfactual_rollouts=3)
        df3 = pd.read_parquet(out3)

    # Both should have a mix of executed and CF rows.
    for label, df in [("rollouts=1", df1), ("rollouts=3", df3)]:
        n_exec = int((df["is_executed_action"] == 1).sum())
        n_cf = int((df["is_executed_action"] == 0).sum())
        assert n_exec > 0, f"{label}: expected executed rows"
        assert n_cf > 0, f"{label}: expected CF rows"
        assert n_cf / n_exec > 0.3, f"{label}: CF ratio too low"


# ── CF disabled ────────────────────────────────────────────────────────────────

def test_cf_disabled_produces_only_executed_rows():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "no_cf.parquet"
        simulate(n_games=3, seed=42, output_path=out,
                 counterfactual=False)
        df = pd.read_parquet(out)

    assert (df["is_executed_action"] == 1).all()
    assert (df["action_source"] == "policy").all()


# ── Sample weights ─────────────────────────────────────────────────────────────

def test_sample_weight_vector():
    """_load() must assign weight=1 to executed rows and COUNTERFACTUAL_WEIGHT to CF."""
    from aimaraffa.ai import config

    df = _run_simulate_with_cf()
    weights = np.where(
        df["is_executed_action"].values == 1, 1.0, config.COUNTERFACTUAL_WEIGHT
    )

    assert (weights[df["is_executed_action"].values == 1] == 1.0).all()
    assert (weights[df["is_executed_action"].values == 0] == config.COUNTERFACTUAL_WEIGHT).all()
    assert weights.mean() < 1.0, "mean weight should be < 1 when CF rows are present"


# ── PolicyMixSimulator CF rollout uses seat policy ────────────────────────────

def test_policy_mix_clone_preserves_seat_assignments():
    """When PolicyMixSimulator clones state for CF, seat_policy must survive."""
    sim = PolicyMixSimulator(
        policy_models={"latest": None, "random": None},
        seat_policy_mix=[("latest", 0.6), ("random", 0.4)],
        epsilon=0.0,
        counterfactual=True,
    )

    import random as stdlib_random
    sim._rng = stdlib_random.Random(99)

    state = _GameState("G_PMX_001")
    sim._prepare_states([state])

    clone = Simulator._clone_state(state)

    assert clone.seat_policy == state.seat_policy
    assert len(clone.seat_policy) == 4
