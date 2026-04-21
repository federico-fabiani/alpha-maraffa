package com.maraffa.beccaccino.domain.engine

import com.maraffa.beccaccino.data.model.Card
import com.maraffa.beccaccino.data.model.Rank
import com.maraffa.beccaccino.data.model.Suit
import javax.inject.Inject

class MarafonaDetector @Inject constructor() {

    /**
     * Returns true if the given hand contains all three top trump cards:
     * 3 of trump, 2 of trump, and Ace of trump.
     *
     * Must be called after the trump suit has been declared.
     *
     * @param hand List of cardIds for a single player
     * @param trumpSuit The declared trump suit
     */
    fun hasMarafona(hand: List<String>, trumpSuit: Suit): Boolean {
        val handCards = hand.map { Card.fromId(it) }
        return Rank.MARAFONA_RANKS.all { rank ->
            handCards.any { card -> card.suit == trumpSuit && card.rank == rank }
        }
    }

    /**
     * Checks all players on a team to see if any single player holds a marafona.
     *
     * @param teamUids UIDs of the two players on the team
     * @param hands Map of uid -> list of cardIds
     * @param trumpSuit The declared trump suit
     * @return The UID of the player holding the marafona, or null
     */
    fun detectMarafonaHolder(
        teamUids: List<String>,
        hands: Map<String, List<String>>,
        trumpSuit: Suit
    ): String? = teamUids.firstOrNull { uid ->
        hasMarafona(hands[uid] ?: emptyList(), trumpSuit)
    }

    /**
     * Checks both teams and returns the team index (0 or 1) that has a marafona, or -1 if none.
     *
     * @param players Map of uid -> Player
     * @param hands Map of uid -> list of cardIds
     * @param trumpSuit The declared trump suit
     */
    fun detectMarafonaTeam(
        players: Map<String, com.maraffa.beccaccino.data.model.Player>,
        hands: Map<String, List<String>>,
        trumpSuit: Suit
    ): Int {
        for (teamIndex in 0..1) {
            val teamUids = players.values
                .filter { it.teamIndex == teamIndex }
                .map { it.uid }
            if (detectMarafonaHolder(teamUids, hands, trumpSuit) != null) {
                return teamIndex
            }
        }
        return -1
    }
}
