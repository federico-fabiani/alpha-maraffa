"""Rule-based heuristic Marafone agent."""
from __future__ import annotations

from collections import defaultdict
from enum import Enum
from typing import Optional, Tuple

from aimaraffa.engine import Card, get_valid_cards, RANK_TO_POINTS, RANK_TO_VALUE, Suit

from .base import BaseAgent

# ---------------------------------------------------------------------------
# Card-strength ordering (applies to all suits — briscola vs non-briscola
# is handled elsewhere; here we only need the intra-suit rank order).
#
#   RANK_TO_VALUE  →  1:11  2:12  3:13  4:4  5:5  … 10:10
#   Descending: 3 > 2 > 1(asso) > 10 > 9 > 8 > 7 > 6 > 5 > 4
# ---------------------------------------------------------------------------

_RANK_BY_STRENGTH: list[int] = sorted(
    range(1, 11), key=lambda r: RANK_TO_VALUE[r], reverse=True
)


# Seat → team mapping (seats 0, 2 = team 1; seats 1, 3 = team 2).
_TEAM: dict[int, int] = {0: 1, 1: 2, 2: 1, 3: 2}


# ---------------------------------------------------------------------------
# Trick-resolution helpers (pure, module-level)
# ---------------------------------------------------------------------------

def _card_power(card: Card, lead_suit: Suit, briscola: Suit) -> int:
    """Numeric strength of a card within the current trick context."""
    if card.suit == briscola:
        return RANK_TO_VALUE[card.rank] + 100
    if card.suit == lead_suit:
        return RANK_TO_VALUE[card.rank]
    return 0


def _current_winner_seat(
    table_cards: list[tuple[int, Card]], briscola: Suit
) -> int:
    """Seat of the current trick winner among cards already on the table."""
    lead_suit = table_cards[0][1].suit
    best_seat, best_card = table_cards[0]
    for seat, card in table_cards[1:]:
        if _card_power(card, lead_suit, briscola) > _card_power(best_card, lead_suit, briscola):
            best_seat, best_card = seat, card
    return best_seat


# ---------------------------------------------------------------------------
# Per-player, per-suit state tracking
# ---------------------------------------------------------------------------

class SuitStatus(Enum):
    """What we know about one player's holding in a given suit."""

    UNKNOWN = "unknown"
    # Confirmed still has ≥1 card (declared striscio or followed suit recently).
    HAS_CARDS = "has_cards"
    # Declared busso — holds the 2nd strongest remaining card at declaration time.
    DECLARED_BUSSO = "declared_busso"
    # No cards left in this suit.
    VOID = "void"


# ---------------------------------------------------------------------------
# Briscola-selection helpers
# ---------------------------------------------------------------------------

_CRICCA_RANKS = frozenset({1, 2, 3})

# Point value each cricca card adds to the briscola-quality score.
# Ace > two > three, because they give increasingly more control.
_CRICCA_BONUS: dict[int, int] = {1: 6, 2: 4, 3: 2}


def _briscola_score(cards: list[Card]) -> float:
    """Return a numeric score for choosing this suit as briscola.

    Higher is better.  Suits with fewer than 3 cards return ``-inf`` and
    should never be chosen.

    **Scoring model**

    * *Maraffa* (ace + two + three all present, ≥ 3 cards): absolute winner.
      Returns 1000 + card_count so that a 5-card maraffa beats a 3-card one.
    * Otherwise: ``count_score + cricca_bonus``

      * ``count_score = n² – 3n + 3``  → 3→3, 4→7, 5→13, 6→21
        (convex: losing the 6th card hurts more than losing the 4th)
      * ``cricca_bonus``: +6 ace, +4 two, +2 three

    Net effect:
    * 6 nothing → 21; need ace+two (score 23) to justify choosing 5 over 6.
    * 5 nothing → 13; ace+two (score 17) justifies 4 over 5.
    * Going from 6 → 4 never pays unless it's maraffa.
    """
    n = len(cards)
    if n < 3:
        return float("-inf")

    ranks = {c.rank for c in cards}
    if _CRICCA_RANKS.issubset(ranks):
        # Maraffa: prefer more cards on tie (e.g. 5-card maraffa > 3-card maraffa)
        return 1_000.0 + n

    # Convex count score
    count_score = n * n - 3 * n + 3

    # Cricca bonus
    cricca_bonus = sum(_CRICCA_BONUS.get(r, 0) for r in ranks)

    return float(count_score + cricca_bonus)


