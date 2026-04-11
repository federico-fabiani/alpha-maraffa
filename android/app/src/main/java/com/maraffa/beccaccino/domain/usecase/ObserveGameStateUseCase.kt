package com.maraffa.beccaccino.domain.usecase

import com.maraffa.beccaccino.data.model.GameState
import com.maraffa.beccaccino.data.repository.GameRepository
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject

class ObserveGameStateUseCase @Inject constructor(
    private val gameRepository: GameRepository
) {
    operator fun invoke(roomId: String): Flow<GameState> =
        gameRepository.observeGameState(roomId)
}
