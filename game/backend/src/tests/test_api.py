"""Integration tests for REST endpoints and WebSocket game flow."""

import json

import pytest
from fastapi.testclient import TestClient

from aimaraffa.api import app

client = TestClient(app)


def _login(name: str = "Tester") -> dict:
    """Register a session and return ``{"uuid": ..., "player_name": ...}``."""
    return client.post("/api/login", json={"player_name": name}).json()


# ── REST: POST /api/rooms ──────────────────────────────────────────────────────

def test_create_room_returns_room_id():
    """POST /api/rooms must return a non-empty room_id string."""
    res = client.post("/api/rooms", json={"player_name": "Tester"})
    assert res.status_code == 200
    data = res.json()
    assert "room_id" in data
    assert isinstance(data["room_id"], str)
    assert len(data["room_id"]) > 0


def test_create_room_default_name():
    """POST /api/rooms with no body must still succeed."""
    res = client.post("/api/rooms", json={})
    assert res.status_code == 200
    assert "room_id" in res.json()


def test_create_room_generates_unique_ids():
    """Two successive room creations must yield different IDs."""
    id1 = client.post("/api/rooms", json={}).json()["room_id"]
    id2 = client.post("/api/rooms", json={}).json()["room_id"]
    assert id1 != id2


# ── REST: GET /api/rooms/{room_id} ─────────────────────────────────────────────

