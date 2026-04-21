package com.maraffa.beccaccino.data.model

enum class DeclarationType(val displayName: String, val description: String) {
    /** Tap table: ask partner to play their highest card of the led suit */
    BUSSO("Busso", "Il compagno gioca la carta più alta"),
    /** Raise hand: you have no more cards of the suit you just led */
    VOLO("Volo", "Non ho altre carte di quel seme"),
    /** Rub table: you have low cards (King or lower) of the suit you just led */
    STRISCIO("Striscio", "Ho carte basse di quel seme")
}

data class Declaration(
    val playerUid: String = "",
    val type: DeclarationType = DeclarationType.BUSSO,
    val suit: String = "",
    val trickIndex: Int = 0
) {
    fun toMap(): Map<String, Any> = mapOf(
        "playerUid" to playerUid,
        "type" to type.name,
        "suit" to suit,
        "trickIndex" to trickIndex
    )

    companion object {
        fun fromMap(map: Map<String, Any?>): Declaration? = runCatching {
            Declaration(
                playerUid = map["playerUid"] as? String ?: return null,
                type = DeclarationType.valueOf(map["type"] as? String ?: return null),
                suit = map["suit"] as? String ?: "",
                trickIndex = (map["trickIndex"] as? Long)?.toInt() ?: 0
            )
        }.getOrNull()
    }
}
