package com.maraffa.beccaccino.data.model

data class PlayedCard(
    val playerUid: String = "",
    val cardId: String = "",
    val seatIndex: Int = 0
) {
    fun toMap(): Map<String, Any> = mapOf(
        "playerUid" to playerUid,
        "cardId" to cardId,
        "seatIndex" to seatIndex
    )

    companion object {
        fun fromMap(map: Map<String, Any?>): PlayedCard? = runCatching {
            PlayedCard(
                playerUid = map["playerUid"] as? String ?: return null,
                cardId = map["cardId"] as? String ?: return null,
                seatIndex = (map["seatIndex"] as? Long)?.toInt() ?: 0
            )
        }.getOrNull()
    }
}

data class Trick(
    val index: Int = 0,
    /** Cards played in turn order */
    val plays: List<PlayedCard> = emptyList(),
    val ledSuit: String = "",
    val winnerUid: String = "",
    val isComplete: Boolean = false
) {
    fun toMap(): Map<String, Any> = mapOf(
        "index" to index,
        "plays" to plays.map { it.toMap() },
        "ledSuit" to ledSuit,
        "winnerUid" to winnerUid,
        "isComplete" to isComplete
    )

    companion object {
        @Suppress("UNCHECKED_CAST")
        fun fromMap(map: Map<String, Any?>): Trick = Trick(
            index = (map["index"] as? Long)?.toInt() ?: 0,
            plays = (map["plays"] as? List<Map<String, Any?>>)
                ?.mapNotNull { PlayedCard.fromMap(it) }
                ?: emptyList(),
            ledSuit = map["ledSuit"] as? String ?: "",
            winnerUid = map["winnerUid"] as? String ?: "",
            isComplete = map["isComplete"] as? Boolean ?: false
        )
    }
}
