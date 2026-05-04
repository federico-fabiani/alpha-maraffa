"""Core game engine: cards, deck, game rooms, bot AI, and room manager."""

import asyncio
import json
import random
import time
from enum import Enum
from math import floor
from typing import Dict, List, Optional, Tuple

from aimaraffa.names import random_bot_name


# ── Card primitives ────────────────────────────────────────────────────────────

class Suit(Enum):
    """The four Italian card suits."""

    BASTONI = "bastoni"
    DENARA  = "denara"
    SPADE   = "spade"
    COPPE   = "coppe"


class Card:
    """A single playing card identified by suit and rank (1–10)."""

    def __init__(self, suit: Suit, rank: int):
        """Create a card with the given suit and rank."""
        self.suit = suit
        self.rank = rank

    def __eq__(self, other: object) -> bool:
        """Two cards are equal when both suit and rank match."""
        return isinstance(other, Card) and self.suit == other.suit and self.rank == other.rank

    def __hash__(self) -> int:
        """Hash by (suit, rank) so cards can be stored in sets/dicts."""
        return hash((self.suit, self.rank))

    def __repr__(self) -> str:
        """Short human-readable representation."""
        return f"{self.rank}/{self.suit.value}"


class Deck:
    """A 40-card Italian deck (4 suits × ranks 1–10)."""

    def __init__(self):
        """Build a fresh ordered deck."""
        self.cards: List[Card] = [Card(s, r) for s in Suit for r in range(1, 11)]

    def shuffle(self, rng=None) -> None:
        """Shuffle the deck in place. Pass an explicit rng for reproducibility."""
        if rng is not None:
            rng.shuffle(self.cards)
        else:
            random.shuffle(self.cards)

    def deal(self, n: int) -> List[Card]:
        """Remove and return the top n cards from the deck."""
        dealt, self.cards = self.cards[:n], self.cards[n:]
        return dealt


# ── Game constants ─────────────────────────────────────────────────────────────

RANK_TO_VALUE: Dict[int, int] = {
    1: 11, 2: 12, 3: 13, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9, 10: 10,
}
RANK_TO_POINTS: Dict[int, float] = {
    1: 1.0, 2: 0.34, 3: 0.34, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0.34, 9: 0.34, 10: 0.34,
}
KEY_CARD               = Card(Suit.DENARA, 4)   # holder selects the briscola in round 1
GAME_WIN_THRESHOLD     = 41
BOT_PLAY_DELAY         = 1.0    # seconds before a bot plays a card
BOT_THINK_DELAY        = 0.5    # seconds before a bot selects briscola
BOT_BRISCOLA_THINK_DELAY = 4.0  # seconds before a bot selects briscola (allows popup to show)
TURN_RESULT_PAUSE      = 2.0    # seconds to display who won a turn
ROUND_END_PAUSE        = 3.5    # seconds to display round summary
HUMAN_TURN_TIMEOUT     = 30.0   # seconds a human has to play before auto-play
MAX_CONSECUTIVE_MISSED = 3      # forfeit if missed this many turns in a row
MAX_TOTAL_MISSED       = 3      # forfeit if missed this many turns total

_VALID_DECLARATIONS = frozenset({"busso", "striscio", "volo"})


class ForfeitError(Exception):
    """Raised inside the game loop when a player forfeits due to inactivity."""

    def __init__(self, slot: "PlayerSlot"):
        self.slot = slot
        super().__init__(f"{slot.name} ha abbandonato per inattivit\u00e0")

# ── Bot strategy selection ─────────────────────────────────────────────────────

_LIVE_BOT_POLICY = "heuristic"
_LIVE_BOT_MODEL_PATH = ""


def configure_live_bot(policy: str, model_path: str = "") -> None:
    """Configure which agent implementation live game rooms should use for bots."""
    normalized = (policy or "heuristic").strip().lower()
    if normalized not in {"heuristic", "random", "ml"}:
        raise ValueError(f"Unknown live bot policy: {policy}")
    if normalized == "ml" and not model_path:
        raise ValueError("ML live bot policy requires a model path")

    global _LIVE_BOT_POLICY, _LIVE_BOT_MODEL_PATH
    _LIVE_BOT_POLICY = normalized
    _LIVE_BOT_MODEL_PATH = model_path


def _create_live_bot_agent():
    """Build a fresh live bot agent instance for one game room."""
    from aimaraffa.agents.factory import create_agent

    return create_agent(_LIVE_BOT_POLICY, model_path=_LIVE_BOT_MODEL_PATH)

