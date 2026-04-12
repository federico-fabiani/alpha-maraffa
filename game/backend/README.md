# aimaraffa – backend

FastAPI WebSocket server for **Marafone** (also called Beccaccino), an Italian 4-player card game.

## Quick start

```bash
uv run uvicorn aimaraffa.api:app --reload
```

## Run tests

```bash
uv run pytest
```

## Simulate a full game (all bots, no WebSocket)

```bash
uv run python src/scripts/simulate_game.py
```

## Structure

```
src/
├── aimaraffa/          # main package
│   ├── config.py       # pydantic-settings configuration
│   ├── names.py        # random Italian name generator
│   ├── engine.py       # game logic, room management, bot AI
│   └── api.py          # FastAPI app (REST + WebSocket)
├── tests/
│   ├── conftest.py
│   ├── test_engine.py  # unit tests
│   └── test_api.py     # integration tests (REST + WS + full game flow)
└── scripts/
    └── simulate_game.py
```

## Game rules (Marafone)

- 4 players split into 2 teams (seats 0,2 vs 1,3)
- 40-card Italian deck (4 suits × ranks 1–10)
- Player holding the **4 of Denara** selects the trump suit (*briscola*)
- Players must follow the lead suit when possible
- First team to reach **41 points** wins

---

## REST API

### `POST /api/rooms`

Create a new game room.

**Request body**
```json
{ "player_name": "Giocatore" }
```
`player_name` is optional (default `"Giocatore"`); it is not assigned to a seat here — seats are claimed via WebSocket.

**Response `200`**
```json
{ "room_id": "ROSSO-LUPO-42" }
```

---

### `GET /api/rooms/{room_id}`

Fetch current room state. The lookup is case-insensitive.

**Response `200`**
```json
{
  "room_id": "ROSSO-LUPO-42",
  "status": "waiting",
  "players": [
    { "seat": 0, "name": "Alice", "is_bot": false },
    { "seat": 1, "name": "Nonno Gino", "is_bot": true }
  ]
}
```

`status` is one of `"waiting"` | `"in_game"` | `"game_over"`.

**Response `404`** – room not found.

---

## WebSocket API

```
ws://<host>/ws/{room_id}?player_name=<name>
```

All frames are JSON objects with a `type` field and a `data` field.

### Connection behaviour

| Situation | Result |
|-----------|--------|
| Room is `waiting`, seat available | Player is assigned the next free seat (0→3) |
| Room is `waiting`, all 4 seats taken | Server sends `error` and closes the connection |
| Room is `in_game`, name matches a disconnected human slot | Reconnection: server sends `reconnected` + current `game_state` |
| Room is `in_game`, no matching disconnected slot | Server sends `error` and closes the connection |
| Room ID not found | Server sends `error` and closes the connection |

---

### Client → Server messages

#### `start_game`
Start the game. Ignored unless the room is `waiting` and the game has not yet started. Empty seats are automatically filled with bots.

```json
{ "type": "start_game" }
```

---

#### `select_briscola`
Choose the trump suit. Only accepted when `phase == "briscola_selection"` and it is the sender's turn.

```json
{
  "type": "select_briscola",
  "data": { "suit": "bastoni" }
}
```

`suit` — one of `"bastoni"` | `"denara"` | `"spade"` | `"coppe"`.

---

#### `play_card`
Play a card from hand. Only accepted when `phase == "playing"` and it is the sender's turn. If the card is invalid (not in hand or breaks the lead-suit rule) the server substitutes the first legal card.

```json
{
  "type": "play_card",
  "data": {
    "card": { "suit": "bastoni", "rank": 1 }
  }
}
```

---

#### `ping`
Keepalive probe.

```json
{ "type": "ping" }
```

---

### Server → Client messages

#### `joined`
Sent to the connecting player after a successful join.

```json
{
  "type": "joined",
  "data": {
    "seat": 0,
    "room_id": "ROSSO-LUPO-42",
    "players": [
      { "seat": 0, "name": "Alice", "is_bot": false, "team": 1 }
    ]
  }
}
```

---

#### `player_joined`
Broadcast to all connected players (including the one who just joined) when a new player takes a seat.

```json
{
  "type": "player_joined",
  "data": {
    "seat": 1,
    "name": "Bob",
    "players": [ ... ]
  }
}
```

