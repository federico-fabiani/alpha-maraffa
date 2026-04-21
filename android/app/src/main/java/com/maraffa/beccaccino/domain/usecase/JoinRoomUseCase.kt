package com.maraffa.beccaccino.domain.usecase

import com.google.firebase.auth.FirebaseAuth
import com.maraffa.beccaccino.data.repository.LobbyRepository
import javax.inject.Inject

class JoinRoomUseCase @Inject constructor(
    private val lobbyRepository: LobbyRepository,
    private val auth: FirebaseAuth
) {
    suspend operator fun invoke(roomCode: String, displayName: String): Result<String> {
        val uid = auth.currentUser?.uid ?: return Result.failure(IllegalStateException("Not signed in"))
        return lobbyRepository.joinRoom(roomCode, uid, displayName)
    }
}