_ROOM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_ROOM_CODE_LENGTH = 4


# ── Pure helper functions ──────────────────────────────────────────────────────

def generate_room_code() -> str:
    """Generate a 4-character uppercase room code without ambiguous glyphs."""
    return "".join(random.choice(_ROOM_CODE_ALPHABET) for _ in range(_ROOM_CODE_LENGTH))


def card_to_dict(card: Card) -> dict:
    """Serialize a Card to a JSON-safe dict."""
    return {"suit": card.suit.value, "rank": card.rank}


def dict_to_card(d: dict) -> Optional[Card]:
    """Deserialize a dict to a Card; returns None on invalid input."""
    try:
        suit = Suit(d["suit"].lower())
        return Card(suit, int(d["rank"]))
    except Exception:
        return None


def get_valid_cards(hand: List[Card], lead_suit: Optional[Suit]) -> List[Card]:
    """Return the subset of cards the player is allowed to play given the lead suit."""
    if lead_suit is None:
        return hand.copy()
    matching = [c for c in hand if c.suit == lead_suit]
    return matching if matching else hand.copy()


def get_valid_declarations(
    hand_after_play: List[Card],
    lead_card_suit: Suit,
) -> List[Optional[str]]:
    """Return valid declarations for the player opening a trick.

    striscio/volo encode factual hand state and must be truthful; busso is a
    strategic invitation and is always valid.  Caller passes the hand *after*
    removing the played card so the remaining suit count is correct.
    """
    remaining = sum(1 for c in hand_after_play if c.suit == lead_card_suit)
    decls: List[Optional[str]] = [None, "busso"]
    decls.append("striscio" if remaining > 0 else "volo")
    return decls


def determine_turn_winner(seat_cards: List[Tuple[int, Card]], briscola: Suit) -> int:
    """Return the seat number of the player who wins this turn."""
    lead_suit = seat_cards[0][1].suit

    def power(card: Card) -> int:
        """Compute card strength: briscola beats lead suit, off-suit loses."""
        if card.suit == briscola:
            return RANK_TO_VALUE[card.rank] + 100
        if card.suit == lead_suit:
            return RANK_TO_VALUE[card.rank]
        return 0

    winner_idx = max(range(len(seat_cards)), key=lambda i: power(seat_cards[i][1]))
    return seat_cards[winner_idx][0]

# ── Room entities ──────────────────────────────────────────────────────────────

class PlayerSlot:
    """One of the four seats in a game room, holding per-player state."""

    def __init__(self, seat: int, name: str, is_bot: bool = False):
        """Initialise a slot; bots start as 'connected', humans start disconnected."""
        self.seat = seat
        self.name = name
        self.is_bot = is_bot
        self.uuid: str = ""
        self.is_connected: bool = not is_bot
        self.hand: List[Card] = []
        self.websocket = None
        self.input_queue: asyncio.Queue = asyncio.Queue()
        self.consecutive_missed: int = 0
        self.total_missed: int = 0

    @property
    def team(self) -> int:
        """Seats 0 and 2 belong to team 1; seats 1 and 3 belong to team 2."""
        return 1 if self.seat in (0, 2) else 2


