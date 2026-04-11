package com.maraffa.beccaccino.data.repository

import com.maraffa.beccaccino.data.model.GameState
import kotlinx.coroutines.flow.Flow

interface GameRepository {
    /** Emits live game state updates from Firebase */
    fun observeGameState(roomId: String): Flow<GameState>

    /** Emits live hand updates for the local player (private data) */
    fun observeMyHand(roomId: String, uid: String): Flow<List<String>>

    /** Atomic multi-path update to the game state node */
    suspend fun updateGameState(roomId: String, update: Map<String, Any>): Result<Unit>

    /**
     * Atomic multi-path write of all 4 hands.
     * Called by the host client after dealing.
     */
    suspend fun writeHands(roomId: String, hands: Map<String, List<String>>): Result<Unit>

    /** Marks the player as connected/disconnected and registers onDisconnect handler */
    suspend fun setPlayerConnected(roomId: String, uid: String, connected: Boolean)
}
