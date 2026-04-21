package com.maraffa.beccaccino.domain.usecase

import com.google.firebase.database.ServerValue
import com.maraffa.beccaccino.data.model.GamePhase
import com.maraffa.beccaccino.data.model.GameState
import com.maraffa.beccaccino.data.model.Suit
import com.maraffa.beccaccino.data.repository.GameRepository
import com.maraffa.beccaccino.domain.engine.MarafonaDetector
import javax.inject.Inject

/**
 * Called by the player holding 4 of Coins to declare the trump suit.
 * After trump is declared, checks for marafona across all players.
 * The first trick is then led by the player sitting after the dealer.
 */
class DeclareTrumpUseCase @Inject constructor(
    private val gameRepository: GameRepository,
    private val marafonaDetector: MarafonaDetector
) {
    suspend operator fun invoke(
        gameState: GameState,
        myUid: String,
        trumpSuit: Suit,
        allHands: Map<String, List<String>>
    ): Result<Unit> {
        if (gameState.currentTurnUid != myUid) {
            return Result.failure(IllegalStateException("Solo chi ha il 4 di Denari può chiamare la briscola"))
        }
        if (gameState.phase != GamePhase.TRUMP_SELECTION) {
            return Result.failure(IllegalStateException("Fase di selezione briscola non attiva"))
        }

        // Check for marafona across all players
        val marafonaTeam = marafonaDetector.detectMarafonaTeam(
            gameState.players,
            allHands,
            trumpSuit
        )

        // First trick is led by the player to the left of the dealer (seat +1)
        val dealerSeat = gameState.dealerSeatIndex
        val firstLeadSeat = (dealerSeat + 1) % 4
        val firstLeadUid = gameState.players.values
            .firstOrNull { it.seatIndex == firstLeadSeat }?.uid
            ?: gameState.players.values.minByOrNull { it.seatIndex }!!.uid

        val updates: Map<String, Any> = mapOf(
            "trumpSuit" to trumpSuit.firebaseKey,
            "phase" to GamePhase.PLAYING.name,
            "currentTurnUid" to firstLeadUid,
            "marafonaTeam" to marafonaTeam,
            "lastUpdatedAt" to ServerValue.TIMESTAMP
        )

        return gameRepository.updateGameState(gameState.roomId, updates)
    }
}
