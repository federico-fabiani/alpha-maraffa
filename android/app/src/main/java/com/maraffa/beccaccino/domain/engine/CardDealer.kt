package com.maraffa.beccaccino.domain.engine

import com.maraffa.beccaccino.data.model.Card
import javax.inject.Inject

data class DealResult(
    /** uid -> list of cardIds for that player's hand */
    val hands: Map<String, List<String>>,
    /** The player who holds the 4 of Coins (must call trump) */
    val trumpCallerUid: String
)

class CardDealer @Inject constructor() {

    /**
     * Shuffles a full 40-card deck and distributes 10 cards to each of the 4 players.
     * The player holding 4 of Coins (coins_4) is identified as the trump caller.
     *
     * @param playerUids List of 4 player UIDs in seat order (seat 0–3)
     */
    fun deal(playerUids: List<String>): DealResult {
        require(playerUids.size == 4) { "Marafone requires exactly 4 players" }
        require(playerUids.distinct().size == 4) { "Player UIDs must be unique" }

        val deck = Card.fullDeck().shuffled()

        val hands: Map<String, List<String>> = playerUids.mapIndexed { i, uid ->
            uid to deck.subList(i * 10, (i + 1) * 10).map { it.id }
        }.toMap()

        val trumpCallerUid = hands.entries
            .firstOrNull { (_, cards) -> "coins_4" in cards }
            ?.key
            ?: error("4 of Coins (coins_4) not found in any hand — deck generation error")

        return DealResult(hands = hands, trumpCallerUid = trumpCallerUid)
    }
}
