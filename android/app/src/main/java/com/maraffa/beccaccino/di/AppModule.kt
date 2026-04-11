package com.maraffa.beccaccino.di

import com.maraffa.beccaccino.domain.engine.CardDealer
import com.maraffa.beccaccino.domain.engine.MarafonaDetector
import com.maraffa.beccaccino.domain.engine.ScoreCalculator
import com.maraffa.beccaccino.domain.engine.TrickEvaluator
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideCardDealer(): CardDealer = CardDealer()

    @Provides
    @Singleton
    fun provideTrickEvaluator(): TrickEvaluator = TrickEvaluator()

    @Provides
    @Singleton
    fun provideScoreCalculator(): ScoreCalculator = ScoreCalculator()

    @Provides
    @Singleton
    fun provideMarafonaDetector(): MarafonaDetector = MarafonaDetector()
}
