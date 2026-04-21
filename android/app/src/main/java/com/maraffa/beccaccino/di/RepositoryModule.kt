package com.maraffa.beccaccino.di

import com.maraffa.beccaccino.data.remote.FirebaseGameRepository
import com.maraffa.beccaccino.data.remote.FirebaseLobbyRepository
import com.maraffa.beccaccino.data.repository.GameRepository
import com.maraffa.beccaccino.data.repository.LobbyRepository
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class RepositoryModule {

    @Binds
    @Singleton
    abstract fun bindGameRepository(impl: FirebaseGameRepository): GameRepository

    @Binds
    @Singleton
    abstract fun bindLobbyRepository(impl: FirebaseLobbyRepository): LobbyRepository
}