class HeuristicAgent(BaseAgent):
    """Plays according to explicit Marafone strategy rules.

    Per-round tracking
    ------------------
    * ``_played``            : set of all Card objects seen via record_card.
    * ``_player_suit_state`` : dict[seat → dict[Suit → SuitStatus]].
    * ``_suit_lead_counts``  : dict[Suit → number of times the suit was led].
    * ``_trick_lead_suit``   : suit of the first card of the current trick.

    SuitStatus transitions
    ----------------------
    * declaration "volo"    → VOID  (last card in suit played)
    * declaration "striscio"→ HAS_CARDS  (≥1 remaining confirmed)
    * declaration "busso"   → DECLARED_BUSSO  (has 2nd strongest remaining)
    * followed lead suit (no decl) → UNKNOWN  (played one, count unknown)
    * played different suit than lead → VOID in lead_suit  (void by rule)
    """

    def __init__(self) -> None:
        self._played: set[Card] = set()
        self._player_suit_state: dict[int, dict[Suit, SuitStatus]] = {}
        self._suit_lead_counts: dict[Suit, int] = {}
        self._trick_lead_suit: Optional[Suit] = None
        self._briscola_force_rounds: int = 0
        self._init_suit_state()

    def _init_suit_state(self) -> None:
        self._player_suit_state = {
            seat: {suit: SuitStatus.UNKNOWN for suit in Suit}
            for seat in range(4)
        }
        self._suit_lead_counts = {suit: 0 for suit in Suit}

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "heuristic"

    def reset_round(self) -> None:
        self._played = set()
        self._trick_lead_suit = None
        self._briscola_force_rounds = 0
        self._init_suit_state()

    def record_card(
        self,
        card: Card,
        seat: int,
        turn_num: int,
        declaration: Optional[str],
    ) -> None:
        """Update internal tracking after every card played by any seat.

        ``turn_num`` is the trick number (1–10).  Lead position is inferred
        from the total number of cards already played: if ``len(_played) % 4 == 0``
        before this card, this player is opening the trick.
        """
        is_lead = len(self._played) % 4 == 0
        self._played.add(card)
        suit = card.suit
        state = self._player_suit_state[seat]

        if is_lead:
            # This seat is leading the trick.
            self._trick_lead_suit = suit
            self._suit_lead_counts[suit] += 1
            if declaration == "volo":
                state[suit] = SuitStatus.VOID
            elif declaration == "busso":
                state[suit] = SuitStatus.DECLARED_BUSSO
            elif declaration == "striscio":
                # striscio guarantees ≥1 remaining after this play.
                state[suit] = SuitStatus.HAS_CARDS
            # None declaration → no information about remaining count.
        else:
            # Following player.
            lead = self._trick_lead_suit
            if lead is not None:
                if suit == lead:
                    # Followed the lead suit — might still have more or not.
                    if state[lead] != SuitStatus.VOID:
                        state[lead] = SuitStatus.UNKNOWN
                else:
                    # Played a different suit → VOID in lead suit (rules enforce it).
                    state[lead] = SuitStatus.VOID

    # ------------------------------------------------------------------
    # Tracking queries
    # ------------------------------------------------------------------

    def _played_ranks(self, suit: Suit) -> frozenset[int]:
        return frozenset(c.rank for c in self._played if c.suit == suit)

    def player_suit_status(self, seat: int, suit: Suit) -> SuitStatus:
        """Return the known SuitStatus of `seat` in `suit`."""
        return self._player_suit_state[seat][suit]

    def strongest_rank_outstanding(self, suit: Suit, my_hand: list[Card]) -> Optional[int]:
        """Strongest rank of `suit` not yet played and not in our hand.

        Returns the rank integer or None if all cards are either played
        or in our own hand.
        """
        played = self._played_ranks(suit)
        own = frozenset(c.rank for c in my_hand if c.suit == suit)
        for rank in _RANK_BY_STRENGTH:
            if rank not in played and rank not in own:
                return rank
        return None

    def cards_played_in_suit(self, suit: Suit) -> int:
        """How many cards of `suit` have been played this round."""
        return sum(1 for c in self._played if c.suit == suit)

    def suit_lead_count(self, suit: Suit) -> int:
        """How many tricks have been opened with `suit` this round."""
        return self._suit_lead_counts[suit]

    def _top_outstanding_run(self, suit: Suit, hand: list[Card]) -> list[Card]:
        """Top outstanding run in `suit` that we currently hold."""
        played = self._played_ranks(suit)
        hand_by_rank = {c.rank: c for c in hand if c.suit == suit}
        run: list[Card] = []

        for rank in _RANK_BY_STRENGTH:
            if rank in played:
                continue
            card = hand_by_rank.get(rank)
            if card is None:
                break
            run.append(card)

        return run

    def _infer_void_from_card_count(self, hand: list[Card]) -> None:
        """Mark all seats VOID in suits where played + our hand accounts for all 10 cards.

        If played_count + our_hand_count == 10, no other player can hold any
        card in that suit — update their status to VOID.
        """
        for suit in Suit:
            played = self.cards_played_in_suit(suit)
            own = sum(1 for c in hand if c.suit == suit)
            if played + own >= 10:
                for seat in range(4):
                    self._player_suit_state[seat][suit] = SuitStatus.VOID

    # ------------------------------------------------------------------
    # Declaration logic (used when we are leading a trick)
    # ------------------------------------------------------------------

    def _should_busso(self, card: Card, hand: list[Card]) -> bool:
        """True if we should declare busso when leading with `card`.

        Busso means: the strongest card of this suit is still outstanding
        (someone else has it), but we hold the 2nd strongest remaining —
        so if this suit is led again we will take it.

        Concretely (for the cricca cards):
        * We have rank 2 and rank 3 is still outstanding → busso.
        * Rank 3 is gone, we have rank 1, rank 2 is still outstanding → busso.
        * Rank 2 is gone, we have rank 1, rank 3 is still outstanding → busso.
        More generally: among all ranks of this suit not yet played and
        not equal to the card we're leading, the strongest is NOT in our
        hand (it's outstanding) and the 2nd strongest IS in our hand.
        """
        suit = card.suit
        played = self._played_ranks(suit)
        # All ranks remaining after this play (not played, not this card).
        remaining = [r for r in _RANK_BY_STRENGTH if r not in played and r != card.rank]
        if not remaining:
            return False
        hand_ranks = frozenset(c.rank for c in hand if c.suit == suit and c != card)
        strongest = remaining[0]
        if strongest in hand_ranks:
            # We hold the strongest remaining — no need to busso.
            return False
        # Strongest is outstanding; check if 2nd strongest is in our hand.
        if len(remaining) >= 2:
            return remaining[1] in hand_ranks
        return False

    def _pick_declaration(self, card: Card, hand: list[Card]) -> Optional[str]:
        """Choose the declaration when leading with `card`.

        Priority:  volo  >  busso  >  striscio
        (No-declaration / None is never used when we lead.)
        """
        suit = card.suit
        remaining_in_hand = sum(1 for c in hand if c.suit == suit and c != card)
        if remaining_in_hand == 0:
            return "volo"
        if self._should_busso(card, hand):
            return "busso"
        return "striscio"

    # ------------------------------------------------------------------
    # Briscola selection
    # ------------------------------------------------------------------

    def select_briscola(self, ctx: dict) -> Suit:
        """Choose the briscola suit.

        Priority:
        1. Maraffa (ace + two + three all present, ≥ 3 cards) — biggest score.
        2. Highest ``_briscola_score`` (convex count + cricca bonus).
        3. Tiebreak: more cards, then higher cricca bonus.
        Never choose a suit with fewer than 3 cards (returns -inf).
        """
        hand: list[Card] = ctx["hand"]

        suit_cards: dict[Suit, list[Card]] = defaultdict(list)
        for card in hand:
            suit_cards[card.suit].append(card)

        best_suit: Suit | None = None
        best_score: float = float("-inf")
        best_n: int = 0
        best_cricca: int = 0

        for suit, cards in suit_cards.items():
            score = _briscola_score(cards)
            n = len(cards)
            cricca = sum(_CRICCA_BONUS.get(c.rank, 0) for c in cards)

            better = (
                score > best_score
                or (score == best_score and n > best_n)
                or (score == best_score and n == best_n and cricca > best_cricca)
            )
            if better:
                best_suit = suit
                best_score = score
                best_n = n
                best_cricca = cricca

        # Fallback: if all suits have < 3 cards (edge case), pick the largest.
        if best_suit is None or best_score == float("-inf"):
            best_suit = max(suit_cards, key=lambda s: len(suit_cards[s]))

        return best_suit  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Card-property helpers
    # ------------------------------------------------------------------

    def _is_controlling(self, card: Card, hand: list[Card]) -> bool:
        """True if card is the strongest remaining in its suit (ignoring briscola contest).

        A card is controlling when, iterating ranks strongest→weakest, we hit
        this card's rank before any rank that is not yet played.
        """
        played = self._played_ranks(card.suit)
        for rank in _RANK_BY_STRENGTH:
            if rank == card.rank:
                return True
            if rank not in played:
                return False  # Someone else holds a stronger card
        return True

    def _would_create_asso_secco(self, card: Card, hand: list[Card]) -> bool:
        """True if playing this card leaves a lone, non-controlling ace in the same suit."""
        suit = card.suit
        remaining = [c for c in hand if c.suit == suit and c != card]
        if len(remaining) == 1 and remaining[0].rank == 1:
            ace = remaining[0]
            hand_after = [c for c in hand if c != card]
            return not self._is_controlling(ace, hand_after)
        return False

    # ------------------------------------------------------------------
    # Lead helpers
    # ------------------------------------------------------------------

    def _try_force_briscola(
        self,
        hand: list[Card],
        briscola: Suit,
        opps: list[int],
    ) -> Optional[Card]:
        """Return a briscola card to force opponents out of briscola, or None.

        Stop conditions:
        * Both opponents confirmed VOID (goal achieved).
        * All remaining briscole are in our hand (played + ours >= 10).
        * Max forced rounds reached: 4 briscole → 2 rounds, 5+ → 3 rounds.

        Card preference: rank 2 first (signals we hold rank 3 for end-game),
        then rank 1, then lower ranks.  Rank 3 reserved as last resort.
        """
        my_briscole = [c for c in hand if c.suit == briscola]
        if len(my_briscole) < 4:
            return None

        opp0_void = self._player_suit_state[opps[0]][briscola] == SuitStatus.VOID
        opp1_void = self._player_suit_state[opps[1]][briscola] == SuitStatus.VOID
        if opp0_void and opp1_void:
            return None  # Goal achieved

        # All remaining briscole are ours — no opponent can have any.
        played_briscola = self.cards_played_in_suit(briscola)
        if played_briscola + len(my_briscole) >= 10:
            return None

        # Max rounds of forced briscola.
        max_rounds = 2 if len(my_briscole) <= 4 else 3
        if self._briscola_force_rounds >= max_rounds:
            return None

        # Priority: 2 > 1 > lower ranks > 3 (keep rank 3 for end-game).
        _prio = {2: 5, 1: 4, 10: 3, 9: 2, 8: 2, 7: 1, 6: 1, 5: 1, 4: 1, 3: 0}
        return max(my_briscole, key=lambda c: _prio.get(c.rank, 1))

    def _busso_response_lead(
        self,
        hand: list[Card],
        briscola: Suit,
        partner: int,
    ) -> Optional[Card]:
        """If partner declared busso on a suit we hold, return our strongest card there."""
        for suit in Suit:
            if suit == briscola:
                continue
            if self._player_suit_state[partner][suit] == SuitStatus.DECLARED_BUSSO:
                our_cards = [c for c in hand if c.suit == suit]
                if our_cards:
                    return max(our_cards, key=lambda c: RANK_TO_VALUE[c.rank])
        return None

    def _known_cut_risk(self, suit: Suit, briscola: Suit, opps: list[int]) -> int:
        """Count opponents who are known void in `suit` and may still cut with briscola."""
        return sum(
            1
            for opp in opps
            if self._player_suit_state[opp][suit] == SuitStatus.VOID
            and self._player_suit_state[opp][briscola] != SuitStatus.VOID
        )

    def _partner_cut_support(self, suit: Suit, briscola: Suit, partner: int) -> int:
        """Return 1 when partner is well placed to overtake a cut in `suit`."""
        if (
            self._player_suit_state[partner][suit] == SuitStatus.VOID
            and self._player_suit_state[partner][briscola] != SuitStatus.VOID
        ):
            return 1
        return 0

    def _team_take_confidence(
        self,
        card: Card,
        hand: list[Card],
        briscola: Suit,
        partner: int,
        opps: list[int],
    ) -> float:
        """Heuristic confidence that our team keeps the trick after leading `card`."""
        stronger_held = 0
        for idx, run_card in enumerate(self._top_outstanding_run(card.suit, hand)):
            if run_card == card:
                stronger_held = idx
                break

        if self._is_controlling(card, hand):
            confidence = 0.75
        elif stronger_held > 0:
            confidence = 0.25 + 0.20 * stronger_held
        else:
            confidence = 0.15

        confidence -= 0.15 * self.suit_lead_count(card.suit)
        confidence -= 0.20 * self._known_cut_risk(card.suit, briscola, opps)
        confidence += 0.10 * self._partner_cut_support(card.suit, briscola, partner)

        return max(0.0, min(0.95, confidence))

    def _best_protected_points_lead(
        self,
        hand: list[Card],
        briscola: Suit,
        partner: int,
        opps: list[int],
    ) -> Optional[Card]:
        """Best early non-briscola lead that cashes protected points from a top run."""
        best_card: Optional[Card] = None
        best_key: Optional[tuple[float, float, int, int]] = None

        for suit in Suit:
            if suit == briscola or self.suit_lead_count(suit) > 1:
                continue

            run = self._top_outstanding_run(suit, hand)
            if len(run) < 2:
                continue

            for idx, card in enumerate(run[1:], start=1):
                if RANK_TO_POINTS[card.rank] <= 0:
                    continue

                confidence = self._team_take_confidence(card, hand, briscola, partner, opps)
                expected_points = confidence * RANK_TO_POINTS[card.rank]
                key = (expected_points, confidence, idx, -RANK_TO_VALUE[card.rank])
                if best_key is None or key > best_key:
                    best_card = card
                    best_key = key

        return best_card

    def _lead_expected_points(
        self,
        card: Card,
        hand: list[Card],
        briscola: Suit,
        partner: int,
        opps: list[int],
    ) -> float:
        """Expected points value of leading `card`, using team-take confidence."""
        return self._team_take_confidence(card, hand, briscola, partner, opps) * RANK_TO_POINTS[card.rank]

    def _best_controlling_lead(self, hand: list[Card], briscola: Suit) -> Optional[Card]:
        """Highest-value controlling non-briscola card.

        Prefers the asso (1.0 pt) over other controlling cards.
        Tiebreak by RANK_TO_VALUE (rank 3 > 2 > 1 > …) for control ordering.
        """
        controlling = [
            c for c in hand
            if c.suit != briscola and self._is_controlling(c, hand)
        ]
        if not controlling:
            return None
        return max(controlling, key=lambda c: (RANK_TO_POINTS[c.rank], RANK_TO_VALUE[c.rank]))

    def _best_busso_lead(
        self,
        hand: list[Card],
        briscola: Suit,
        is_selector: bool = False,
    ) -> Optional[Card]:
        """Best card to lead for a busso declaration (we hold the 2nd strongest).

        Briscola busso is allowed only when we are the selector — the intent
        is to invite the partner to help exhaust opponent briscole.
        """
        busso_candidates = [
            c for c in hand
            if (c.suit != briscola or is_selector) and self._should_busso(c, hand)
        ]
        if not busso_candidates:
            return None
        return max(busso_candidates, key=lambda c: RANK_TO_VALUE[c.rank])

    def _lead_for_partner_briscola(
        self,
        hand: list[Card],
        briscola: Suit,
        partner: int,
    ) -> Optional[Card]:
        """Lead into a suit where partner is VOID but the ace is still outstanding.

        Lets the partner use a briscola to take the ace.  Skip if partner is
        also known to be VOID in briscola (they can't capitalise).
        """
        if self._player_suit_state[partner][briscola] == SuitStatus.VOID:
            return None

        for suit in Suit:
            if suit == briscola:
                continue
            if self._player_suit_state[partner][suit] != SuitStatus.VOID:
                continue
            # Partner is void in this suit — is the ace still outstanding?
            played = self._played_ranks(suit)
            if 1 in played:
                continue  # Ace already played
            if any(c.suit == suit and c.rank == 1 for c in hand):
                continue  # Ace is ours — no point leading here
            our_cards = [c for c in hand if c.suit == suit]
            if our_cards:
                return min(our_cards, key=lambda c: RANK_TO_POINTS[c.rank])

        return None

    def _shed_short_suit_lead(self, hand: list[Card], briscola: Suit, partner: int = -1) -> Optional[Card]:
        """Play toward voiding a short non-briscola suit (for future volo).

        Targets suits with ≤2 cards.  Avoids creating asso secco unless the
        ace is already the controlling card.  Prefers suits where partner's
        status is UNKNOWN (probing value — sondaggio).
        """
        suit_groups: dict[Suit, list[Card]] = defaultdict(list)
        for c in hand:
            if c.suit != briscola:
                suit_groups[c.suit].append(c)

        # (card, partner_is_unknown)
        candidates: list[tuple[Card, bool]] = []
        for suit, cards in suit_groups.items():
            n = len(cards)
            has_ace = any(c.rank == 1 for c in cards)
            partner_unknown = (
                partner >= 0
                and self._player_suit_state[partner][suit] == SuitStatus.UNKNOWN
            )
            if n <= 2 and not has_ace:
                best = min(cards, key=lambda c: RANK_TO_POINTS[c.rank])
                candidates.append((best, partner_unknown))
            elif n == 2 and has_ace:
                non_ace_cards = [c for c in cards if c.rank != 1]
                ace_cards = [c for c in cards if c.rank == 1]
                if non_ace_cards and ace_cards:
                    hand_after = [c for c in hand if c != non_ace_cards[0]]
                    if self._is_controlling(ace_cards[0], hand_after):
                        candidates.append((non_ace_cards[0], partner_unknown))

        if not candidates:
            return None
        # Prefer suits where partner is UNKNOWN (sondaggio), then lowest value.
        return min(candidates, key=lambda t: (0 if t[1] else 1, RANK_TO_POINTS[t[0].rank]))[0]

    def _fallback_lead(self, hand: list[Card], briscola: Suit) -> Card:
        """Lowest-value non-briscola card, avoiding asso secco creation where possible."""
        non_briscola = [c for c in hand if c.suit != briscola]
        pool = non_briscola if non_briscola else hand
        safe = [c for c in pool if not self._would_create_asso_secco(c, hand)]
        candidates = safe if safe else pool
        return min(candidates, key=lambda c: RANK_TO_POINTS[c.rank])

    def _lead_card(self, ctx: dict, briscola: Suit) -> Card:
        """Choose which card to lead, in priority order."""
        hand: list[Card] = ctx["hand"]
        seat: int = ctx["seat"]
        partner = (seat + 2) % 4
        opps = [(seat + 1) % 4, (seat + 3) % 4]
        is_selector = ctx.get("briscola_selector_seat") == seat

        # 1. Exhaust opponent briscole (only if WE are the briscola selector).
        if is_selector:
            forced = self._try_force_briscola(hand, briscola, opps)
            if forced is not None:
                self._briscola_force_rounds += 1
                return forced

        # 2. Return partner's busso (play our strongest card in their bussed suit).
        busso_resp = self._busso_response_lead(hand, briscola, partner)
        if busso_resp is not None:
            return busso_resp

        # 3. Cash protected points early when our team is likely to keep the trick.
        protected_points = self._best_protected_points_lead(hand, briscola, partner, opps)

        # 4. Play a controlling card; prefer asso (highest pts) over other controlling.
        controlling = self._best_controlling_lead(hand, briscola)
        if protected_points is not None:
            if controlling is None:
                return protected_points
            if (
                self._lead_expected_points(protected_points, hand, briscola, partner, opps)
                > self._lead_expected_points(controlling, hand, briscola, partner, opps)
            ):
                return protected_points
        if controlling is not None:
            return controlling

        # 5. Declare busso (2nd strongest remaining); briscola busso allowed if selector.
        busso = self._best_busso_lead(hand, briscola, is_selector=is_selector)
        if busso is not None:
            return busso

        # 6. Lead into partner's void suit where ace is still outstanding.
        partner_tactic = self._lead_for_partner_briscola(hand, briscola, partner)
        if partner_tactic is not None:
            return partner_tactic

        # 7. Shed a short suit to work toward volo (≤2 cards, no asso secco risk).
        shed = self._shed_short_suit_lead(hand, briscola, partner)
        if shed is not None:
            return shed

        # 8. Fallback: lowest-value card, avoiding asso secco.
        return self._fallback_lead(hand, briscola)

    # ------------------------------------------------------------------
    # Follow helpers
    # ------------------------------------------------------------------

    def _give_points_to_partner(
        self,
        valid: list[Card],
        lead_suit: Suit,
        briscola: Suit,
        opps: list[int],
        position: int = 1,
    ) -> Card:
        """Play to maximise points added to a trick our partner is winning.

        At position 3 (last player) no one can steal — give freely but avoid
        rank 3 (strategically valuable for control); prefer asso then figures.
        For earlier positions, skip aces when an opponent might steal with briscola.
        """
        lead_cards = [c for c in valid if c.suit == lead_suit]
        if lead_cards:
            if position == 3:
                # Last player: prefer asso, avoid giving rank 3.
                non_tre = [c for c in lead_cards if c.rank != 3]
                pool = non_tre if non_tre else lead_cards
                return max(pool, key=lambda c: RANK_TO_POINTS[c.rank])
            return max(lead_cards, key=lambda c: RANK_TO_POINTS[c.rank])

        # Void in lead suit.
        non_briscola = [c for c in valid if c.suit != briscola]
        if not non_briscola:
            return min(valid, key=lambda c: RANK_TO_VALUE[c.rank])

        if position == 3:
            # Last player — no risk of theft; give best card, avoid rank 3.
            non_tre = [c for c in non_briscola if c.rank != 3]
            pool = non_tre if non_tre else non_briscola
            return max(pool, key=lambda c: RANK_TO_POINTS[c.rank])

        # Check if any opponent might steal with a briscola.
        any_risky_opp = any(
            self._player_suit_state[opp][lead_suit] == SuitStatus.VOID
            and self._player_suit_state[opp][briscola] != SuitStatus.VOID
            for opp in opps
        )
        if not any_risky_opp:
            return max(non_briscola, key=lambda c: RANK_TO_POINTS[c.rank])

        # Risky — avoid giving aces; give best non-ace.
        non_ace = [c for c in non_briscola if c.rank != 1]
        pool = non_ace if non_ace else non_briscola
        return max(pool, key=lambda c: RANK_TO_POINTS[c.rank])

    def _try_beat(
        self,
        valid: list[Card],
        winner_card: Card,
        lead_suit: Suit,
        briscola: Suit,
        table_cards: list[tuple[int, Card]],
        hand: list[Card],
        position: int,
    ) -> Optional[Card]:
        """Return the cheapest card that beats `winner_card`, or None.

        Briscola is only used out-of-suit (when void in lead suit) when:
        - we are NOT the last player (position < 3), AND
        - there are already points on the table OR the ace of lead_suit
          is still outstanding (not played, not in our hand).
        """
        points_on_table = sum(RANK_TO_POINTS[c.rank] for _, c in table_cards)
        played_lead = self._played_ranks(lead_suit)
        ace_outstanding = (
            1 not in played_lead
            and not any(c.suit == lead_suit and c.rank == 1 for c in hand)
        )
        can_use_briscola_oos = position < 3 and (points_on_table > 0 or ace_outstanding)

        winning = [
            c for c in valid
            if _card_power(c, lead_suit, briscola) > _card_power(winner_card, lead_suit, briscola)
            and (c.suit != briscola or can_use_briscola_oos)
        ]
        if not winning:
            return None
        return min(winning, key=lambda c: _card_power(c, lead_suit, briscola))

    def _play_low_neutral(self, valid: list[Card], briscola: Suit) -> Card:
        """Play the lowest-value card, avoiding briscola if possible."""
        non_briscola = [c for c in valid if c.suit != briscola]
        pool = non_briscola if non_briscola else valid
        return min(pool, key=lambda c: RANK_TO_POINTS[c.rank])

    def _follow_card(
        self,
        ctx: dict,
        briscola: Suit,
        valid: list[Card],
        lead_suit: Suit,
        table_cards: list[tuple[int, Card]],
        position: int,
    ) -> Card:
        """Choose a card when following (positions 1–3 in a trick)."""
        hand: list[Card] = ctx["hand"]
        seat: int = ctx["seat"]
        partner = (seat + 2) % 4
        opps = [(seat + 1) % 4, (seat + 3) % 4]

        partner_has_played = any(s == partner for s, _ in table_cards)
        current_winner = _current_winner_seat(table_cards, briscola)
        partner_winning = (current_winner == partner)
        current_winner_card = next(c for s, c in table_cards if s == current_winner)

        if partner_winning:
            return self._give_points_to_partner(valid, lead_suit, briscola, opps, position)

        # Partner bussed in the lead suit → they likely win; play our highest there.
        if (
            not partner_has_played
            and self._player_suit_state[partner][lead_suit] == SuitStatus.DECLARED_BUSSO
        ):
            lead_cards = [c for c in valid if c.suit == lead_suit]
            if lead_cards:
                return max(lead_cards, key=lambda c: RANK_TO_POINTS[c.rank])

        if not partner_has_played:
            # Partner still to play — play low, pass the hand.
            return self._play_low_neutral(valid, briscola)

        # Partner has played and is NOT winning → opponent is winning.
        beat = self._try_beat(
            valid, current_winner_card, lead_suit, briscola, table_cards, hand, position
        )
        if beat is not None:
            return beat

        # Can't win — discard lowest-value card.
        return min(valid, key=lambda c: RANK_TO_POINTS[c.rank])

    # ------------------------------------------------------------------
    # Main public interface
    # ------------------------------------------------------------------

    def select_card(self, ctx: dict, briscola: Suit) -> Tuple[Card, Optional[str]]:
        """Choose card + optional declaration to play.

        Returns ``(card, declaration)`` where declaration is one of
        ``"busso"``, ``"striscio"``, ``"volo"``, or ``None``.
        Non-lead plays always return ``None`` for declaration.
        """
        hand: list[Card] = ctx["hand"]
        self._infer_void_from_card_count(hand)
        table_cards: list[tuple[int, Card]] = ctx["table_cards"]
        position = len(table_cards)  # 0 = lead, 1–3 = follow

        # Single card left: no choice to make.
        if len(hand) == 1:
            decl = self._pick_declaration(hand[0], hand) if position == 0 else None
            return hand[0], decl

        lead_suit = table_cards[0][1].suit if table_cards else None
        valid = get_valid_cards(hand, lead_suit)

        if position == 0:
            card = self._lead_card(ctx, briscola)
            decl = self._pick_declaration(card, hand)
        else:
            card = self._follow_card(ctx, briscola, valid, lead_suit, table_cards, position)
            decl = None

        return card, decl
