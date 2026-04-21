package com.maraffa.beccaccino.data.model

enum class GamePhase {
    WAITING_FOR_PLAYERS,
    TRUMP_SELECTION,
    PLAYING,
    HAND_COMPLETE,
    GAME_OVER
}

data class HandScore(
    val handNumber: Int = 0,
    val team0Points: Float = 0f,
    val team1Points: Float = 0f,
    val marafonaTeam: Int = -1
)

data class GameState(
    val roomId: String = "",
    val phase: GamePhase = GamePhase.WAITING_FOR_PLAYERS,
    /** uid -> Player */
    val players: Map<String, Player> = emptyMap(),
    val currentTrick: Trick = Trick(),
    /** trick index (as String) -> Trick */
    val completedTricks: Map<String, Trick> = emptyMap(),
    /** Firebase key of trump suit, e.g. "coins" */
    val trumpSuit: String = "",
    val currentTurnUid: String = "",
    val dealerSeatIndex: Int = 0,
    val handNumber: Int = 0,
    /** teamIndex (0 or 1) -> cumulative score */
    val cumulativeScore: Map<String, Float> = mapOf("0" to 0f, "1" to 0f),
    val declarations: List<Declaration> = emptyList(),
    /** -1 = none, 0 = Team A, 1 = Team B */
    val marafonaTeam: Int = -1,
    val lastUpdatedAt: Long = 0L
) {
    val team0Score: Float get() = cumulativeScore["0"] ?: 0f
    val team1Score: Float get() = cumulativeScore["1"] ?: 0f

    fun playerByUid(uid: String): Player? = players[uid]

    fun playersBySeat(): List<Player> = players.values.sortedBy { it.seatIndex }

    fun currentTurnPlayer(): Player? = players[currentTurnUid]
}
