"""Tests for live agent construction."""

import pytest

from aimaraffa.agents.factory import create_agent
from aimaraffa.agents.heuristic_agent import HeuristicAgent
from aimaraffa.agents.random_agent import RandomAgent


def test_create_agent_builds_heuristic_by_default_policy():
    """The live factory should resolve heuristic bots from the policy label."""
    assert isinstance(create_agent("heuristic"), HeuristicAgent)


def test_create_agent_builds_random_policy():
    """The live factory should resolve random bots from the policy label."""
    assert isinstance(create_agent("random"), RandomAgent)


def test_create_agent_rejects_ml_without_model_path():
    """ML policy selection must require an explicit model path."""
    with pytest.raises(ValueError, match="model path"):
        create_agent("ml")