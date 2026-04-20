"""Tests for mixed-policy training self-play helpers."""

import random
from pathlib import Path

from aimaraffa.ai.simulator import (
    PolicyMixSimulator,
    _GameState,
    _normalize_policy_mix,
    _policy_mix_has_learned_model,
    _sample_policy_label,
)


def test_normalize_policy_mix_drops_non_positive_weights():
    mix = _normalize_policy_mix([("latest", 3.0), ("prev1", 0.0), ("random", 1.0)])

    assert mix == [("latest", 0.75), ("random", 0.25)]


def test_sample_policy_label_returns_only_known_labels():
    rng = random.Random(42)
    mix = [("latest", 0.7), ("random", 0.3)]

    picks = {_sample_policy_label(rng, mix) for _ in range(30)}

    assert picks == {"latest", "random"}


def test_prepare_states_assigns_fixed_policy_when_mix_is_degenerate():
    simulator = PolicyMixSimulator(
        policy_models={"latest": None},
        seat_policy_mix=[("latest", 1.0)],
        epsilon=0.0,
    )
    simulator._rng = random.Random(7)
    states = [_GameState("G0000001"), _GameState("G0000002")]

    simulator._prepare_states(states)

    assert all(set(state.seat_policy.values()) == {"latest"} for state in states)


def test_policy_mix_has_learned_model_only_when_active_label_has_model():
    assert not _policy_mix_has_learned_model(
        {"latest": None, "random": None},
        [("latest", 0.9), ("random", 0.1)],
    )

    assert _policy_mix_has_learned_model(
        {"latest": Path("v3.joblib"), "random": None},
        [("latest", 0.9), ("random", 0.1)],
    )