class GameRoom:
    """Manages the full lifecycle and mutable state for one game room."""

    def __init__(self, room_id: str):
        """Initialise a new room in the 'waiting' state."""
        self.room_id = room_id
        self.slots: Dict[int, PlayerSlot] = {}
        self.status = "waiting"
        self.game_task: Optional[asyncio.Task] = None
        self.creator_slot: Optional["PlayerSlot"] = None  # first human to join

        self.total_scores: Dict[int, int] = {1: 0, 2: 0}
        self.round_scores: Dict[int, float] = {1: 0.0, 2: 0.0}
        self.round_num = 0
        self.turn_num = 0
        self.briscola: Optional[Suit] = None
        self.briscola_selector_seat: Optional[int] = None
        self.current_player_seat: Optional[int] = None
        self.table_cards: List[Tuple[int, Card]] = []
        self.last_turn_winner_seat: Optional[int] = None
        self.current_declaration: Optional[str] = None
        self.phase = "waiting"
        self._maraffa_forced: bool = False  # selector must lead with briscola ace
        self.current_turn_deadline: Optional[float] = None
        self._bot_agent = None

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _rotate_seats(self, start: int) -> List[int]:
        """Return seat order starting from 'start', wrapping around."""
        seats = sorted(self.slots.keys())
        idx = seats.index(start)
        return seats[idx:] + seats[:idx]

    def _build_bot_context(self, seat: int) -> dict:
        """Build the decision context shared by heuristic and ML agents."""
        return {
            "seat": seat,
            "round_num": self.round_num,
            "turn_num": self.turn_num,
            "briscola_selector_seat": self.briscola_selector_seat,
            "table_cards": list(self.table_cards),
            "round_scores": {k: round(v, 2) for k, v in self.round_scores.items()},
            "total_scores": dict(self.total_scores),
            "hand": self.slots[seat].hand,
        }

    def _get_bot_agent(self):
        """Return the room-scoped live agent used for bots and timeout auto-play."""
        if self._bot_agent is None:
            self._bot_agent = _create_live_bot_agent()
        return self._bot_agent

    def _build_state(self, for_seat: int, phase: str = None) -> dict:
        """Build the personalised game_state payload for a specific seat."""
        slot = self.slots[for_seat]
        lead_suit = self.table_cards[0][1].suit if self.table_cards else None

        valid_set: set = set()
        if self.current_player_seat == for_seat and self.phase == "playing":
            if self._maraffa_forced and for_seat == self.briscola_selector_seat and lead_suit is None:
                valid_set = {(self.briscola.value, 1)}
            else:
                valid_set = {(c.suit.value, c.rank) for c in get_valid_cards(slot.hand, lead_suit)}

        my_hand = [
            {**card_to_dict(c), "playable": (c.suit.value, c.rank) in valid_set}
            for c in slot.hand
        ]
        players = [
            {
                "seat": s,
                "name": sl.name,
                "team": sl.team,
                "cards_count": len(sl.hand),
                "is_you": s == for_seat,
                "is_bot": sl.is_bot,
                "is_connected": sl.is_connected,
            }
            for s, sl in sorted(self.slots.items())
        ]
        return {
            "type": "game_state",
            "data": {
                "phase": phase or self.phase,
                "round": self.round_num,
                "turn": self.turn_num,
                "briscola": self.briscola.value if self.briscola else None,
                "briscola_selector_seat": self.briscola_selector_seat,
                "current_player_seat": self.current_player_seat,
                "table_cards": [{"seat": s, "card": card_to_dict(c)} for s, c in self.table_cards],
                "my_hand": my_hand,
                "players": players,
                "total_scores": self.total_scores,
                "round_scores": {k: round(v, 2) for k, v in self.round_scores.items()},
                "last_turn_winner": self.last_turn_winner_seat,
                "current_declaration": self.current_declaration,
                "turn_deadline": self.current_turn_deadline,
            },
        }

    # ── Seat management ────────────────────────────────────────────────────────

    async def swap_seats(self, seat_a: int, seat_b: int) -> None:
        """Swap or move slots between two seats (waiting phase only). Either seat may be empty."""
        if self.status != "waiting" or seat_a == seat_b:
            return
        slot_a = self.slots.get(seat_a)
        slot_b = self.slots.get(seat_b)
        if slot_a is None and slot_b is None:
            return

        # Update .seat on each slot, then update the dict
        if slot_a is not None:
            slot_a.seat = seat_b
            self.slots[seat_b] = slot_a
        else:
            del self.slots[seat_b]   # seat_b player moved away, vacate

        if slot_b is not None:
            slot_b.seat = seat_a
            self.slots[seat_a] = slot_b
        else:
            del self.slots[seat_a]   # seat_a player moved away, vacate
        player_list = [
            {"seat": s, "name": sl.name, "is_bot": sl.is_bot, "team": sl.team}
            for s, sl in sorted(self.slots.items())
        ]
        await self.broadcast({
            "type": "seats_swapped",
            "data": {
                "seat_a": seat_a,
                "seat_b": seat_b,
                "players": player_list,
                "owner_seat": self.creator_slot.seat if self.creator_slot else None,
            },
        })

    # ── Networking ─────────────────────────────────────────────────────────────

    async def _send(self, seat: int, msg: dict) -> None:
        """Send a JSON message to one connected human player; marks disconnected on error."""
        slot = self.slots.get(seat)
        if slot and not slot.is_bot and slot.is_connected and slot.websocket:
            try:
                await slot.websocket.send_text(json.dumps(msg))
            except Exception:
                slot.is_connected = False

    async def broadcast(self, msg: dict) -> None:
        """Send a message to all connected human players."""
        for seat in self.slots:
            await self._send(seat, msg)

    async def broadcast_state(self, phase: str = None) -> None:
        """Send a personalised game_state to every connected human player."""
        for seat, slot in self.slots.items():
            if not slot.is_bot and slot.is_connected and slot.websocket:
                await self._send(seat, self._build_state(seat, phase))

    # ── Forfeit ────────────────────────────────────────────────────────────────

    async def forfeit(self, by_slot: "PlayerSlot") -> None:
        """Immediately end the game, awarding victory to the opposing team."""
        if self.status != "in_game":
            return
        loser_team = by_slot.team
        winner_team = 2 if loser_team == 1 else 1
        self.phase = "game_over"
        self.status = "game_over"
        await self.broadcast({
            "type": "game_over",
            "data": {
                "winner_team": winner_team,
                "scores": self.total_scores,
                "forfeit_by": by_slot.name,
                "forfeit_seat": by_slot.seat,
            },
        })
        if self.game_task and not self.game_task.done():
            self.game_task.cancel()

    # ── Input awaiting ─────────────────────────────────────────────────────────

    async def _await_briscola(self, seat: int) -> Suit:
        """Wait for the player's briscola choice, or generate one for a bot."""
        slot = self.slots[seat]
        if slot.is_bot:
            await asyncio.sleep(BOT_BRISCOLA_THINK_DELAY)
            ctx = self._build_bot_context(seat)
            return self._get_bot_agent().select_briscola(ctx)
        try:
            payload = await asyncio.wait_for(slot.input_queue.get(), timeout=HUMAN_TURN_TIMEOUT)
            slot.consecutive_missed = 0
            return Suit(payload["suit"].lower())
        except asyncio.TimeoutError:
            slot.consecutive_missed += 1
            slot.total_missed += 1
            await self.broadcast({
                "type": "player_timeout",
                "data": {
                    "seat": slot.seat,
                    "name": slot.name,
                    "consecutive": slot.consecutive_missed,
                    "total": slot.total_missed,
                },
            })
            if slot.consecutive_missed >= MAX_CONSECUTIVE_MISSED or slot.total_missed >= MAX_TOTAL_MISSED:
                raise ForfeitError(slot)
            return self._get_bot_agent().select_briscola(self._build_bot_context(seat))

    async def _await_card(self, seat: int) -> Tuple[Card, Optional[str]]:
        """Wait for the player's card play; returns (card, declaration) where declaration is
        only meaningful for the lead player and None for all other players and bots."""
        slot = self.slots[seat]
        lead_suit = self.table_cards[0][1].suit if self.table_cards else None

        # Maraffa rule: briscola selector must open the first trick with the briscola ace
        if self._maraffa_forced and seat == self.briscola_selector_seat and lead_suit is None:
            self._maraffa_forced = False
            forced_card = Card(self.briscola, 1)
            if slot.is_bot:
                await asyncio.sleep(BOT_PLAY_DELAY)
                return forced_card, None
            # Human: consume their input but silently override the card
            try:
                payload = await asyncio.wait_for(slot.input_queue.get(), timeout=HUMAN_TURN_TIMEOUT)
                slot.consecutive_missed = 0
                declaration = payload.get("declaration")
            except asyncio.TimeoutError:
                slot.consecutive_missed += 1
                slot.total_missed += 1
                await self.broadcast({
                    "type": "player_timeout",
                    "data": {
                        "seat": slot.seat,
                        "name": slot.name,
                        "consecutive": slot.consecutive_missed,
                        "total": slot.total_missed,
                    },
                })
                if slot.consecutive_missed >= MAX_CONSECUTIVE_MISSED or slot.total_missed >= MAX_TOTAL_MISSED:
                    raise ForfeitError(slot)
                declaration = None
            return forced_card, (declaration if declaration in _VALID_DECLARATIONS else None)

        if slot.is_bot:
            await asyncio.sleep(BOT_PLAY_DELAY)
            ctx = self._build_bot_context(seat)
            return self._get_bot_agent().select_card(ctx, self.briscola)
        try:
            payload = await asyncio.wait_for(slot.input_queue.get(), timeout=HUMAN_TURN_TIMEOUT)
            slot.consecutive_missed = 0
            card = dict_to_card(payload.get("card", {}))
            valid = get_valid_cards(slot.hand, lead_suit)
            if card not in valid:
                card = valid[0]
            declaration = payload.get("declaration")
            return card, (declaration if declaration in _VALID_DECLARATIONS else None)
        except asyncio.TimeoutError:
            slot.consecutive_missed += 1
            slot.total_missed += 1
            await self.broadcast({
                "type": "player_timeout",
                "data": {
                    "seat": slot.seat,
                    "name": slot.name,
                    "consecutive": slot.consecutive_missed,
                    "total": slot.total_missed,
                },
            })
            if slot.consecutive_missed >= MAX_CONSECUTIVE_MISSED or slot.total_missed >= MAX_TOTAL_MISSED:
                raise ForfeitError(slot)
            return self._get_bot_agent().select_card(self._build_bot_context(seat), self.briscola)

    # ── Game loop ──────────────────────────────────────────────────────────────

    async def run_game_loop(self) -> None:
        """Entry point for the background game task; handles all exceptions gracefully."""
        try:
            await self._game()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self.broadcast({"type": "error", "data": {"message": str(e)}})

    async def _game(self) -> None:
        """Run full rounds until one team reaches the win threshold."""
        self.status = "in_game"

        # Fill empty seats with bots
        used_names: set = {sl.name for sl in self.slots.values()}
        for seat in range(4):
            if seat not in self.slots:
                name = random_bot_name()
                while name in used_names:
                    name = random_bot_name()
                used_names.add(name)
                self.slots[seat] = PlayerSlot(seat=seat, name=name, is_bot=True)

        # Create the live policy agent for the whole room so timeout auto-play
        # shares the same round state even in all-human games.
        self._bot_agent = _create_live_bot_agent()

        await self.broadcast({
            "type": "game_started",
            "data": {
                "players": [
                    {"seat": s, "name": sl.name, "team": sl.team, "is_bot": sl.is_bot}
                    for s, sl in sorted(self.slots.items())
                ]
            },
        })

        next_first: Optional[int] = None
        while max(self.total_scores.values()) < GAME_WIN_THRESHOLD:
            await self._round(next_first)
            if max(self.total_scores.values()) >= GAME_WIN_THRESHOLD:
                break
            seats = sorted(self.slots.keys())
            idx = (seats.index(self.briscola_selector_seat) + 1) % len(seats)
            next_first = seats[idx]

        winner_team = max(self.total_scores, key=self.total_scores.get)
        self.phase = "game_over"
        await self.broadcast({
            "type": "game_over",
            "data": {"winner_team": winner_team, "scores": self.total_scores},
        })
        self.status = "game_over"

    async def _round(self, first_seat: Optional[int]) -> None:
        """Run one full round: deal cards, select briscola, play 10 turns, score."""
        self.round_num += 1
        self.turn_num = 0
        self.round_scores = {1: 0.0, 2: 0.0}
        self.briscola = None
        self.table_cards = []
        self.last_turn_winner_seat = None

        self._get_bot_agent().reset_round()

        deck = Deck()
        deck.shuffle()
        for slot in self.slots.values():
            slot.hand = deck.deal(10)
            if not slot.is_bot:
                slot.consecutive_missed = 0  # reset per-round; total_missed persists

        if first_seat is None:
            self.briscola_selector_seat = None
            for seat, slot in self.slots.items():
                if KEY_CARD in slot.hand:
                    self.briscola_selector_seat = seat
                    break
        else:
            self.briscola_selector_seat = first_seat

        self.phase = "briscola_selection"
        self.current_player_seat = self.briscola_selector_seat
        self.current_turn_deadline = (
            time.time() + HUMAN_TURN_TIMEOUT
            if not self.slots[self.briscola_selector_seat].is_bot else None
        )
        await self.broadcast_state()

        self.briscola = await self._await_briscola(self.briscola_selector_seat)
        self.current_turn_deadline = None

        await self.broadcast({
            "type": "briscola_set",
            "data": {
                "suit": self.briscola.value,
                "by_seat": self.briscola_selector_seat,
                "by_name": self.slots[self.briscola_selector_seat].name,
            },
        })

        # Maraffa (cricca): selettore ha 1, 2 e 3 di briscola → +3 punti immediati
        selector_slot = self.slots[self.briscola_selector_seat]
        maraffa_cards = [c for c in selector_slot.hand if c.suit == self.briscola and c.rank in (1, 2, 3)]
        if len(maraffa_cards) == 3:
            maraffa_team = selector_slot.team
            self.total_scores[maraffa_team] += 3
            self._maraffa_forced = True  # selector must open first trick with the ace
            await self.broadcast({
                "type": "maraffa",
                "data": {
                    "seat": self.briscola_selector_seat,
                    "name": selector_slot.name,
                    "team": maraffa_team,
                    "cards": [card_to_dict(c) for c in sorted(maraffa_cards, key=lambda c: c.rank)],
                    "bonus": 3,
                    "total_scores": self.total_scores,
                },
            })

        first_of_turn = self.briscola_selector_seat

        for t in range(10):
            self.turn_num = t + 1
            self.table_cards = []
            self.current_declaration = None
            self.phase = "playing"

            for i, seat in enumerate(self._rotate_seats(first_of_turn)):
                self.current_player_seat = seat
                self.current_turn_deadline = (
                    time.time() + HUMAN_TURN_TIMEOUT
                    if not self.slots[seat].is_bot else None
                )
                await self.broadcast_state()

                card, declaration = await self._await_card(seat)
                self.current_turn_deadline = None

                # Only the lead player's declaration (first card of trick) is recorded
                if i == 0 and declaration:
                    self.current_declaration = declaration

                slot = self.slots[seat]
                hand_before = [card_to_dict(c) for c in slot.hand]
                if card in slot.hand:
                    slot.hand.remove(card)
                self.table_cards.append((seat, card))
                self._get_bot_agent().record_card(
                    card,
                    seat,
                    self.turn_num,
                    declaration if i == 0 else None,
                )

                await self.broadcast({
                    "type": "card_played",
                    "data": {
                        "seat": seat,
                        "name": slot.name,
                        "card": card_to_dict(card),
                        "declaration": self.current_declaration if i == 0 else None,
                        "table": [{"seat": s, "card": card_to_dict(c)} for s, c in self.table_cards],
                        "hands_count": {str(s): len(sl.hand) for s, sl in self.slots.items()},
                        "hand_before": hand_before,
                    },
                })

            winner_seat = determine_turn_winner(self.table_cards, self.briscola)
            self.last_turn_winner_seat = winner_seat
            winner_team = self.slots[winner_seat].team
            turn_pts = sum(RANK_TO_POINTS[c.rank] for _, c in self.table_cards)
            self.round_scores[winner_team] += turn_pts

            self.phase = "turn_result"
            await self.broadcast({
                "type": "turn_result",
                "data": {
                    "winner_seat": winner_seat,
                    "winner_name": self.slots[winner_seat].name,
                    "winner_team": winner_team,
                    "points": round(turn_pts, 2),
                    "table": [{"seat": s, "card": card_to_dict(c)} for s, c in self.table_cards],
                    "round_scores": {k: round(v, 2) for k, v in self.round_scores.items()},
                },
            })

            first_of_turn = winner_seat
            await asyncio.sleep(TURN_RESULT_PAUSE)

        # Last-trick bonus goes to winner of the final turn
        self.round_scores[self.slots[first_of_turn].team] += 1

        self.round_scores[1] = floor(self.round_scores[1])
        self.round_scores[2] = floor(self.round_scores[2])

        for team in (1, 2):
            self.total_scores[team] += self.round_scores[team]

        self.phase = "round_end"
        await self.broadcast({
            "type": "round_end",
            "data": {
                "round": self.round_num,
                "round_scores": self.round_scores,
                "total_scores": self.total_scores,
            },
        })
        await asyncio.sleep(ROUND_END_PAUSE)


# ── Room manager ───────────────────────────────────────────────────────────────

class RoomManager:
    """In-memory registry of all active game rooms."""

    def __init__(self):
        """Initialise with an empty room store."""
        self.rooms: Dict[str, GameRoom] = {}

    def create(self) -> GameRoom:
        """Create a new room with a unique generated code and register it."""
        for _ in range(30):
            code = generate_room_code()
            if code not in self.rooms:
                room = GameRoom(code)
                self.rooms[code] = room
                return room
        raise RuntimeError("Cannot generate a unique room code after 30 attempts")

    def get(self, room_id: str) -> Optional[GameRoom]:
        """Return the room matching room_id (case-insensitive), or None."""
        return self.rooms.get(room_id.upper())

    def purge_finished(self) -> None:
        """Remove all rooms whose status is 'game_over'."""
        for k in [k for k, v in self.rooms.items() if v.status == "game_over"]:
            del self.rooms[k]

    def delete(self, room_id: str) -> None:
        """Remove a room by ID."""
        self.rooms.pop(room_id, None)
