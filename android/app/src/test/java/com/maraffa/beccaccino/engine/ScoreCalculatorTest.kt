package com.maraffa.beccaccino.engine

import com.maraffa.beccaccino.data.model.Player
import com.maraffa.beccaccino.data.model.PlayedCard
import com.maraffa.beccaccino.data.model.Rank
import com.maraffa.beccaccino.data.model.Trick
import com.maraffa.beccaccino.domain.engine.ScoreCalculator
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class ScoreCalculatorTest {

    private lateinit var calculator: ScoreCalculator

    private val players = mapOf(
        "alice" to Player("alice", "Alice", seatIndex = 0),  // Team 0
        "bob"   to Player("bob",   "Bob",   seatIndex = 1),  // Team 1
        "carol" to Player("carol", "Carol", seatIndex = 2),  // Team 0
        "dave"  to Player("dave",  "Dave",  seatIndex = 3)   // Team 1
    )

    @Before
    fun setUp() {
        calculator = ScoreCalculator()
    }

    @Test
    fun `ace scores 1 full point`() {
        assertEquals(1.0f, Rank.ACE.pointValue, 0.001f)
    }

    @Test
    fun `two and three score one third each`() {
        assertEquals(1f / 3f, Rank.TWO.pointValue, 0.001f)
        assertEquals(1f / 3f, Rank.THREE.pointValue, 0.001f)
    }

    @Test
    fun `court cards score one third each`() {
        assertEquals(1f / 3f, Rank.KING.pointValue, 0.001f)
        assertEquals(1f / 3f, Rank.HORSE.pointValue, 0.001f)
        assertEquals(1f / 3f, Rank.JACK.pointValue, 0.001f)
    }

    @Test
    fun `number cards score zero`() {
        listOf(Rank.SEVEN, Rank.SIX, Rank.FIVE, Rank.FOUR).forEach {
            assertEquals(0f, it.pointValue, 0.001f)
        }
    }

    @Test
    fun `total pip points across deck is 10`() {
        val aces = 4 * 1f
        val twos = 4 * (1f / 3f)
        val threes = 4 * (1f / 3f)
        val courts = 3 * 4 * (1f / 3f)  // King + Horse + Jack across 4 suits
        val total = aces + twos + threes + courts
        assertEquals(10f, total, 0.01f)
    }

    @Test
    fun `game over at 41 points`() {
        assertTrue(calculator.isGameOver(41f, 0f))
        assertTrue(calculator.isGameOver(0f, 41f))
        assertTrue(calculator.isGameOver(45f, 30f))
        assertFalse(calculator.isGameOver(40f, 40f))
        assertFalse(calculator.isGameOver(0f, 0f))
    }

    @Test
    fun `last trick bonus awarded to winner of trick 9`() {
        // Create 10 tricks: all won by Team 0 except last won by Team 1
        val tricks = (0..8).map { i ->
            Trick(i, listOf(
                PlayedCard("alice", "coins_4", 0),
                PlayedCard("bob", "cups_4", 1),
                PlayedCard("carol", "swords_4", 2),
                PlayedCard("dave", "clubs_4", 3)
            ), winnerUid = "alice", isComplete = true)
        } + listOf(
            Trick(9, listOf(
                PlayedCard("alice", "coins_5", 0),
                PlayedCard("bob", "cups_5", 1),
                PlayedCard("carol", "swords_5", 2),
                PlayedCard("dave", "clubs_5", 3)
            ), winnerUid = "bob", isComplete = true)  // Team 1 wins last trick
        )

        val score = calculator.calculateHandScore(tricks, players, marafonaTeam = -1)
        // All cards are 0-value (4s and 5s), so only the last trick bonus matters
        assertEquals(0f, score.team0Points, 0.001f)
        assertEquals(1f, score.team1Points, 0.001f)  // Team 1 gets last trick bonus
    }

    @Test
    fun `marafona adds 3 points to declaring team`() {
        val tricks = (0..9).map { i ->
            Trick(i, listOf(
                PlayedCard("alice", "coins_4", 0),
                PlayedCard("bob", "cups_4", 1),
                PlayedCard("carol", "swords_4", 2),
                PlayedCard("dave", "clubs_4", 3)
            ), winnerUid = "alice", isComplete = true)
        }
        val score = calculator.calculateHandScore(tricks, players, marafonaTeam = 0)
        // Alice wins all tricks: last trick +1, marafona +3
        assertEquals(4f, score.team0Points, 0.001f)
        assertEquals(0f, score.team1Points, 0.001f)
    }
}
