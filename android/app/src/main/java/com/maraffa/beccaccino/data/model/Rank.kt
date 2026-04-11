package com.maraffa.beccaccino.data.model

/**
 * Card ranks in Marafone Beccaccino.
 * gameOrder: 9 = highest (3), 0 = lowest (4)
 * pointValue: used for score calculation
 *   Ace = 1.0, 2/3/court = 1/3, number cards = 0
 */
enum class Rank(
    val displayName: String,
    val firebaseKey: String,
    val gameOrder: Int,
    val pointValue: Float
) {
    THREE("3", "3", 9, 1f / 3f),
    TWO("2", "2", 8, 1f / 3f),
    ACE("A", "1", 7, 1.0f),
    KING("K", "king", 6, 1f / 3f),
    HORSE("C", "horse", 5, 1f / 3f),
    JACK("J", "jack", 4, 1f / 3f),
    SEVEN("7", "7", 3, 0f),
    SIX("6", "6", 2, 0f),
    FIVE("5", "5", 1, 0f),
    FOUR("4", "4", 0, 0f);

    companion object {
        fun fromFirebaseKey(key: String): Rank =
            values().first { it.firebaseKey == key }

        /** The three cards that form a Marafona (highest trump trio), in descending order */
        val MARAFONA_RANKS = listOf(THREE, TWO, ACE)
    }
}
