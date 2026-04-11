package com.maraffa.beccaccino.data.repository

import com.maraffa.beccaccino.data.model.GameRoom
import kotlinx.coroutines.flow.Flow

interface LobbyRepository {
    /** Creates a new room and returns its ID */
    suspend fun createRoom(hostUid: String, hostDisplayName: String): Result<GameRoom>

    /**
     * Joins an existing room by its 6-character code.
     * Assigns the next available seat and returns the roomId.
     */
    suspend fun joinRoom(roomCode: String, uid: String, displayName: String): Result<String>

    /** Observes the lobby (player list and status) for a given room */
    fun observeRoom(roomId: String): Flow<GameRoom>

    /** Marks the room as IN_PROGRESS (called by host when starting) */
    suspend fun startGame(roomId: String): Result<Unit>
}
