"""Pipeline configuration tests."""

from aimaraffa.ai import config
from aimaraffa.ai.pipeline import _resolve_dataset_generation_options


def test_bootstrap_dataset_generation_uses_fast_path():
    options = _resolve_dataset_generation_options(bootstrap=True)

    assert options["policy_models"] is None
    assert options["seat_policy_mix"] is None
    assert options["counterfactual"] is False
    assert options["counterfactual_prob"] == 0.0
    assert options["counterfactual_alts"] == 0
    assert options["counterfactual_rollouts"] == 0


def test_non_bootstrap_dataset_generation_keeps_training_features():
    policy_models = {"latest": object(), "random": None}

    options = _resolve_dataset_generation_options(
        bootstrap=False,
        policy_models=policy_models,
    )

    assert options["policy_models"] is policy_models
    assert options["seat_policy_mix"] == config.DATASET_POLICY_MIX
    assert options["counterfactual"] == config.COUNTERFACTUAL_ENABLED
    assert options["counterfactual_prob"] == config.COUNTERFACTUAL_PROBABILITY
    assert options["counterfactual_alts"] == config.COUNTERFACTUAL_ALTERNATIVES
    assert options["counterfactual_rollouts"] == config.COUNTERFACTUAL_ROLLOUTS