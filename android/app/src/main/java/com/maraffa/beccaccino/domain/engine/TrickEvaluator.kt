package com.maraffa.beccaccino.domain.engine

import com.maraffa.beccaccino.data.model.Card
import com.maraffa.beccaccino.data.model.PlayedCard
import com.maraffa.beccaccino.data.model.Suit
import com.maraffa.beccaccino.data.model.Trick
import javax.inject.Inject

class TrickEvaluator @Inject constructor() {

    /**
     * Determines the winner of a completed trick (exactly 4 played cards).
     *
     * Scoring priority:
     *   - Trump card:    100 + rank.gameOrder  (always beats non-trump)
     *   - Led suit card:  10 + rank.gameOrder  (beats off-suit non-trump)
     *   - Off-suit non-trump: -1               (never wins)
     *
     * @return UID of the winning player
     */
    fun evaluateTrick(plays: List<PlayedCard>, trumpSuit: Suit): String {
        require(plays.size == 4) { "A trick must have exactly 4 played cards" }

        val ledSuit = Card.fromId(plays.first().cardId).suit

        return plays.maxByOrNull { playedCard ->
            val card = Card.fromId(playedCard.cardId)
            when {
                card.suit == trumpSuit -> 100 + card.rank.gameOrder
                card.suit == ledSuit  -> 10  + card.rank.gameOrder
                else                  -> -1
            }
        }!!.playerUid
    }

    /**
     * Checks whether playing [cardId] from [hand] is a legal move given the current trick state.
     *
     * Rules:
     *  - If you are the first to play, any card is legal.
     *  - If you have one or more cards matching the led suit, you MUST play one.
     *  - If you have no cards of the led suit, you may play any card (including trump).
     */
    fun isPlayLegal(
        cardId: String,
        hand: List<String>,
        currentTrick: Trick,
        trumpSuit: Suit
    ): Boolean {
        if (currentTrick.plays.isEmpty()) return true

        val ledSuit = Card.fromId(currentTrick.plays.first().cardId).suit
        val handCards = hand.map { Card.fromId(it) }
        val hasLedSuit = handCards.any { it.suit == ledSuit }

        if (!hasLedSuit) return true

        val playedCard = Card.fromId(cardId)
        return playedCard.suit == ledSuit
    }

    /**
     * Returns all card IDs from [hand] that are legal to play given the current trick.
     */
    fun legalCards(hand: List<String>, currentTrick: Trick, trumpSuit: Suit): Set<String> =
        hand.filter { isPlayLegal(it, hand, currentTrick, trumpSuit) }.toSet()
}
