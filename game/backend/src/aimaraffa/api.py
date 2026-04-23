"""FastAPI application: REST room management and WebSocket game server."""

import asyncio
import json
import logging
import uuid as uuid_module
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from aimaraffa.config import settings
import aimaraffa.engine as eng
from aimaraffa.engine import GameRoom, PlayerSlot, RoomManager
from aimaraffa.names import Genre, pick_a_name

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ml_model_path:
        eng.init_ml_bot(settings.ml_model_path)
        logger.info("ML bot enabled — model: %s", settings.ml_model_path)
    else:
        logger.info("ML bot disabled — bots use random strategy")
    yield


app = FastAPI(title="Marafone Digital", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rooms = RoomManager()
STATIC_DIR = Path(__file__).resolve().parent / "static"
FRONTEND_APP_SHELL_FILES = frozenset({"index.html", "sw.js", "registerSW.js", "manifest.webmanifest"})


def _frontend_file_response(file_path: Path) -> FileResponse:
    cache_control = None
    if file_path.name in FRONTEND_APP_SHELL_FILES or file_path.suffix == ".html":
        cache_control = "no-cache, max-age=0, must-revalidate"

    headers = {"Cache-Control": cache_control} if cache_control else None
    return FileResponse(file_path, headers=headers)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="frontend-static")
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")


# ── User registry ──────────────────────────────────────────────────────────────

class UserRegistry:
    """Tracks active sessions and banned UUIDs."""

    def __init__(self):
        self._active: dict[str, str] = {}   # uuid → display name
        self._banned: set[str] = set()

    def login(self, requested_name: str) -> tuple[str, str]:
        """Create a new session."""
        uid = str(uuid_module.uuid4())
        genre = Genre.MASCULINE if uid[-1] in "01234567" else Genre.FEMININE
        title = "Nonno" if genre == Genre.MASCULINE else "Nonna"
        name = requested_name.strip() or f"{title} {pick_a_name(genre)}"
        self._active[uid] = name
        return uid, name

    def logout(self, uid: str) -> None:
        self._active.pop(uid, None)

    def is_active(self, uid: str) -> bool:
        return uid in self._active

    def is_banned(self, uid: str) -> bool:
        return uid in self._banned

    def ban(self, uid: str) -> None:
        self._active.pop(uid, None)
        self._banned.add(uid)


registry = UserRegistry()


# ── REST endpoints ─────────────────────────────────────────────────────────────

class CreateRoomBody(BaseModel):
    """Request body for POST /api/rooms."""

    player_name: str = "Giocatore"


class LoginBody(BaseModel):
    """Request body for POST /api/login."""

    player_name: str = ""


class LogoutBody(BaseModel):
    """Request body for POST /api/logout."""

    uuid: str


@app.post("/api/login")
async def login(body: LoginBody):
    """Register a new session. Returns uuid + assigned player name."""
    uid, name = registry.login(body.player_name)
    logger.info("Login: %s (%s)", name, uid)
    return {"uuid": uid, "player_name": name}


@app.post("/api/logout")
async def logout(body: LogoutBody):
    """Invalidate a session UUID."""
    registry.logout(body.uuid)
    return {"ok": True}


@app.post("/api/rooms")
async def create_room(body: CreateRoomBody):
    """Create a new game room and return its ID."""
    rooms.purge_finished()
    if len(rooms.rooms) >= settings.max_rooms:
        raise HTTPException(status_code=503, detail="Server pieno: troppe stanze aperte, riprova pi\u00f9 tardi")
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


@app.get("/api/ping")
async def ping():
    """Liveness probe used by frontend bootstrap."""
    return {"ok": True}


# ── WebSocket endpoint ─────────────────────────────────────────────────────────

