package com.maraffa.beccaccino.data.model

data class Player(
    val uid: String = "",
    val displayName: String = "",
    /**
     * Seat index 0–3.
     * Team A: seats 0 and 2 (partners sit opposite each other)
     * Team B: seats 1 and 3
     */
    val seatIndex: Int = -1,
    val isConnected: Boolean = true,
    val isReady: Boolean = false
) {
    /** 0 = Team A (seats 0,2), 1 = Team B (seats 1,3) */
    val teamIndex: Int get() = seatIndex % 2
}
