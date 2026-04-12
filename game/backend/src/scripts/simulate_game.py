"""Simulate and log a complete Marafone game with four bot players."""

import asyncio
import logging

import aimaraffa.engine as eng
from aimaraffa.engine import GameRoom

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


async def _log_event(msg: dict) -> None:
    """Print a game event as a structured log line."""
    t = msg.get("type", "?")
    d = msg.get("data", {})

    if t == "game_started":
        logger.info("[GAME STARTED] %s", [(p["seat"], p["name"]) for p in d["players"]])

    elif t == "briscola_set":
        logger.info("[BRISCOLA]  %s (seat %s) sceglie %s", d["by_name"], d["by_seat"], d["suit"].upper())

    elif t == "card_played":
        logger.info(
            "[CARD]      seat %s (%s) gioca %s/%s",
            d["seat"], d["name"], d["card"]["rank"], d["card"]["suit"],
        )

    elif t == "turn_result":
        logger.info(
            "[TURN]      vince %s (team %s)  +%s pt  |  round: %s",
            d["winner_name"], d["winner_team"], d["points"], d["round_scores"],
        )

    elif t == "round_end":
        logger.info(
            "[ROUND %s]   punti round: %s  |  totale: %s",
            d["round"], d["round_scores"], d["total_scores"],
        )

    elif t == "game_over":
        logger.info(
            "[GAME OVER] team %s vince!  Punteggio finale: %s",
            d["winner_team"], d["scores"],
        )


async def simulate() -> None:
    """Run a full Marafone game with 4 bots and log every event."""
    # Zero out all timing delays so the simulation runs instantly
    eng.BOT_PLAY_DELAY    = 0.0
    eng.BOT_THINK_DELAY   = 0.0
    eng.TURN_RESULT_PAUSE = 0.0
    eng.ROUND_END_PAUSE   = 0.0

    room = GameRoom("SIM-001")

    # Replace WebSocket-based methods with plain logging
    room.broadcast       = _log_event
    room.broadcast_state = lambda phase=None: asyncio.sleep(0)
    room._send           = lambda seat, msg: _log_event(msg)

    logger.info("=" * 60)
    logger.info("=== Inizio simulazione Marafone ===")
    logger.info("=" * 60)

    await room.run_game_loop()

    logger.info("=" * 60)
    logger.info("=== Fine simulazione ===")
    logger.info("Score finale: team 1 = %s  |  team 2 = %s",
                room.total_scores[1], room.total_scores[2])
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(simulate())