def test_get_room_after_create():
    """GET /api/rooms/{id} must return the room details after creation."""
    room_id = client.post("/api/rooms", json={}).json()["room_id"]
    res = client.get(f"/api/rooms/{room_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["room_id"] == room_id
    assert data["status"] == "waiting"
    assert isinstance(data["players"], list)


def test_get_room_not_found_returns_404():
    """GET /api/rooms/{bad_id} must return HTTP 404."""
    res = client.get("/api/rooms/NONEXISTENT-ROOM-99")
    assert res.status_code == 404


def test_get_room_case_insensitive():
    """Room lookup via GET must be case-insensitive."""
    room_id = client.post("/api/rooms", json={}).json()["room_id"]
    res = client.get(f"/api/rooms/{room_id.lower()}")
    assert res.status_code == 200


# ── WebSocket: join ────────────────────────────────────────────────────────────

def test_ws_join_receives_joined_message():
    """A player connecting via WebSocket must receive a 'joined' message."""
    user = _login("Alice")
    room_id = client.post("/api/rooms", json={}).json()["room_id"]
    with client.websocket_connect(f"/ws/{room_id}?player_name={user['player_name']}&uuid={user['uuid']}") as ws:
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "joined"
        assert msg["data"]["seat"] == 0
        assert msg["data"]["room_id"] == room_id


def test_ws_join_nonexistent_room_returns_error():
    """Connecting to a non-existent room must return an error message."""
    with client.websocket_connect("/ws/FAKE-ROOM-00?player_name=Ghost") as ws:
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "error"


def test_ws_two_players_get_different_seats():
    """Two players joining the same room must be assigned different seats."""
    alice = _login("Alice")
    bob = _login("Bob")
    room_id = client.post("/api/rooms", json={}).json()["room_id"]
    with client.websocket_connect(f"/ws/{room_id}?player_name={alice['player_name']}&uuid={alice['uuid']}") as ws1:
        seat1 = json.loads(ws1.receive_text())["data"]["seat"]

        with client.websocket_connect(f"/ws/{room_id}?player_name={bob['player_name']}&uuid={bob['uuid']}") as ws2:
            # ws1 receives a player_joined notification
            notif = json.loads(ws1.receive_text())
            assert notif["type"] == "player_joined"

            seat2 = json.loads(ws2.receive_text())["data"]["seat"]

    assert seat1 != seat2
    assert {seat1, seat2} == {0, 1}


def test_ws_room_full_returns_error():
    """Connecting to a full room (4 players) must return an error."""
    users = [_login(f"Player{i}") for i in range(5)]
    room_id = client.post("/api/rooms", json={}).json()["room_id"]
    connections = []
    try:
        for u in users[:4]:
            ws = client.websocket_connect(f"/ws/{room_id}?player_name={u['player_name']}&uuid={u['uuid']}")
            ws.__enter__()
            msg = json.loads(ws.receive_text())
            # Drain any player_joined notifications that accumulate
            assert msg["type"] == "joined"
            connections.append(ws)

        # Fifth player should be rejected
        u5 = users[4]
        with client.websocket_connect(f"/ws/{room_id}?player_name={u5['player_name']}&uuid={u5['uuid']}") as ws5:
            msg = json.loads(ws5.receive_text())
            assert msg["type"] == "error"
    finally:
        for ws in connections:
            try:
                ws.__exit__(None, None, None)
            except Exception:
                pass


def test_ws_ping_returns_pong():
    """Sending a ping message must elicit a pong response."""
    user = _login("Pinger")
    room_id = client.post("/api/rooms", json={}).json()["room_id"]
    with client.websocket_connect(f"/ws/{room_id}?player_name={user['player_name']}&uuid={user['uuid']}") as ws:
        joined = json.loads(ws.receive_text())
        assert joined["type"] == "joined"
        # Drain the player_joined broadcast the server sends to all slots
        _notif = json.loads(ws.receive_text())
        assert _notif["type"] == "player_joined"
        ws.send_text(json.dumps({"type": "ping"}))
        pong = json.loads(ws.receive_text())
        assert pong["type"] == "pong"


def test_http_ping_returns_ok():
    """The REST ping endpoint must return an OK payload."""
    res = client.get("/api/ping")
    assert res.status_code == 200
    assert res.json() == {"ok": True}


def test_only_owner_can_start_game():
    """A non-owner start_game message must not transition room status to in_game."""
    owner_login = client.post("/api/login", json={"player_name": "Owner"}).json()
    guest_login = client.post("/api/login", json={"player_name": "Guest"}).json()
    room_id = client.post("/api/rooms", json={"player_name": "Owner"}).json()["room_id"]
    try:
        with client.websocket_connect(
            f"/ws/{room_id}?player_name={owner_login['player_name']}&uuid={owner_login['uuid']}"
        ) as ws_owner:
            owner_joined = json.loads(ws_owner.receive_text())
            assert owner_joined["type"] == "joined"
            assert owner_joined["data"]["seat"] == 0

            with client.websocket_connect(
                f"/ws/{room_id}?player_name={guest_login['player_name']}&uuid={guest_login['uuid']}"
            ) as ws_guest:
                guest_joined = json.loads(ws_guest.receive_text())
                assert guest_joined["type"] == "joined"
                assert guest_joined["data"]["seat"] == 1

                owner_notice = json.loads(ws_owner.receive_text())
                assert owner_notice["type"] == "player_joined"

                ws_guest.send_text(json.dumps({"type": "start_game"}))

                room_state = client.get(f"/api/rooms/{room_id}").json()
                assert room_state["status"] == "waiting"
    finally:
        client.post("/api/logout", json={"uuid": owner_login["uuid"]})
        client.post("/api/logout", json={"uuid": guest_login["uuid"]})


# ── WebSocket: full game flow (1 human + 3 bots) ──────────────────────────────

def test_ws_full_game_reaches_game_over():
    """Starting a game with 1 human and 3 bots must eventually emit game_over."""
    user = _login("Solo")
    room_id = client.post("/api/rooms", json={}).json()["room_id"]
    received: list[dict] = []

    with client.websocket_connect(f"/ws/{room_id}?player_name={user['player_name']}&uuid={user['uuid']}") as ws:
        joined = json.loads(ws.receive_text())
        assert joined["type"] == "joined"
        my_seat: int = joined["data"]["seat"]

        ws.send_text(json.dumps({"type": "start_game"}))

        for _ in range(3000):
            try:
                msg = json.loads(ws.receive_text())
            except Exception:
                break

            received.append(msg)

            if msg["type"] == "game_state":
                phase = msg["data"]["phase"]
                current = msg["data"]["current_player_seat"]

                if phase == "briscola_selection" and current == my_seat:
                    ws.send_text(json.dumps({
                        "type": "select_briscola",
                        "data": {"suit": "bastoni"},
                    }))

                elif phase == "playing" and current == my_seat:
                    playable = [c for c in msg["data"]["my_hand"] if c["playable"]]
                    if playable:
                        ws.send_text(json.dumps({
                            "type": "play_card",
                            "data": {"card": {"suit": playable[0]["suit"], "rank": playable[0]["rank"]}},
                        }))

            elif msg["type"] == "game_over":
                break

    message_types = [m["type"] for m in received]
    assert "game_over" in message_types, f"game_over not received; last types: {message_types[-10:]}"

    game_over_msg = next(m for m in received if m["type"] == "game_over")
    winner = game_over_msg["data"]["winner_team"]
    assert winner in (1, 2)
    assert game_over_msg["data"]["scores"][str(winner)] > 41
