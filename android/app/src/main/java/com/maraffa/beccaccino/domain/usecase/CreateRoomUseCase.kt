package com.maraffa.beccaccino.domain.usecase

import com.google.firebase.auth.FirebaseAuth
import com.maraffa.beccaccino.data.repository.LobbyRepository
import javax.inject.Inject

class CreateRoomUseCase @Inject constructor(
    private val lobbyRepository: LobbyRepository,
    private val auth: FirebaseAuth
) {
    suspend operator fun invoke(displayName: String): Result<String> {
        val uid = auth.currentUser?.uid ?: return Result.failure(IllegalStateException("Not signed in"))
        return lobbyRepository.createRoom(uid, displayName).map { room -> room.roomId }
    }
}
