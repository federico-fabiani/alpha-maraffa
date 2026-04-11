package com.maraffa.beccaccino.engine

import com.maraffa.beccaccino.data.model.PlayedCard
import com.maraffa.beccaccino.data.model.Suit
import com.maraffa.beccaccino.data.model.Trick
import com.maraffa.beccaccino.domain.engine.TrickEvaluator
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class TrickEvaluatorTest {

    private lateinit var evaluator: TrickEvaluator

    @Before
    fun setUp() {
        evaluator = TrickEvaluator()
    }

    @Test
    fun `trump beats led suit even if lowest trump vs highest led suit card`() {
        val plays = listOf(
            PlayedCard("alice", "cups_3", 0),    // Highest cups card
            PlayedCard("bob", "coins_4", 1),      // Lowest trump (4 of Coins)
            PlayedCard("carol", "cups_2", 2),
            PlayedCard("dave", "cups_1", 3)
        )
        val winner = evaluator.evaluateTrick(plays, trumpSuit = Suit.COINS)
        assertEquals("bob", winner)
    }

    @Test
    fun `highest trump wins when multiple trumps played`() {
        val plays = listOf(
            PlayedCard("alice", "coins_4", 0),    // gameOrder 0
            PlayedCard("bob", "coins_3", 1),      // gameOrder 9 (highest)
            PlayedCard("carol", "coins_2", 2),    // gameOrder 8
            PlayedCard("dave", "coins_1", 3)      // gameOrder 7 (Ace)
        )
        val winner = evaluator.evaluateTrick(plays, trumpSuit = Suit.COINS)
        assertEquals("bob", winner)
    }

    @Test
    fun `highest of led suit wins when no trumps played`() {
        val plays = listOf(
            PlayedCard("alice", "cups_7", 0),
            PlayedCard("bob", "swords_3", 1),    // Off-suit, should not win
            PlayedCard("carol", "cups_3", 2),    // Highest cups card -> wins
            PlayedCard("dave", "cups_king", 3)
        )
        val winner = evaluator.evaluateTrick(plays, trumpSuit = Suit.COINS)
        assertEquals("carol", winner)
    }

    @Test
    fun `ace beats king of same suit`() {
        val plays = listOf(
            PlayedCard("alice", "cups_king", 0),
            PlayedCard("bob", "cups_1", 1),      // Ace, gameOrder 7 > King's 6
            PlayedCard("carol", "cups_horse", 2),
            PlayedCard("dave", "cups_jack", 3)
        )
        val winner = evaluator.evaluateTrick(plays, trumpSuit = Suit.COINS)
        assertEquals("bob", winner)
    }

    @Test
    fun `three beats two which beats ace of same suit`() {
        val plays = listOf(
            PlayedCard("alice", "cups_3", 0),    // gameOrder 9 -> wins
            PlayedCard("bob", "cups_2", 1),      // gameOrder 8
            PlayedCard("carol", "cups_1", 2),    // gameOrder 7 (Ace)
            PlayedCard("dave", "cups_4", 3)
        )
        val winner = evaluator.evaluateTrick(plays, trumpSuit = Suit.COINS)
        assertEquals("alice", winner)
    }

    @Test
    fun `first player wins when all play the same rank off different suits`() {
        val plays = listOf(
            PlayedCard("alice", "cups_king", 0),  // Led suit = cups
            PlayedCard("bob", "swords_king", 1),
            PlayedCard("carol", "clubs_king", 2),
            PlayedCard("dave", "coins_king", 3)   // This would be trump but only if COINS is trump
        )
        // With SWORDS as trump, no trumps played
        val winner = evaluator.evaluateTrick(plays, trumpSuit = Suit.SWORDS)
        // Swords king is trump: should win
        assertEquals("bob", winner)
    }

    // --- isPlayLegal tests ---

    @Test
    fun `first player can play any card`() {
        val hand = listOf("cups_3", "swords_king", "coins_4")
        val emptyTrick = Trick(index = 0)
        assertTrue(evaluator.isPlayLegal("coins_4", hand, emptyTrick, Suit.COINS))
        assertTrue(evaluator.isPlayLegal("cups_3", hand, emptyTrick, Suit.COINS))
    }

    @Test
    fun `must follow suit if you have led suit cards`() {
        val hand = listOf("cups_3", "cups_7", "swords_king")
        val trick = Trick(
            index = 0,
            plays = listOf(PlayedCard("bob", "cups_king", 1)),
            ledSuit = "cups"
        )
        assertFalse(evaluator.isPlayLegal("swords_king", hand, trick, Suit.COINS))
        assertTrue(evaluator.isPlayLegal("cups_3", hand, trick, Suit.COINS))
        assertTrue(evaluator.isPlayLegal("cups_7", hand, trick, Suit.COINS))
    }

    @Test
    fun `can play any card if no led suit in hand`() {
        val hand = listOf("swords_3", "clubs_king")
        val trick = Trick(
            index = 0,
            plays = listOf(PlayedCard("bob", "cups_king", 1)),
            ledSuit = "cups"
        )
        assertTrue(evaluator.isPlayLegal("swords_3", hand, trick, Suit.COINS))
        assertTrue(evaluator.isPlayLegal("clubs_king", hand, trick, Suit.COINS))
    }

    @Test
    fun `can play trump when you have no led suit`() {
        val hand = listOf("coins_3", "clubs_king")  // No cups
        val trick = Trick(
            index = 0,
            plays = listOf(PlayedCard("bob", "cups_king", 1)),
            ledSuit = "cups"
        )
        assertTrue(evaluator.isPlayLegal("coins_3", hand, trick, Suit.COINS))
    }
}
