package com.maraffa.beccaccino.domain.usecase

import com.google.firebase.database.ServerValue
import com.maraffa.beccaccino.data.model.Declaration
import com.maraffa.beccaccino.data.model.DeclarationType
import com.maraffa.beccaccino.data.model.GameState
import com.maraffa.beccaccino.data.model.Suit
import com.maraffa.beccaccino.data.repository.GameRepository
import javax.inject.Inject

/**
 * Records a player declaration (Busso/Volo/Striscio) into the shared game state.
 * Declarations are informational signals to the player's partner.
 */
class MakeDeclarationUseCase @Inject constructor(
    private val gameRepository: GameRepository
) {
    suspend operator fun invoke(
        gameState: GameState,
        myUid: String,
        type: DeclarationType,
        suit: Suit
    ): Result<Unit> {
        val declaration = Declaration(
            playerUid = myUid,
            type = type,
            suit = suit.firebaseKey,
            trickIndex = gameState.currentTrick.index
        )
        val declarationIndex = gameState.declarations.size
        val updates: Map<String, Any> = mapOf(
            "declarations/$declarationIndex" to declaration.toMap(),
            "lastUpdatedAt" to ServerValue.TIMESTAMP
        )
        return gameRepository.updateGameState(gameState.roomId, updates)
    }
}
