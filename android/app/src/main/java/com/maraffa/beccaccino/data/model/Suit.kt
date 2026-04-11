package com.maraffa.beccaccino.data.model

enum class Suit(val displayName: String, val firebaseKey: String, val symbol: String) {
    COINS("Denari", "coins", "D"),
    CUPS("Coppe", "cups", "C"),
    SWORDS("Spade", "swords", "S"),
    CLUBS("Bastoni", "clubs", "B");

    companion object {
        fun fromFirebaseKey(key: String): Suit =
            values().first { it.firebaseKey == key }

        fun fromFirebaseKeyOrNull(key: String?): Suit? =
            if (key.isNullOrBlank()) null else values().firstOrNull { it.firebaseKey == key }
    }
}
