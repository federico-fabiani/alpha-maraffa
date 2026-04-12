"""Shared pytest fixtures for the aimaraffa test suite."""

import pytest

import aimaraffa.engine as eng


@pytest.fixture(autouse=True)
def zero_delays(monkeypatch):
    """Patch all game timing delays to zero so tests run instantly."""
    monkeypatch.setattr(eng, "BOT_PLAY_DELAY", 0.0)
    monkeypatch.setattr(eng, "BOT_THINK_DELAY", 0.0)
    monkeypatch.setattr(eng, "TURN_RESULT_PAUSE", 0.0)
    monkeypatch.setattr(eng, "ROUND_END_PAUSE", 0.0)
