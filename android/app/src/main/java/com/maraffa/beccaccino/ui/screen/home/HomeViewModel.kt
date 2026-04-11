package com.maraffa.beccaccino.ui.screen.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.firebase.auth.FirebaseAuth
import com.maraffa.beccaccino.domain.usecase.CreateRoomUseCase
import com.maraffa.beccaccino.domain.usecase.JoinRoomUseCase
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await
import javax.inject.Inject

data class HomeUiState(
    val displayName: String = "",
    val roomCode: String = "",
    val isLoading: Boolean = false,
    val error: String? = null,
    val navigateToRoom: String? = null
)

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val auth: FirebaseAuth,
    private val createRoomUseCase: CreateRoomUseCase,
    private val joinRoomUseCase: JoinRoomUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    init {
        signInAnonymouslyIfNeeded()
    }

    private fun signInAnonymouslyIfNeeded() {
        if (auth.currentUser == null) {
            viewModelScope.launch {
                runCatching { auth.signInAnonymously().await() }
                    .onFailure { e ->
                        _uiState.update { it.copy(error = "Errore di autenticazione: ${e.message}") }
                    }
            }
        }
    }

    fun onDisplayNameChange(name: String) {
        _uiState.update { it.copy(displayName = name, error = null) }
    }

    fun onRoomCodeChange(code: String) {
        _uiState.update { it.copy(roomCode = code.uppercase().take(6), error = null) }
    }

    fun onCreateRoom() {
        val name = _uiState.value.displayName.trim()
        if (name.isBlank()) {
            _uiState.update { it.copy(error = "Inserisci il tuo nome") }
            return
        }
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            createRoomUseCase(name)
                .onSuccess { roomId ->
                    _uiState.update { it.copy(isLoading = false, navigateToRoom = roomId) }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(isLoading = false, error = e.message ?: "Errore sconosciuto") }
                }
        }
    }

    fun onJoinRoom() {
        val name = _uiState.value.displayName.trim()
        val code = _uiState.value.roomCode.trim()
        if (name.isBlank()) {
            _uiState.update { it.copy(error = "Inserisci il tuo nome") }
            return
        }
        if (code.length != 6) {
            _uiState.update { it.copy(error = "Il codice stanza deve avere 6 caratteri") }
            return
        }
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            joinRoomUseCase(code, name)
                .onSuccess { roomId ->
                    _uiState.update { it.copy(isLoading = false, navigateToRoom = roomId) }
                }
                .onFailure { e ->
                    _uiState.update { it.copy(isLoading = false, error = e.message ?: "Stanza non trovata") }
                }
        }
    }

    fun onNavigationHandled() {
        _uiState.update { it.copy(navigateToRoom = null) }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }
}
