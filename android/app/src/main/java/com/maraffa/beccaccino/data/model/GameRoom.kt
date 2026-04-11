package com.maraffa.beccaccino.data.model

enum class RoomStatus { OPEN, IN_PROGRESS, FINISHED }

data class GameRoom(
    val roomId: String = "",
    /** 6-character human-readable join code, e.g. "XKPQ72" */
    val roomCode: String = "",
    val hostUid: String = "",
    val status: RoomStatus = RoomStatus.OPEN,
    val playerUids: List<String> = emptyList(),
    val createdAt: Long = 0L
)
