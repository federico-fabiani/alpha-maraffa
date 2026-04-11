package com.maraffa.beccaccino.ui.screen.lobby

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.firebase.auth.FirebaseAuth
import com.maraffa.beccaccino.data.model.GamePhase
import com.maraffa.beccaccino.data.model.GameRoom
import com.maraffa.beccaccino.data.model.GameState
import com.maraffa.beccaccino.data.model.Player
import com.maraffa.beccaccino.data.repository.LobbyRepository
import com.maraffa.beccaccino.domain.usecase.DealCardsUseCase
import com.maraffa.beccaccino.domain.usecase.ObserveGameStateUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class LobbyUiState(
    val roomId: String = "",
    val roomCode: String = "",
    val players: List<Player> = emptyList(),
    val isHost: Boolean = false,
    val isLoading: Boolean = true,
    val gameStarted: Boolean = false,
    val error: String? = null
) {
    val canStart: Boolean get() = isHost && players.size == 4
}

@HiltViewModel
class LobbyViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val auth: FirebaseAuth,
    private val lobbyRepository: LobbyRepository,
    private val observeGameStateUseCase: ObserveGameStateUseCase,
    private val dealCardsUseCase: DealCardsUseCase
) : ViewModel() {

    private val roomId: String = checkNotNull(savedStateHandle["roomId"])
    private val myUid get() = auth.currentUser?.uid ?: ""

    private val _uiState = MutableStateFlow(LobbyUiState(roomId = roomId))
    val uiState: StateFlow<LobbyUiState> = _uiState.asStateFlow()

    private var cachedGameState: GameState? = null

    init {
        observeLobby()
        observeGameState()
    }

    private fun observeLobby() {
        viewModelScope.launch {
            lobbyRepository.observeRoom(roomId).collect { room ->
                _uiState.update { state ->
                    state.copy(
                        roomCode = room.roomCode,
                        isLoading = false
                    )
                }
            }
        }
    }

    private fun observeGameState() {
        viewModelScope.launch {
            observeGameStateUseCase(roomId).collect { gameState ->
                cachedGameState = gameState
                val sortedPlayers = gameState.players.values.sortedBy { it.seatIndex }
                _uiState.update { state ->
                    state.copy(
                        players = sortedPlayers,
                        isHost = gameState.players[myUid]?.seatIndex == 0,
                        isLoading = false,
                        gameStarted = gameState.phase != GamePhase.WAITING_FOR_PLAYERS
                    )
                }
            }
        }
    }

    fun onStartGame() {
        val gameState = cachedGameState ?: return
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            lobbyRepository.startGame(roomId)
                .onSuccess {
                    dealCardsUseCase(gameState)
                        .onFailure { e ->
                            _uiState.update { it.copy(isLoading = false, error = e.message) }
                        }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(isLoading = false, error = e.message) }
                }
        }
    }
}
