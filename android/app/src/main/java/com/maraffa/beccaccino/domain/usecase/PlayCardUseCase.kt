package com.maraffa.beccaccino.domain.usecase

import com.google.firebase.database.ServerValue
import com.maraffa.beccaccino.data.model.GamePhase
import com.maraffa.beccaccino.data.model.GameState
import com.maraffa.beccaccino.data.model.PlayedCard
import com.maraffa.beccaccino.data.model.Suit
import com.maraffa.beccaccino.data.model.Trick
import com.maraffa.beccaccino.data.repository.GameRepository
import com.maraffa.beccaccino.domain.engine.ScoreCalculator
import com.maraffa.beccaccino.domain.engine.TrickEvaluator
import javax.inject.Inject

/**
 * Validates and executes a card play.
 *
 * Handles:
 *  - Turn validation
 *  - Suit-following rule enforcement
 *  - Trick completion (4 cards played)
 *  - Hand completion (10 tricks played) with score calculation
 *  - Game-over detection (cumulative score >= 41)
 */
class PlayCardUseCase @Inject constructor(
    private val gameRepository: GameRepository,
    private val trickEvaluator: TrickEvaluator,
    private val scoreCalculator: ScoreCalculator
) {
    suspend operator fun invoke(
        gameState: GameState,
        myHand: List<String>,
        myUid: String,
        cardId: String
    ): Result<Unit> {
        // Guard: correct player's turn
        if (gameState.currentTurnUid != myUid) {
            return Result.failure(IllegalStateException("Non è il tuo turno"))
        }
        if (gameState.phase != GamePhase.PLAYING) {
            return Result.failure(IllegalStateException("La partita non è in corso"))
        }
        // Guard: card in hand
        if (cardId !in myHand) {
            return Result.failure(IllegalStateException("Carta non in mano"))
        }

        val trumpSuit = Suit.fromFirebaseKeyOrNull(gameState.trumpSuit)
            ?: return Result.failure(IllegalStateException("Briscola non ancora dichiarata"))

        // Guard: legal play (must follow suit)
        if (!trickEvaluator.isPlayLegal(cardId, myHand, gameState.currentTrick, trumpSuit)) {
            return Result.failure(IllegalStateException("Devi rispondere al seme"))
        }

        val myPlayer = gameState.players[myUid]
            ?: return Result.failure(IllegalStateException("Giocatore non trovato"))

        val newPlay = PlayedCard(playerUid = myUid, cardId = cardId, seatIndex = myPlayer.seatIndex)
        val updatedPlays = gameState.currentTrick.plays + newPlay
        val updatedHand = myHand - cardId

        // Determine led suit (first card of the trick)
        val ledSuit = if (gameState.currentTrick.plays.isEmpty()) {
            Suit.fromFirebaseKey(cardId.substringBefore("_")).firebaseKey
        } else {
            gameState.currentTrick.ledSuit
        }

        val updates = mutableMapOf<String, Any>()

        // Update hand
        updates["privateHands/${gameState.roomId}/$myUid/cards"] = updatedHand

        if (updatedPlays.size == 4) {
            // ─── Trick complete ───────────────────────────────────────────
            val winnerUid = trickEvaluator.evaluateTrick(updatedPlays, trumpSuit)
            val completedTrick = Trick(
                index = gameState.currentTrick.index,
                plays = updatedPlays,
                ledSuit = ledSuit,
                winnerUid = winnerUid,
                isComplete = true
            )
            val trickKey = gameState.currentTrick.index.toString()
            updates["gameStates/${gameState.roomId}/completedTricks/$trickKey"] = completedTrick.toMap()

            val totalTricksCompleted = gameState.completedTricks.size + 1

            if (totalTricksCompleted == 10) {
                // ─── Hand complete ─────────────────────────────────────────
                val allTricks = (gameState.completedTricks.values + completedTrick).toList()
                val handScore = scoreCalculator.calculateHandScore(
                    allTricks,
                    gameState.players,
                    gameState.marafonaTeam,
                    gameState.handNumber
                )
                val newTeam0Total = gameState.team0Score + handScore.team0Points
                val newTeam1Total = gameState.team1Score + handScore.team1Points

                updates["gameStates/${gameState.roomId}/cumulativeScore/0"] = newTeam0Total
                updates["gameStates/${gameState.roomId}/cumulativeScore/1"] = newTeam1Total

                val nextPhase = if (scoreCalculator.isGameOver(newTeam0Total, newTeam1Total)) {
                    GamePhase.GAME_OVER
                } else {
                    GamePhase.HAND_COMPLETE
                }
                updates["gameStates/${gameState.roomId}/phase"] = nextPhase.name
                updates["gameStates/${gameState.roomId}/currentTrick"] = Trick(index = 0).toMap()
            } else {
                // ─── Start next trick, winner leads ────────────────────────
                updates["gameStates/${gameState.roomId}/currentTrick"] = Trick(
                    index = gameState.currentTrick.index + 1
                ).toMap()
                updates["gameStates/${gameState.roomId}/currentTurnUid"] = winnerUid
            }
        } else {
            // ─── Trick still in progress ──────────────────────────────────
            updates["gameStates/${gameState.roomId}/currentTrick"] = Trick(
                index = gameState.currentTrick.index,
                plays = updatedPlays,
                ledSuit = ledSuit,
                winnerUid = "",
                isComplete = false
            ).toMap()
            updates["gameStates/${gameState.roomId}/currentTurnUid"] = nextPlayerUid(gameState, myUid)
        }

        updates["gameStates/${gameState.roomId}/lastUpdatedAt"] = ServerValue.TIMESTAMP

        return gameRepository.updateGameState(gameState.roomId, updates)
    }

    private fun nextPlayerUid(gameState: GameState, currentUid: String): String {
        val sortedPlayers = gameState.players.values.sortedBy { it.seatIndex }
        val currentSeat = gameState.players[currentUid]!!.seatIndex
        val nextSeat = (currentSeat + 1) % 4
        return sortedPlayers.first { it.seatIndex == nextSeat }.uid
    }
}
