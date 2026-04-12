"""FastAPI application: REST room management and WebSocket game server."""

import asyncio
import json
import logging

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from aimaraffa.config import settings
from aimaraffa.engine import GameRoom, PlayerSlot, RoomManager

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Marafone Digital")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rooms = RoomManager()


# ── REST endpoints ─────────────────────────────────────────────────────────────

class CreateRoomBody(BaseModel):
    """Request body for POST /api/rooms."""

    player_name: str = "Giocatore"


@app.post("/api/rooms")
async def create_room(body: CreateRoomBody):
    """Create a new game room and return its ID."""
    room = rooms.create()
    logger.info("Room created: %s", room.room_id)
    return {"room_id": room.room_id}


@app.get("/api/rooms/{room_id}")
async def get_room(room_id: str):
    """Return room details, or raise 404 if not found."""
    room = rooms.get(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return {
        "room_id": room.room_id,
        "status": room.status,
        "players": [
            {"seat": s, "name": sl.name, "is_bot": sl.is_bot}
            for s, sl in sorted(room.slots.items())
        ],
    }


# ── WebSocket endpoint ─────────────────────────────────────────────────────────

@app.websocket("/ws/{room_id}")
async def ws_endpoint(websocket: WebSocket, room_id: str, player_name: str = "Giocatore"):
    """Handle WebSocket connections: join a waiting room or reconnect to an in-game room."""
    await websocket.accept()

    room = rooms.get(room_id)
    if not room:
        await websocket.send_text(json.dumps({"type": "error", "data": {"message": "Stanza non trovata"}}))
        await websocket.close()
        return

    my_slot: PlayerSlot = None

    if room.status == "in_game":
        # Reconnection: find a disconnected slot with the same name
        for slot in room.slots.values():
            if not slot.is_bot and not slot.is_connected and slot.name == player_name:
                my_slot = slot
                break
        if my_slot is None:
            await websocket.send_text(json.dumps({"type": "error", "data": {"message": "Partita già iniziata"}}))
            await websocket.close()
            return
        my_slot.websocket = websocket
        my_slot.is_connected = True
        await websocket.send_text(json.dumps({"type": "reconnected", "data": {"seat": my_slot.seat}}))
        await room._send(my_slot.seat, room._build_state(my_slot.seat))
        logger.info("%s reconnected to %s seat %s", player_name, room_id, my_slot.seat)

    else:
        taken = set(room.slots.keys())
        seat = next((s for s in range(4) if s not in taken), None)
        if seat is None:
            await websocket.send_text(json.dumps({"type": "error", "data": {"message": "Stanza piena"}}))
            await websocket.close()
            return

        my_slot = PlayerSlot(seat=seat, name=player_name, is_bot=False)
        my_slot.websocket = websocket
        room.slots[seat] = my_slot

        if room.creator_slot is None:
            room.creator_slot = my_slot

        player_list = [
            {"seat": s, "name": sl.name, "is_bot": sl.is_bot, "team": sl.team}
            for s, sl in sorted(room.slots.items())
        ]
        await websocket.send_text(json.dumps({
            "type": "joined",
            "data": {"seat": seat, "room_id": room.room_id, "players": player_list},
        }))
        await room.broadcast({
            "type": "player_joined",
            "data": {"seat": seat, "name": player_name, "players": player_list},
        })
        logger.info("%s joined %s seat %s", player_name, room_id, seat)

    try:
        async for raw in websocket.iter_text():
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            await _handle(room, my_slot, msg)
    except WebSocketDisconnect:
        pass
    finally:
        # Always clean up regardless of how the connection ended
        # (WebSocketDisconnect, normal close frame, or any other exception)
        if not my_slot.is_connected and my_slot.websocket is None:
            # Already cleaned up (e.g. double disconnect), skip
            return
        my_slot.is_connected = False
        my_slot.websocket = None
        if room.status == "waiting":
            room.slots.pop(my_slot.seat, None)
            player_list = [
                {"seat": s, "name": sl.name, "is_bot": sl.is_bot, "team": sl.team}
                for s, sl in sorted(room.slots.items())
            ]
            await room.broadcast({
                "type": "player_left",
                "data": {"seat": my_slot.seat, "name": my_slot.name, "players": player_list},
            })
        else:
            await room.broadcast({"type": "player_disconnected", "data": {"seat": my_slot.seat, "name": my_slot.name}})
        logger.info("%s disconnected from %s", my_slot.name, room_id)


async def _handle(room: GameRoom, slot: PlayerSlot, msg: dict) -> None:
    """Dispatch an incoming WebSocket message to the appropriate handler."""
    t = msg.get("type")
    data = msg.get("data", {})

    if t == "start_game":
        if room.status == "waiting" and room.game_task is None:
            room.game_task = asyncio.create_task(room.run_game_loop())

    elif t == "select_briscola":
        if room.phase == "briscola_selection" and room.current_player_seat == slot.seat:
            await slot.input_queue.put({"suit": data.get("suit", "bastoni")})

    elif t == "play_card":
        if room.phase == "playing" and room.current_player_seat == slot.seat:
            await slot.input_queue.put({"card": data.get("card", {})})

    elif t == "swap_seats":
        if room.status == "waiting" and slot is room.creator_slot:
            try:
                seat_a = int(data.get("seat_a", -1))
                seat_b = int(data.get("seat_b", -1))
            except (TypeError, ValueError):
                return
            if seat_a in (0, 1, 2, 3) and seat_b in (0, 1, 2, 3):
                await room.swap_seats(seat_a, seat_b)

    elif t == "ping":
        await room._send(slot.seat, {"type": "pong"})
