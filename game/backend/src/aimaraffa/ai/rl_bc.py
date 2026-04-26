"""Behavioural-cloning pre-trainer for the Maraffa RL policy.

Generates heuristic-vs-heuristic games and trains a policy to imitate
the heuristic via cross-entropy.  Saves the result to rl_v0 so the PPO
batch pipeline starts from a competent baseline instead of from random.

Typical usage:
    python -m aimaraffa.ai.rl_bc               # 10 000 episodes (default)
    python -m aimaraffa.ai.rl_bc --episodes 20000 --epochs 15

Output:
    RL_ARTIFACTS_DIR/rl_v0/marafone_rl_model.pt
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import random
from math import floor
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import torch
import torch.nn.functional as F
import torch.optim as optim

from aimaraffa.agents.heuristic_agent import HeuristicAgent
from aimaraffa.agents.ml_agent import _COL_NAMES
from aimaraffa.engine import (
    Card, Deck, Suit,
    GAME_WIN_THRESHOLD, KEY_CARD, RANK_TO_POINTS,
    determine_turn_winner,
    get_valid_cards, get_valid_declarations,
)

from . import config_rl as cfg
from .rl_env import _briscola_candidates, _card_candidates
from .rl_model import MarafonePolicy
from .simulator import Simulator, _GameState, _TEAM, _SEATS, _SUIT_ENC
from .config_rl import RL_ARTIFACTS_DIR, RL_MODEL_FILENAME

logger = logging.getLogger(__name__)

N_FEATURES = len(_COL_NAMES)
_SUITS_LIST = list(Suit)


# ── Action-index matcher ───────────────────────────────────────────────────────

def _match_card_action(
    cands: List[Tuple[Card, Optional[str]]],
    chosen_card: Card,
    chosen_decl: Optional[str],
) -> int:
    """Find index of (chosen_card, chosen_decl) in candidate list.

    Tries exact match first, falls back to card-only match.
    Returns 0 on complete failure (shouldn't happen in valid games).
    """
    for i, (card, decl) in enumerate(cands):
        if card == chosen_card and decl == chosen_decl:
            return i
    for i, (card, _) in enumerate(cands):
        if card == chosen_card:
            return i
    logger.warning("BC match failure: %s %s not in %d candidates", chosen_card, chosen_decl, len(cands))
    return 0


# ── Single episode collector ───────────────────────────────────────────────────

def _run_bc_episode(
    sim: Simulator,
    heuristics: List[HeuristicAgent],
    rng: random.Random,
) -> List[Tuple[np.ndarray, int]]:
    """Play one complete game with heuristic on all 4 seats.

    Returns list of (feature_matrix [K, F], action_idx) for each decision
    made by any seat.
    """
    state = _GameState()
    state.briscola_selector = None
    data: List[Tuple[np.ndarray, int]] = []

    round_num = 0
    while max(state.total_scores.values()) < GAME_WIN_THRESHOLD:
        round_num += 1

        deck = Deck()
        deck.shuffle()
        for s in _SEATS:
            state.hands[s] = deck.cards[s * 10:(s + 1) * 10]

        if state.briscola_selector is None:
            for s in _SEATS:
                if KEY_CARD in state.hands[s]:
                    state.briscola_selector = s
                    break

        state.round_history  = {}
        state.round_scores   = {1: 0.0, 2: 0.0}
        state.table_tuples   = []
        state.maraffa_forced = False

        for h in heuristics:
            h.reset_round()

        # ── Briscola selection ────────────────────────────────────────────────
        sel_seat = state.briscola_selector
        feats, suits_list = _briscola_candidates(state, sel_seat, round_num, sim)
        ctx = sim._build_ctx(state, sel_seat, round_num, turn_num=0)
        chosen_suit = heuristics[sel_seat].select_briscola(ctx)
        action_idx = suits_list.index(chosen_suit)
        data.append((feats, action_idx))
        state.briscola = chosen_suit

        # Maraffa check
        hand_sel = state.hands[sel_seat]
        mar = [c for c in hand_sel if c.suit == state.briscola and c.rank in (1, 2, 3)]
        if len(mar) == 3:
            state.total_scores[_TEAM[sel_seat]] += 3
            state.maraffa_forced = True
        state.first_of_turn = sel_seat

        # ── 10 turns ──────────────────────────────────────────────────────────
        for turn_idx in range(10):
            turn_num = turn_idx + 1
            state.table_tuples   = []
            state.maraffa_forced = False

            for position in range(4):
                seat = (state.first_of_turn + position) % 4
                team = _TEAM[seat]

                # Build candidate features for this seat.
                feats, cands = _card_candidates(
                    state, seat, round_num, turn_num, position, sim,
                )

                # Ask heuristic what it would play.
                is_lead  = (position == 0)
                lead_s   = state.table_tuples[0][1].suit if state.table_tuples else None

                if state.maraffa_forced and seat == state.briscola_selector and lead_s is None:
                    # Forced card — declaration choice is arbitrary; skip BC signal.
                    forced = Card(state.briscola, 1)
                    decls  = get_valid_declarations(
                        [c for c in state.hands[seat] if c != forced], forced.suit
                    )
                    card, decl = forced, rng.choice(decls)
                else:
                    ctx        = sim._build_ctx(state, seat, round_num, turn_num)
                    card, decl = heuristics[seat].select_card(ctx, state.briscola)
                    action_idx = _match_card_action(cands, card, decl if is_lead else None)
                    data.append((feats, action_idx))

                declaration = decl if position == 0 else None

                state.hands[seat].remove(card)
                key = f"{card.suit.value}_{card.rank}"
                state.round_history[key] = (seat, turn_num, declaration or "")
                state.table_tuples.append((seat, card))

                for h in heuristics:
                    h.record_card(card, seat, turn_num, declaration)

            # Trick resolution
            winner_seat = determine_turn_winner(state.table_tuples, state.briscola)
            winner_team = _TEAM[winner_seat]
            pts = sum(RANK_TO_POINTS[c.rank] for _, c in state.table_tuples)
            state.round_scores[winner_team] += pts
            state.first_of_turn = winner_seat

        # Round end
        last_winner_team = _TEAM[state.first_of_turn]
        state.round_scores[last_winner_team] += 1.0
        s1 = int(floor(state.round_scores[1]))
        s2 = int(floor(state.round_scores[2]))
        state.total_scores[1] += s1
        state.total_scores[2] += s2

        if max(state.total_scores.values()) < GAME_WIN_THRESHOLD:
            state.briscola_selector = (state.briscola_selector + 1) % 4

    return data


# ── Worker ─────────────────────────────────────────────────────────────────────

def _worker_bc(args: tuple) -> List[Tuple[np.ndarray, int]]:
    """Collect n_episodes of BC data in a worker process (CPU-only)."""
    n_episodes, seed = args
    rng        = random.Random(seed)
    sim        = Simulator(model_path=None)
    heuristics = [HeuristicAgent() for _ in range(4)]
    results: List[Tuple[np.ndarray, int]] = []
    for _ in range(n_episodes):
        results.extend(_run_bc_episode(sim, heuristics, rng))
    return results


# ── Training ───────────────────────────────────────────────────────────────────

def train_bc(
    n_episodes: int   = 10_000,
    n_epochs:   int   = 10,
    batch_size: int   = 2_048,
    lr:         float = 1e-3,
    device:     str   = cfg.DEVICE,
    n_workers:  int   = cfg.N_WORKERS,
    out_dir:    Optional[Path] = None,
) -> Path:
    """Collect BC data, train policy to imitate heuristic, save as rl_v0.

    Args:
        n_episodes: number of heuristic-vs-heuristic games to generate
        n_epochs:   training epochs over the collected dataset
        batch_size: decisions per gradient step
        lr:         Adam learning rate
        device:     torch device
        n_workers:  parallel collection workers
        out_dir:    override output directory (default: RL_ARTIFACTS_DIR/rl_v0)

    Returns:
        Path to the saved model checkpoint.
    """
    if out_dir is None:
        out_dir = RL_ARTIFACTS_DIR / "rl_v0"
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / RL_MODEL_FILENAME

    # ── Collect data ───────────────────────────────────────────────────────────
    # Use small tasks (CHUNK_EPS episodes each) streamed via imap to avoid
    # OOM from pickling giant numpy arrays across process boundaries at once.
    CHUNK_EPS   = 50
    logger.info("Collecting %d BC episodes on %d workers (chunk=%d) …",
                n_episodes, n_workers, CHUNK_EPS)
    base_seed   = random.randint(0, 2 ** 31)
    n_chunks    = (n_episodes + CHUNK_EPS - 1) // CHUNK_EPS
    tasks       = [(CHUNK_EPS, base_seed + i) for i in range(n_chunks)]
    # Last chunk: trim to exact episode count
    last_rem    = n_episodes % CHUNK_EPS
    if last_rem:
        tasks[-1] = (last_rem, tasks[-1][1])

    all_data: List[Tuple[np.ndarray, int]] = []
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=n_workers) as pool:
        for i, chunk in enumerate(pool.imap_unordered(_worker_bc, tasks), 1):
            all_data.extend(chunk)
            if i % 20 == 0 or i == n_chunks:
                logger.info("  collected %d/%d chunks (%d decisions so far)",
                            i, n_chunks, len(all_data))
    logger.info("Collected %d decisions from %d episodes.", len(all_data), n_episodes)

    # ── Build model ────────────────────────────────────────────────────────────
    is_cuda = device.startswith("cuda")
    if is_cuda and cfg.USE_TF32:
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32        = True

    policy    = MarafonePolicy(N_FEATURES, cfg.HIDDEN_DIM, cfg.N_LAYERS).to(device)
    optimizer = optim.Adam(policy.parameters(), lr=lr, eps=1e-5, fused=is_cuda)

    # ── Training loop ──────────────────────────────────────────────────────────
    n = len(all_data)
    use_amp   = is_cuda and cfg.USE_AMP and cfg.AMP_DTYPE == "bfloat16"
    amp_dtype = torch.bfloat16 if cfg.AMP_DTYPE == "bfloat16" else torch.float16
    autocast  = (
        torch.amp.autocast(device_type="cuda", dtype=amp_dtype)
        if use_amp
        else torch.amp.autocast(device_type="cpu", enabled=False)
    )

    for epoch in range(1, n_epochs + 1):
        perm    = np.random.permutation(n)
        losses  = []

        policy.train()
        for start in range(0, n, batch_size):
            mb_idx = perm[start:start + batch_size]
            if len(mb_idx) == 0:
                continue

            mb = [all_data[i] for i in mb_idx]
            max_k = max(feats.shape[0] for feats, _ in mb)
            B     = len(mb)

            padded_cpu = torch.zeros(B, max_k, N_FEATURES, dtype=torch.float32)
            mask_cpu   = torch.zeros(B, max_k, dtype=torch.bool)
            actions_cpu = torch.zeros(B, dtype=torch.long)

            for bi, (feats, action_idx) in enumerate(mb):
                k = feats.shape[0]
                padded_cpu[bi, :k] = torch.from_numpy(feats).float()
                mask_cpu[bi, :k]   = True
                actions_cpu[bi]    = action_idx

            if is_cuda:
                padded_cpu  = padded_cpu.pin_memory()
                mask_cpu    = mask_cpu.pin_memory()
                actions_cpu = actions_cpu.pin_memory()

            padded  = padded_cpu.to(device, non_blocking=True)
            mask    = mask_cpu.to(device, non_blocking=True)
            actions = actions_cpu.to(device, non_blocking=True)
            actions = actions.clamp(max=max_k - 1)

            with autocast:
                logits, _ = policy(padded, mask)          # [B, max_k]
                loss = F.cross_entropy(logits, actions)

            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(policy.parameters(), cfg.MAX_GRAD_NORM)
            optimizer.step()
            losses.append(loss.item())

        mean_loss = float(np.mean(losses))
        logger.info("BC epoch %d/%d — loss=%.4f", epoch, n_epochs, mean_loss)

    # ── Save ───────────────────────────────────────────────────────────────────
    policy.eval()
    policy.save(model_path)
    logger.info("BC pre-trained model saved: %s", model_path)
    return model_path


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    logging.basicConfig(
        level  = logging.INFO,
        format = "%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    parser = argparse.ArgumentParser(description="Behavioural-cloning pre-trainer for Maraffa RL.")
    parser.add_argument("--episodes", type=int,   default=10_000, help="BC games to generate (default: 10000)")
    parser.add_argument("--epochs",   type=int,   default=10,     help="Training epochs (default: 10)")
    parser.add_argument("--lr",       type=float, default=1e-3,   help="Learning rate (default: 1e-3)")
    parser.add_argument("--device",   type=str,   default=cfg.DEVICE)
    parser.add_argument("--workers",  type=int,   default=cfg.N_WORKERS)
    args = parser.parse_args()

    train_bc(
        n_episodes = args.episodes,
        n_epochs   = args.epochs,
        lr         = args.lr,
        device     = args.device,
        n_workers  = args.workers,
    )
