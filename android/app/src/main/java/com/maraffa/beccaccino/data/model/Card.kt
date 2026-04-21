package com.maraffa.beccaccino.data.model

data class Card(
    val suit: Suit,
    val rank: Rank
) {
    /** Unique string identifier used as Firebase key, e.g. "coins_3", "cups_1" */
    val id: String get() = "${suit.firebaseKey}_${rank.firebaseKey}"

    /**
     * Returns true if this card beats [other] given the trump suit and the led suit.
     * Rules:
     *  - Trump always beats non-trump
     *  - Among same suit, higher gameOrder wins
     *  - Off-suit non-trump never beats anything
     */
    fun beats(other: Card, trumpSuit: Suit, ledSuit: Suit): Boolean {
        if (this.suit == trumpSuit && other.suit != trumpSuit) return true
        if (this.suit != trumpSuit && other.suit == trumpSuit) return false
        if (this.suit == other.suit) return this.rank.gameOrder > other.rank.gameOrder
        return false
    }

    companion object {
        fun fromId(id: String): Card {
            val underscore = id.indexOf('_')
            val suitKey = id.substring(0, underscore)
            val rankKey = id.substring(underscore + 1)
            return Card(Suit.fromFirebaseKey(suitKey), Rank.fromFirebaseKey(rankKey))
        }

        /** Returns a full 40-card Italian deck */
        fun fullDeck(): List<Card> =
            Suit.values().flatMap { suit ->
                Rank.values().map { rank -> Card(suit, rank) }
            }
    }
}