@app.websocket("/ws/{room_id}")
async def ws_endpoint(websocket: WebSocket, room_id: str, player_name: str = "Giocatore", uuid: str = ""):
    """Handle WebSocket connections: join a waiting room or reconnect to an in-game room."""
    await websocket.accept()

    # ── Auth checks ────────────────────────────────────────────────────────────
    if registry.is_banned(uuid):
        await websocket.send_text(json.dumps({"type": "error", "data": {"message": "Sei stato bandito da questa partita"}}))
        await websocket.close()
        return

    room = rooms.get(room_id)
    if not room:
        await websocket.send_text(json.dumps({"type": "error", "data": {"message": "Stanza non trovata"}}))
        await websocket.close()
        return

    my_slot: PlayerSlot = None

    if room.status == "in_game":
        # Reconnection: prefer matching by UUID, fall back to name for backward compatibility
        for slot in room.slots.values():
            if not slot.is_bot and not slot.is_connected and slot.uuid == uuid:
                my_slot = slot
                break
        if my_slot is None:
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
        if not registry.is_active(uuid):
            await websocket.send_text(json.dumps({"type": "error", "data": {"message": "Sessione non valida, ricarica la pagina"}}))
            await websocket.close()
            return

        taken = set(room.slots.keys())
        seat = next((s for s in range(4) if s not in taken), None)
        if seat is None:
            await websocket.send_text(json.dumps({"type": "error", "data": {"message": "Stanza piena"}}))
            await websocket.close()
            return

        my_slot = PlayerSlot(seat=seat, name=player_name, is_bot=False)
        my_slot.uuid = uuid
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
            "data": {"seat": seat, "room_id": room.room_id, "players": player_list, "owner_seat": room.creator_slot.seat},
        }))
        await room.broadcast({
            "type": "player_joined",
            "data": {"seat": seat, "name": player_name, "players": player_list, "owner_seat": room.creator_slot.seat},
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
            if not room.slots:
                rooms.delete(room.room_id)
                logger.info("Room %s deleted (empty)", room_id)
                return
            # Promote the most recently joined human to owner if the owner left
            if my_slot is room.creator_slot:
                humans = [sl for sl in room.slots.values() if not sl.is_bot]
                if humans:
                    room.creator_slot = max(humans, key=lambda sl: sl.seat)
            player_list = [
                {"seat": s, "name": sl.name, "is_bot": sl.is_bot, "team": sl.team}
                for s, sl in sorted(room.slots.items())
            ]
            await room.broadcast({
                "type": "player_left",
                "data": {
                    "seat": my_slot.seat,
                    "name": my_slot.name,
                    "players": player_list,
                    "owner_seat": room.creator_slot.seat if room.creator_slot else None,
                },
            })
        else:
            await room.broadcast({"type": "player_disconnected", "data": {"seat": my_slot.seat, "name": my_slot.name}})
        logger.info("%s disconnected from %s", my_slot.name, room_id)


async def _handle(room: GameRoom, slot: PlayerSlot, msg: dict) -> None:
    """Dispatch an incoming WebSocket message to the appropriate handler."""
    t = msg.get("type")
    data = msg.get("data", {})

    if t == "start_game":
        if room.status == "waiting" and room.game_task is None and slot is room.creator_slot:
            room.game_task = asyncio.create_task(room.run_game_loop())

    elif t == "select_briscola":
        if room.phase == "briscola_selection" and room.current_player_seat == slot.seat:
            await slot.input_queue.put({"suit": data.get("suit", "bastoni")})

    elif t == "play_card":
        if room.phase == "playing" and room.current_player_seat == slot.seat:
            await slot.input_queue.put({
                "card": data.get("card", {}),
                "declaration": data.get("declaration"),
            })

    elif t == "swap_seats":
        if room.status == "waiting" and slot is room.creator_slot:
            try:
                seat_a = int(data.get("seat_a", -1))
                seat_b = int(data.get("seat_b", -1))
            except (TypeError, ValueError):
                return
            if seat_a in (0, 1, 2, 3) and seat_b in (0, 1, 2, 3):
                await room.swap_seats(seat_a, seat_b)

    elif t == "kick":
        if room.status == "waiting" and slot is room.creator_slot:
            try:
                target_seat = int(data.get("seat", -1))
            except (TypeError, ValueError):
                return
            target = room.slots.get(target_seat)
            if target is None or target.is_bot or target is room.creator_slot:
                return
            # Ban UUID, then clean up before closing WS to prevent double-cleanup
            registry.ban(target.uuid)
            target.is_connected = False
            target_ws = target.websocket
            target.websocket = None
            room.slots.pop(target_seat, None)
            if target_ws:
                try:
                    await target_ws.send_text(json.dumps({"type": "kicked", "data": {"message": "Sei stato espulso dalla stanza"}}))
                    await target_ws.close()
                except Exception:
                    pass
            player_list = [
                {"seat": s, "name": sl.name, "is_bot": sl.is_bot, "team": sl.team}
                for s, sl in sorted(room.slots.items())
            ]
            await room.broadcast({"type": "player_left", "data": {"seat": target_seat, "name": target.name, "players": player_list}})
            logger.info("%s kicked %s (uuid %s) from %s", slot.name, target.name, target.uuid, room.room_id)

    elif t == "promote":
        if room.status == "waiting" and slot is room.creator_slot:
            try:
                target_seat = int(data.get("seat", -1))
            except (TypeError, ValueError):
                return
            target = room.slots.get(target_seat)
            if target is None or target.is_bot or target is room.creator_slot:
                return
            room.creator_slot = target
            player_list = [
                {"seat": s, "name": sl.name, "is_bot": sl.is_bot, "team": sl.team}
                for s, sl in sorted(room.slots.items())
            ]
            await room.broadcast({
                "type": "owner_changed",
                "data": {"owner_seat": target_seat, "players": player_list},
            })
            logger.info("%s promoted %s to owner in %s", slot.name, target.name, room.room_id)

    elif t == "ping":
        await room._send(slot.seat, {"type": "pong"})

    elif t == "forfeit":
        if room.status == "in_game" and not slot.is_bot:
            await room.forfeit(slot)


@app.get("/", include_in_schema=False)
async def frontend_index():
    """Serve the built SPA index when frontend assets are available."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend static files not found")
    return _frontend_file_response(index_file)


@app.get("/{full_path:path}", include_in_schema=False)
async def frontend_spa_fallback(full_path: str):
    """Serve static files and fallback to index.html for SPA routes."""
    reserved_prefixes = ("api", "ws", "docs", "redoc", "openapi.json", "static", "assets")
    if full_path.startswith(reserved_prefixes):
        raise HTTPException(status_code=404, detail="Not found")

    requested_file = STATIC_DIR / full_path
    if requested_file.is_file():
        return _frontend_file_response(requested_file)

    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return _frontend_file_response(index_file)

    raise HTTPException(status_code=404, detail="Frontend static files not found")
