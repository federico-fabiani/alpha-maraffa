package com.maraffa.beccaccino.domain.usecase

import com.google.firebase.database.ServerValue
import com.maraffa.beccaccino.data.model.GamePhase
import com.maraffa.beccaccino.data.model.GameState
import com.maraffa.beccaccino.data.model.Trick
import com.maraffa.beccaccino.data.repository.GameRepository
import com.maraffa.beccaccino.domain.engine.CardDealer
import javax.inject.Inject

/**
 * Called by the host client when all 4 players have joined.
 * Shuffles and distributes cards, writes private hands, transitions to TRUMP_SELECTION.
 */
class DealCardsUseCase @Inject constructor(
    private val gameRepository: GameRepository,
    private val cardDealer: CardDealer
) {
    suspend operator fun invoke(gameState: GameState): Result<Unit> {
        val playerUids = gameState.players.values
            .sortedBy { it.seatIndex }
            .map { it.uid }

        require(playerUids.size == 4) { "Need exactly 4 players to deal" }

        val dealResult = cardDealer.deal(playerUids)

        // Write all 4 hands atomically to /privateHands
        gameRepository.writeHands(gameState.roomId, dealResult.hands)
            .getOrElse { return Result.failure(it) }

        // Transition game state to TRUMP_SELECTION
        val updates: Map<String, Any> = mapOf(
            "phase" to GamePhase.TRUMP_SELECTION.name,
            "currentTurnUid" to dealResult.trumpCallerUid,
            "handNumber" to (gameState.handNumber + 1),
            "currentTrick" to Trick(index = 0).toMap(),
            "completedTricks" to emptyMap<String, Any>(),
            "declarations" to emptyMap<String, Any>(),
            "trumpSuit" to "",
            "marafonaTeam" to -1,
            "lastUpdatedAt" to ServerValue.TIMESTAMP
        )

        return gameRepository.updateGameState(gameState.roomId, updates)
    }
}