---

#### `player_disconnected`
Broadcast when a human player's WebSocket closes mid-game.

```json
{
  "type": "player_disconnected",
  "data": { "seat": 2, "name": "Carlo" }
}
```

---

#### `reconnected`
Sent to a player who successfully reconnects to an in-progress game. Followed immediately by a `game_state` message.

```json
{
  "type": "reconnected",
  "data": { "seat": 0 }
}
```

---

#### `game_started`
Broadcast when the game loop begins (after `start_game`). Contains the full player list including bots that were added to fill empty seats.

```json
{
  "type": "game_started",
  "data": {
    "players": [
      { "seat": 0, "name": "Alice", "team": 1, "is_bot": false },
      { "seat": 1, "name": "Nonno Gino", "team": 2, "is_bot": true },
      { "seat": 2, "name": "Nonna Rosa", "team": 1, "is_bot": true },
      { "seat": 3, "name": "Nonno Aldo", "team": 2, "is_bot": true }
    ]
  }
}
```

---

#### `game_state`
Sent to each human player individually whenever the active seat or phase changes. Each player receives a personalised view (their own hand with playability flags, not other players' cards).

```json
{
  "type": "game_state",
  "data": {
    "phase": "playing",
    "round": 1,
    "turn": 3,
    "briscola": "bastoni",
    "briscola_selector_seat": 2,
    "current_player_seat": 0,
    "table_cards": [
      { "seat": 2, "card": { "suit": "denara", "rank": 7 } }
    ],
    "my_hand": [
      { "suit": "bastoni", "rank": 1, "playable": true },
      { "suit": "coppe",   "rank": 5, "playable": false }
    ],
    "players": [
      {
        "seat": 0, "name": "Alice", "team": 1, "cards_count": 7,
        "is_you": true, "is_bot": false, "is_connected": true
      }
    ],
    "total_scores":  { "1": 12, "2": 8 },
    "round_scores":  { "1": 3.0, "2": 2.0 },
    "last_turn_winner": 2
  }
}
```

`phase` — one of `"waiting"` | `"briscola_selection"` | `"playing"` | `"turn_result"` | `"round_end"` | `"game_over"`.  
`playable: true` means the card may legally be played this turn (only set for the active player).

---

#### `briscola_set`
Broadcast after the trump suit is chosen.

```json
{
  "type": "briscola_set",
  "data": {
    "suit": "bastoni",
    "by_seat": 2,
    "by_name": "Alice"
  }
}
```

---

#### `card_played`
Broadcast each time any player places a card on the table.

```json
{
  "type": "card_played",
  "data": {
    "seat": 0,
    "name": "Alice",
    "card": { "suit": "bastoni", "rank": 1 },
    "table": [
      { "seat": 2, "card": { "suit": "denara", "rank": 7 } },
      { "seat": 3, "card": { "suit": "denara", "rank": 4 } },
      { "seat": 0, "card": { "suit": "bastoni", "rank": 1 } }
    ],
    "hands_count": { "0": 7, "1": 8, "2": 7, "3": 7 }
  }
}
```

---

#### `turn_result`
Broadcast after all 4 cards of a turn have been played.

```json
{
  "type": "turn_result",
  "data": {
    "winner_seat": 0,
    "winner_name": "Alice",
    "winner_team": 1,
    "points": 1.34,
    "table": [ ... ],
    "round_scores": { "1": 5.0, "2": 2.0 }
  }
}
```

---

#### `round_end`
Broadcast at the end of each round (after the last `turn_result`).

```json
{
  "type": "round_end",
  "data": {
    "round": 1,
    "round_scores": { "1": 6, "2": 5 },
    "total_scores": { "1": 6, "2": 5 }
  }
}
```

`round_scores` are floored integers. They always sum to 11.

---

#### `game_over`
Broadcast when a team exceeds 41 total points.

```json
{
  "type": "game_over",
  "data": {
    "winner_team": 1,
    "scores": { "1": 44, "2": 32 }
  }
}
```

---

#### `pong`
Response to a `ping`.

```json
{ "type": "pong" }
```

---

#### `error`
Sent when a connection is rejected or an internal error occurs. The connection is closed immediately after.

```json
{
  "type": "error",
  "data": { "message": "Stanza non trovata" }
}
```
