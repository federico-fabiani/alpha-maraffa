package com.maraffa.beccaccino.ui.screen.result

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.firebase.auth.FirebaseAuth
import com.maraffa.beccaccino.data.model.GameState
import com.maraffa.beccaccino.domain.usecase.ObserveGameStateUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ResultUiState(
    val team0Score: Float = 0f,
    val team1Score: Float = 0f,
    val winningTeam: Int = -1,
    val myTeamIndex: Int = -1,
    val myTeamWon: Boolean = false,
    val marafonaTeam: Int = -1,
    val handNumber: Int = 0,
    val isLoading: Boolean = true
)

@HiltViewModel
class ResultViewModel @Inject constructor(
    savedStateHandle: SavedStateHandle,
    private val observeGameStateUseCase: ObserveGameStateUseCase,
    private val auth: FirebaseAuth
) : ViewModel() {

    private val roomId: String = checkNotNull(savedStateHandle["roomId"])
    private val myUid get() = auth.currentUser?.uid ?: ""

    private val _uiState = MutableStateFlow(ResultUiState())
    val uiState: StateFlow<ResultUiState> = _uiState.asStateFlow()

    init {
        loadResults()
    }

    private fun loadResults() {
        viewModelScope.launch {
            val gameState = observeGameStateUseCase(roomId).first()
            val myTeam = gameState.players[myUid]?.teamIndex ?: -1
            val team0Score = gameState.team0Score
            val team1Score = gameState.team1Score
            val winningTeam = if (team0Score >= team1Score) 0 else 1

            _uiState.update {
                ResultUiState(
                    team0Score = team0Score,
                    team1Score = team1Score,
                    winningTeam = winningTeam,
                    myTeamIndex = myTeam,
                    myTeamWon = myTeam == winningTeam,
                    marafonaTeam = gameState.marafonaTeam,
                    handNumber = gameState.handNumber,
                    isLoading = false
                )
            }
        }
    }
}
