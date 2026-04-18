"""Simulate Marafone games and produce a per-play CSV for ML training."""

import argparse
import asyncio
import logging
import multiprocessing
import os
import random
import tempfile
from math import floor
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import aimaraffa.engine as eng
from aimaraffa.engine import (
    Card, Deck, GameRoom, Suit,
    GAME_WIN_THRESHOLD, KEY_CARD, RANK_TO_POINTS,
    bot_select_briscola, bot_select_card, determine_turn_winner,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_SUITS = ["bastoni", "denara", "spade", "coppe"]
_RANKS = list(range(1, 11))
_SEATS = [0, 1, 2, 3]
_TEAM  = {0: 1, 1: 2, 2: 1, 3: 2}

# Pre-computed template dicts — copied once per call instead of rebuilt from scratch
_HAND_TEMPLATE: Dict[str, int] = {}
for _r in _RANKS:
    _HAND_TEMPLATE[f"hand_briscola_{_r}"] = 0
    _HAND_TEMPLATE[f"hand_lead_{_r}"]     = 0
    _HAND_TEMPLATE[f"hand_other_{_r}_count"] = 0

_HISTORY_TEMPLATE: dict = {}
for _s in _SUITS:
    for _r in _RANKS:
        _HISTORY_TEMPLATE[f"hist_{_s}_{_r}_seat"] = -1
        _HISTORY_TEMPLATE[f"hist_{_s}_{_r}_turn"] = -1
        _HISTORY_TEMPLATE[f"hist_{_s}_{_r}_decl"] = ""

# Pre-computed field name list (avoid rebuilding on every worker spawn)
_FIELDNAMES: List[str] = (  # noqa: E501
    [
        "game_id", "round_num", "turn_num", "play_order",
        "seat", "team", "briscola_suit", "briscola_selector_seat",
        "card_rank", "card_is_briscola", "card_is_lead",
        "is_lead", "lead_suit", "declaration",
        "table_0_rank", "table_0_is_briscola", "table_0_is_lead", "table_0_seat",
        "table_1_rank", "table_1_is_briscola", "table_1_is_lead", "table_1_seat",
        "table_2_rank", "table_2_is_briscola", "table_2_is_lead", "table_2_seat",
        "round_score_t1", "round_score_t2",
        "total_score_t1", "total_score_t2",
    ] +
    [f"hand_briscola_{r}" for r in _RANKS] +
    [f"hand_lead_{r}"     for r in _RANKS] +
    [f"hand_other_{r}_count" for r in _RANKS] +
    [f"hist_{s}_{r}_seat" for s in _SUITS for r in _RANKS] +
    [f"hist_{s}_{r}_turn" for s in _SUITS for r in _RANKS] +
    [f"hist_{s}_{r}_decl" for s in _SUITS for r in _RANKS] +
    [
        "turn_winner_seat", "turn_winner_team", "turn_pts",
        "round_pts_t1", "round_pts_t2",
        "round_pts_player_team", "round_pts_diff",
    ]
)

# Optimal dtypes per column — eliminates float64 bloat (11 GB → ~1 GB in RAM)
_DTYPE_MAP: Dict[str, str] = {
    "game_id":                 "category",
    "round_num":               "int8",
    "turn_num":                "int8",
    "play_order":              "int8",
    "seat":                    "int8",
    "team":                    "int8",
    "briscola_suit":           "category",
    "briscola_selector_seat":  "int8",
    "card_rank":               "int8",
    "card_is_briscola":        "int8",
    "card_is_lead":            "int8",
    "is_lead":                 "int8",
    "lead_suit":               "category",
    "declaration":             "category",
    "table_0_rank":            "int8",  # -1 = empty slot
    "table_0_is_briscola":     "int8",
    "table_0_is_lead":         "int8",
    "table_0_seat":            "int8",
    "table_1_rank":            "int8",
    "table_1_is_briscola":     "int8",
    "table_1_is_lead":         "int8",
    "table_1_seat":            "int8",
    "table_2_rank":            "int8",
    "table_2_is_briscola":     "int8",
    "table_2_is_lead":         "int8",
    "table_2_seat":            "int8",
    "round_score_t1":          "float32",
    "round_score_t2":          "float32",
    "total_score_t1":          "int16",
    "total_score_t2":          "int16",
    **{f"hand_briscola_{r}":      "int8" for r in _RANKS},
    **{f"hand_lead_{r}":          "int8" for r in _RANKS},
    **{f"hand_other_{r}_count":   "int8" for r in _RANKS},
    **{f"hist_{s}_{r}_seat":      "int8" for s in _SUITS for r in _RANKS},
    **{f"hist_{s}_{r}_turn":      "int8" for s in _SUITS for r in _RANKS},
    **{f"hist_{s}_{r}_decl":  "category" for s in _SUITS for r in _RANKS},
    "turn_winner_seat":         "int8",
    "turn_winner_team":         "int8",
    "turn_pts":                 "float32",
    "round_pts_t1":             "int8",
    "round_pts_t2":             "int8",
    "round_pts_player_team":    "int8",
    "round_pts_diff":           "int16",
}


# ── Feature helpers ────────────────────────────────────────────────────────────

def _suit_role(suit: str, briscola: str, lead: str):
    """Return (is_briscola, is_lead) for a suit — mutually exclusive binary flags."""
    is_briscola = int(suit == briscola)
    is_lead     = int(suit == lead and suit != briscola)
    return is_briscola, is_lead


def _hand_features(hand: List[dict], briscola: str, lead: str) -> Dict[str, int]:
    """
    Role-relative hand encoding (suit-invariant):
      hand_briscola_{rank}    — 1 if player holds rank R of briscola suit
      hand_lead_{rank}        — 1 if player holds rank R of lead suit (non-briscola)
      hand_other_{rank}_count — how many non-briscola non-lead cards of rank R (0-2)
    Total: 30 columns vs 40 absolute.
    """
    feat = _HAND_TEMPLATE.copy()
    for c in hand:
        r = c["rank"]
        ib, il = _suit_role(c["suit"], briscola, lead)
        if ib:
            feat[f"hand_briscola_{r}"] = 1
        elif il:
            feat[f"hand_lead_{r}"] = 1
        else:
            feat[f"hand_other_{r}_count"] += 1
    return feat


def _history_features(played: Dict[str, tuple]) -> dict:
    """Seat, turn, and declaration for each card (-1/'' = not yet played).
    History keeps absolute suit identity — needed for card counting across turns."""
    feat = _HISTORY_TEMPLATE.copy()
    for key, (seat, turn, decl) in played.items():
        feat[f"hist_{key}_seat"] = seat
        feat[f"hist_{key}_turn"] = turn
        feat[f"hist_{key}_decl"] = decl
    return feat


def _fieldnames() -> List[str]:
    return _FIELDNAMES


# ── Event tracker ──────────────────────────────────────────────────────────────

class GameTracker:
    """Converts broadcast events into tabular rows; retroactively fills turn/round outcomes."""

    def __init__(self, game_id: str):
        self.game_id = game_id
        self._round_num = 0
        self._turns_done = 0
        self._briscola: Optional[str] = None
        self._briscola_selector: Optional[int] = None
        self._total_scores: Dict[int, int] = {1: 0, 2: 0}
        self._round_scores: Dict[int, float] = {1: 0.0, 2: 0.0}
        self._round_history: Dict[str, tuple] = {}  # "suit_rank" -> (seat, turn_num, decl)
        self._pending_turn: List[dict] = []
        self._pending_round: List[dict] = []
        self.rows: List[dict] = []

    def on_event(self, msg: dict) -> None:
        t = msg["type"]
        d = msg.get("data", {})

        if t == "briscola_set":
            self._round_num += 1
            self._turns_done = 0
            self._briscola = d["suit"]
            self._briscola_selector = d["by_seat"]
            self._round_scores = {1: 0.0, 2: 0.0}
            self._round_history = {}

        elif t == "card_played":
            table    = d["table"]           # includes current card (appended before broadcast)
            play_order = len(table) - 1
            lead_suit  = table[0]["card"]["suit"]
            card       = d["card"]
            prev       = table[:play_order]  # cards on table before this play

            cib, cil = _suit_role(card["suit"], self._briscola, lead_suit)

            def _tslot(i):
                if len(prev) <= i:
                    return {"rank": -1, "is_briscola": -1, "is_lead": -1, "seat": -1}
                ib, il = _suit_role(prev[i]["card"]["suit"], self._briscola, lead_suit)
                return {"rank": prev[i]["card"]["rank"], "is_briscola": ib, "is_lead": il,
                        "seat": prev[i]["seat"]}

            t0, t1, t2 = _tslot(0), _tslot(1), _tslot(2)

            row: dict = {
                "game_id": self.game_id,
                "round_num": self._round_num,
                "turn_num": self._turns_done + 1,
                "play_order": play_order,
                "seat": d["seat"],
                "team": 1 if d["seat"] in (0, 2) else 2,
                "briscola_suit": self._briscola,
                "briscola_selector_seat": self._briscola_selector,
                "card_rank": card["rank"],
                "card_is_briscola": cib,
                "card_is_lead": cil,
                "is_lead": int(play_order == 0),
                "lead_suit": lead_suit,
                "declaration": d.get("declaration") or "",
                "table_0_rank": t0["rank"], "table_0_is_briscola": t0["is_briscola"],
                "table_0_is_lead": t0["is_lead"], "table_0_seat": t0["seat"],
                "table_1_rank": t1["rank"], "table_1_is_briscola": t1["is_briscola"],
                "table_1_is_lead": t1["is_lead"], "table_1_seat": t1["seat"],
                "table_2_rank": t2["rank"], "table_2_is_briscola": t2["is_briscola"],
                "table_2_is_lead": t2["is_lead"], "table_2_seat": t2["seat"],
                "round_score_t1": round(self._round_scores[1], 2),
                "round_score_t2": round(self._round_scores[2], 2),
                "total_score_t1": self._total_scores[1],
                "total_score_t2": self._total_scores[2],
                **_hand_features(d.get("hand_before", []), self._briscola, lead_suit),
                **_history_features(self._round_history),
                # filled retroactively
                "turn_winner_seat": None,
                "turn_winner_team": None,
                "turn_pts": None,
                "round_pts_t1": None,
                "round_pts_t2": None,
                "round_pts_player_team": None,
                "round_pts_diff": None,
            }

            self._round_history[f"{card['suit']}_{card['rank']}"] = (
                d["seat"], self._turns_done + 1, d.get("declaration") or ""
            )
            self._pending_turn.append(row)

        elif t == "turn_result":
            for row in self._pending_turn:
                row["turn_winner_seat"] = d["winner_seat"]
                row["turn_winner_team"] = d["winner_team"]
                row["turn_pts"] = d["points"]
            self._round_scores = {k: v for k, v in d["round_scores"].items()}
            self._pending_round.extend(self._pending_turn)
            self._pending_turn.clear()
            self._turns_done += 1

        elif t == "round_end":
            rpts = d["round_scores"]
            for row in self._pending_round:
                team = row["team"]
                opp  = 3 - team
                row["round_pts_t1"]          = rpts[1]
                row["round_pts_t2"]          = rpts[2]
                row["round_pts_player_team"] = rpts[team]
                row["round_pts_diff"]        = rpts[team] - rpts[opp]
            self.rows.extend(self._pending_round)
            self._pending_round.clear()
            self._total_scores = {k: v for k, v in d["total_scores"].items()}


# ── Logging ────────────────────────────────────────────────────────────────────

async def _log_event(msg: dict) -> None:
    t = msg.get("type", "?")
    d = msg.get("data", {})

    if t == "game_started":
        logger.info("[GAME STARTED] %s", [(p["seat"], p["name"]) for p in d["players"]])
    elif t == "briscola_set":
        logger.info("[BRISCOLA]  %s (seat %s) sceglie %s", d["by_name"], d["by_seat"], d["suit"].upper())
    elif t == "card_played":
        decl = f" dichiarando {d['declaration'].upper()}" if d.get("declaration") else ""
        logger.info("[CARD]      seat %s (%s) gioca %s/%s%s",
                    d["seat"], d["name"], d["card"]["rank"], d["card"]["suit"], decl)
    elif t == "turn_result":
        logger.info("[TURN]      vince %s (team %s)  +%s pt  |  round: %s",
                    d["winner_name"], d["winner_team"], d["points"], d["round_scores"])
    elif t == "round_end":
        logger.info("[ROUND %s]   punti round: %s  |  totale: %s",
                    d["round"], d["round_scores"], d["total_scores"])
    elif t == "game_over":
        logger.info("[GAME OVER] team %s vince!  Punteggio finale: %s",
                    d["winner_team"], d["scores"])


# ── Simulation runner ──────────────────────────────────────────────────────────

def simulate_one_sync(game_id: str, tracker: GameTracker) -> None:
    """Pure synchronous game simulation — no asyncio overhead."""
    total_scores: Dict[int, int] = {1: 0, 2: 0}
    hands: Dict[int, list] = {}
    briscola_selector: Optional[int] = None

    while max(total_scores.values()) < GAME_WIN_THRESHOLD:
        # Deal cards
        deck = Deck()
        deck.shuffle()
        for s in _SEATS:
            hands[s] = deck.deal(10)

        # Round 1: KEY_CARD holder picks briscola; subsequent rounds rotate
        if briscola_selector is None:
            for s in _SEATS:
                if KEY_CARD in hands[s]:
                    briscola_selector = s
                    break

        briscola = bot_select_briscola(hands[briscola_selector])
        tracker.on_event({"type": "briscola_set", "data": {
            "suit": briscola.value,
            "by_seat": briscola_selector,
            "by_name": "",
        }})

        # Maraffa (cricca): selettore ha 1, 2 e 3 di briscola → +3 punti immediati
        maraffa_cards = [c for c in hands[briscola_selector]
                         if c.suit == briscola and c.rank in (1, 2, 3)]
        if len(maraffa_cards) == 3:
            total_scores[_TEAM[briscola_selector]] += 3

        round_scores: Dict[int, float] = {1: 0.0, 2: 0.0}
        first = briscola_selector

        for _ in range(10):
            idx = _SEATS.index(first)
            order = _SEATS[idx:] + _SEATS[:idx]

            table_tuples: list = []   # (seat, Card) — for determine_turn_winner
            table_dicts:  list = []   # {"seat": s, "card": {"suit": ..., "rank": ...}}

            for i, seat in enumerate(order):
                lead_suit_obj = table_tuples[0][1].suit if table_tuples else None

                hand_before = [{"suit": c.suit.value, "rank": c.rank} for c in hands[seat]]
                card, decl = bot_select_card(hands[seat], lead_suit_obj, briscola)
                hands[seat].remove(card)
                declaration = decl if i == 0 else None

                card_dict = {"suit": card.suit.value, "rank": card.rank}
                table_tuples.append((seat, card))
                table_dicts.append({"seat": seat, "card": card_dict})

                # Pass table_dicts by reference — tracker reads it synchronously
                tracker.on_event({"type": "card_played", "data": {
                    "seat": seat,
                    "card": card_dict,
                    "declaration": declaration,
                    "table": table_dicts,
                    "hand_before": hand_before,
                }})

            winner_seat = determine_turn_winner(table_tuples, briscola)
            winner_team = _TEAM[winner_seat]
            turn_pts = sum(RANK_TO_POINTS[c.rank] for _, c in table_tuples)
            round_scores[winner_team] += turn_pts

            tracker.on_event({"type": "turn_result", "data": {
                "winner_seat": winner_seat,
                "winner_team": winner_team,
                "winner_name": "",
                "points": round(turn_pts, 2),
                "round_scores": {1: round(round_scores[1], 2), 2: round(round_scores[2], 2)},
            }})

            first = winner_seat

        # Last-trick bonus
        round_scores[_TEAM[first]] += 1
        round_scores[1] = floor(round_scores[1])
        round_scores[2] = floor(round_scores[2])
        for team in (1, 2):
            total_scores[team] += int(round_scores[team])

        tracker.on_event({"type": "round_end", "data": {
            "round": tracker._round_num,
            "round_scores": {1: int(round_scores[1]), 2: int(round_scores[2])},
            "total_scores": dict(total_scores),
        }})

        # Rotate briscola selector
        briscola_selector = _SEATS[(_SEATS.index(briscola_selector) + 1) % 4]


async def simulate_one(game_id: str, tracker: GameTracker, verbose: bool) -> None:
    eng.BOT_PLAY_DELAY    = 0.0
    eng.BOT_THINK_DELAY   = 0.0
    eng.TURN_RESULT_PAUSE = 0.0
    eng.ROUND_END_PAUSE   = 0.0

    room = GameRoom(game_id)

    async def _broadcast(msg: dict) -> None:
        tracker.on_event(msg)
        if verbose:
            await _log_event(msg)

    room.broadcast       = _broadcast
    room.broadcast_state = lambda phase=None: asyncio.sleep(0)

    await room.run_game_loop()


def _rows_to_table(rows: list) -> pa.Table:
    """Convert a list of row dicts to a typed PyArrow Table."""
    df = pd.DataFrame(rows, columns=_FIELDNAMES)
    for col, dtype in _DTYPE_MAP.items():
        if col in df.columns:
            df[col] = df[col].astype(dtype)
    return pa.Table.from_pandas(df, preserve_index=False)


def _simulate_batch(args: tuple) -> str:
    """Worker: simulate a batch of games, write rows to a temp Parquet file, return the path."""
    game_ids, _verbose, tmp_path = args
    rows: list = []
    for gid in game_ids:
        tracker = GameTracker(gid)
        simulate_one_sync(gid, tracker)
        rows.extend(tracker.rows)
    pq.write_table(_rows_to_table(rows), tmp_path, compression="snappy")
    return tmp_path


def run(n_games: int, output: Path, verbose: bool, workers: int = 0) -> None:
    n_workers = min(workers or os.cpu_count() or 1, n_games)
    # Small batches: better load balancing; workers return only a file path via IPC
    batch_size = max(1, min(500, (n_games + n_workers - 1) // n_workers))

    tmp_dir = Path(tempfile.mkdtemp(prefix="maraffa_sim_"))
    batches = [
        (
            [f"G{j:07d}" for j in range(start, min(start + batch_size, n_games))],
            verbose and start == 0,
            str(tmp_dir / f"batch_{i:05d}.parquet"),
        )
        for i, start in enumerate(range(0, n_games, batch_size))
    ]

    games_done = 0
    parquet_writer: pq.ParquetWriter | None = None
    try:
        if len(batches) > 1:
            with multiprocessing.Pool(processes=n_workers) as pool:
                for tmp_path in pool.imap_unordered(_simulate_batch, batches):
                    table = pq.read_table(tmp_path)
                    if parquet_writer is None:
                        parquet_writer = pq.ParquetWriter(str(output), table.schema, compression="snappy")
                    parquet_writer.write_table(table)
                    Path(tmp_path).unlink()
                    games_done = min(games_done + batch_size, n_games)
                    logger.info("Progress: %d/%d games", games_done, n_games)
        else:
            tmp_path = _simulate_batch(batches[0])
            table = pq.read_table(tmp_path)
            parquet_writer = pq.ParquetWriter(str(output), table.schema, compression="snappy")
            parquet_writer.write_table(table)
            Path(tmp_path).unlink()
    finally:
        if parquet_writer is not None:
            parquet_writer.close()

    tmp_dir.rmdir()
    logger.info("Done. %d games → %s", n_games, output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate Marafone games for ML training")
    parser.add_argument("--games",   type=int,  default=1,
                        help="Number of games to simulate (default: 1)")
    parser.add_argument("--output",  type=Path,
                        default=Path("src/scripts/artifacts/marafone_dataset.parquet"),
                        help="Output Parquet path")
    parser.add_argument("--verbose", action="store_true",
                        help="Print play-by-play log for the first game")
    parser.add_argument("--workers", type=int, default=0,
                        help="Parallel worker processes (default: CPU count)")
    args = parser.parse_args()
    run(args.games, args.output, args.verbose, args.workers)


if __name__ == "__main__":
    main()
