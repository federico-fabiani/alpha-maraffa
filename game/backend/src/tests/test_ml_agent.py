"""Regression tests for ML-based action selection helpers."""

import numpy as np

import aimaraffa.ai.simulator as simulator_module
import aimaraffa.ml_agent as ml_agent_module
from aimaraffa.ai.simulator import Simulator, _GameState
from aimaraffa.engine import Card, Suit
from aimaraffa.ml_agent import MLAgent


def test_ml_agent_select_briscola_uses_best_opening_line(monkeypatch):
    """Briscola selection must follow the best opening, not the average opening value."""
    monkeypatch.setattr(ml_agent_module, "get_valid_declarations", lambda _hand, _suit: [None])

    value_map = {
        (Suit.BASTONI, Suit.BASTONI): 9.0,
        (Suit.BASTONI, Suit.COPPE): 1.0,
        (Suit.COPPE, Suit.BASTONI): 6.0,
        (Suit.COPPE, Suit.COPPE): 6.0,
        (Suit.DENARA, Suit.BASTONI): 0.0,
        (Suit.DENARA, Suit.COPPE): 0.0,
        (Suit.SPADE, Suit.BASTONI): 0.0,
        (Suit.SPADE, Suit.COPPE): 0.0,
    }

    agent = MLAgent.__new__(MLAgent)
    agent._build_np_row = (
        lambda card, _decl, briscola, _ctx, force_lead=False: np.array(
            [value_map[(briscola, card.suit)]], dtype=np.float32
        )
    )
    agent._predict = lambda rows: np.array([row[0] for row in rows], dtype=np.float32)

    hand = [Card(Suit.BASTONI, 1), Card(Suit.COPPE, 1)]
    picked = agent.select_briscola({"hand": hand})

    assert picked == Suit.BASTONI


def test_simulator_select_briscolas_uses_best_opening_line(monkeypatch):
    """Training self-play must rank briscole with the same criterion as runtime inference."""
    monkeypatch.setattr(simulator_module, "get_valid_declarations", lambda _hand, _suit: [None])

    value_map = {
        (Suit.BASTONI, Suit.BASTONI): 9.0,
        (Suit.BASTONI, Suit.COPPE): 1.0,
        (Suit.COPPE, Suit.BASTONI): 6.0,
        (Suit.COPPE, Suit.COPPE): 6.0,
        (Suit.DENARA, Suit.BASTONI): 0.0,
        (Suit.DENARA, Suit.COPPE): 0.0,
        (Suit.SPADE, Suit.BASTONI): 0.0,
        (Suit.SPADE, Suit.COPPE): 0.0,
    }

    class DummyAgent:
        @staticmethod
        def _build_np_row(card, _decl, briscola, _ctx, force_lead=False):
            return np.array([value_map[(briscola, card.suit)]], dtype=np.float32)

    simulator = Simulator.__new__(Simulator)
    simulator.random_mode = False
    simulator.agent = DummyAgent()
    simulator._batched_predict = lambda rows: np.array([row[0] for row in rows], dtype=np.float32)

    state = _GameState("G0000001")
    state.briscola_selector = 0
    state.hands[0] = [Card(Suit.BASTONI, 1), Card(Suit.COPPE, 1)]

    simulator._select_briscolas([state], round_num=1)

    assert state.briscola == Suit.BASTONI