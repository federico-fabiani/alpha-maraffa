package com.maraffa.beccaccino.ui.screen.game

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.firebase.auth.FirebaseAuth
import com.maraffa.beccaccino.data.model.Card
import com.maraffa.beccaccino.data.model.Declaration
import com.maraffa.beccaccino.data.model.DeclarationType
import com.maraffa.beccaccino.data.model.GamePhase
import com.maraffa.beccaccino.data.model.GameState
import com.maraffa.beccaccino.data.model.Player
import com.maraffa.beccaccino.data.model.Suit
import com.maraffa.beccaccino.data.repository.GameRepository
import com.maraffa.beccaccino.domain.engine.TrickEvaluator
import com.maraffa.beccaccino.domain.usecase.DeclareTrumpUseCase
import com.maraffa.beccaccino.domain.usecase.DealCardsUseCase
import com.maraffa.beccaccino.domain.usecase.MakeDeclarationUseCase
import com.maraffa.beccaccino.domain.usecase.ObserveGameStateUseCase
import com.maraffa.beccaccino.domain.usecase.PlayCardUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class GameUiState(
    val gameState: GameState = GameState(),
    val myHand: List<Card> = emptyList(),
    val myHandIds: List<String> = emptyList(),
    val isMyTurn: Boolean = false,
    val isHost: Boolean = false,
    val selectedCard: Card? = null,
    val legalCards: Set<String> = emptySet(),
    val error: String? = null,
    val isLoading: Boolean = true,
    val showMarafonaAnnouncement: Boolean = false,
    /** Players relative to local user: [0]=me, [1]=left, [2]=opposite, [3]=right */
    val seatedPlayers: List<Player?> = listOf(null, null, null, null),
    /** Card counts per seated player */
    val opponentCardCounts: Map<Int, Int> = emptyMap()
)

@HiltViewModel
class GameViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val observeGameStateUseCase: ObserveGameStateUseCase,
    private val playCardUseCase: PlayCardUseCase,
    private val makeDeclarationUseCase: MakeDeclarationUseCase,
    private val declareTrumpUseCase: DeclareTrumpUseCase,
    private val dealCardsUseCase: DealCardsUseCase,
    private val gameRepository: GameRepository,
    private val trickEvaluator: TrickEvaluator,
    private val auth: FirebaseAuth
) : ViewModel() {

    private val roomId: String = checkNotNull(savedStateHandle["roomId"])
    val myUid: String get() = auth.currentUser?.uid ?: ""

    private val _uiState = MutableStateFlow(GameUiState())
    val uiState: StateFlow<GameUiState> = _uiState.asStateFlow()

    // Cached hand for passing to use cases
    private var myCurrentHand: List<String> = emptyList()

    init {
        observeGame()
        registerPresence()
    }

    private fun observeGame() {
        viewModelScope.launch {
            combine(
                observeGameStateUseCase(roomId),
                gameRepository.observeMyHand(roomId, myUid)
            ) { gameState, handCardIds ->
                myCurrentHand = handCardIds
                val myPlayer = gameState.players[myUid]
                val mySeat = myPlayer?.seatIndex ?: 0
                val isMyTurn = gameState.currentTurnUid == myUid && gameState.phase == GamePhase.PLAYING

                val trumpSuit = Suit.fromFirebaseKeyOrNull(gameState.trumpSuit)

                val legalCards = if (isMyTurn && trumpSuit != null) {
                    trickEvaluator.legalCards(handCardIds, gameState.currentTrick, trumpSuit)
                } else emptySet()

                // Arrange players relative to local seat
                val seatedPlayers = (0..3).map { relPos ->
                    val absSeat = (mySeat + relPos) % 4
                    gameState.players.values.firstOrNull { it.seatIndex == absSeat }
                }

                // Auto-deal if host and phase transitions back to WAITING (next hand)
                val shouldAutoDeal = gameState.phase == GamePhase.HAND_COMPLETE &&
                        myPlayer?.seatIndex == 0 &&
                        gameState.players.size == 4

                GameUiState(
                    gameState = gameState,
                    myHand = handCardIds.mapNotNull { runCatching { Card.fromId(it) }.getOrNull() },
                    myHandIds = handCardIds,
                    isMyTurn = isMyTurn,
                    isHost = myPlayer?.seatIndex == 0,
                    legalCards = legalCards,
                    isLoading = false,
                    seatedPlayers = seatedPlayers,
                    showMarafonaAnnouncement = gameState.marafonaTeam >= 0 &&
                            gameState.currentTrick.index == 0 &&
                            gameState.currentTrick.plays.isEmpty()
                )
            }.collect { state ->
                _uiState.value = state
                // Auto-start next hand if host and previous hand ended
                if (state.gameState.phase == GamePhase.HAND_COMPLETE && state.isHost) {
                    dealNextHand(state.gameState)
                }
            }
        }
    }

    fun onCardSelected(card: Card) {
        _uiState.update { it.copy(selectedCard = card, error = null) }
    }

    fun onCardPlayed(card: Card) {
        val hand = myCurrentHand
        viewModelScope.launch {
            playCardUseCase(_uiState.value.gameState, hand, myUid, card.id)
                .onSuccess { _uiState.update { it.copy(selectedCard = null) } }
                .onFailure { e -> _uiState.update { it.copy(error = e.message, selectedCard = null) } }
        }
    }

    fun onTrumpSelected(suit: Suit) {
        val hand = myCurrentHand
        viewModelScope.launch {
            val allHands = mapOf(myUid to hand)  // Only local hand is available; marafona detection runs server-side via host
            declareTrumpUseCase(_uiState.value.gameState, myUid, suit, allHands)
                .onFailure { e -> _uiState.update { it.copy(error = e.message) } }
        }
    }

    fun onDeclaration(type: DeclarationType, suit: Suit) {
        viewModelScope.launch {
            makeDeclarationUseCase(_uiState.value.gameState, myUid, type, suit)
                .onFailure { e -> _uiState.update { it.copy(error = e.message) } }
        }
    }

    fun dismissMarafonaAnnouncement() {
        _uiState.update { it.copy(showMarafonaAnnouncement = false) }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }

    private fun dealNextHand(gameState: GameState) {
        viewModelScope.launch {
            dealCardsUseCase(gameState)
                .onFailure { e -> _uiState.update { it.copy(error = e.message) } }
        }
    }

    private fun registerPresence() {
        viewModelScope.launch {
            gameRepository.setPlayerConnected(roomId, myUid, true)
        }
    }

    override fun onCleared() {
        super.onCleared()
        viewModelScope.launch {
            gameRepository.setPlayerConnected(roomId, myUid, false)
        }
    }
}
