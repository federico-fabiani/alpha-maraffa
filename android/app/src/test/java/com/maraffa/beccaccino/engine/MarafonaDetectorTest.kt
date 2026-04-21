package com.maraffa.beccaccino.engine

import com.maraffa.beccaccino.data.model.Player
import com.maraffa.beccaccino.data.model.Suit
import com.maraffa.beccaccino.domain.engine.MarafonaDetector
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class MarafonaDetectorTest {

    private lateinit var detector: MarafonaDetector

    @Before
    fun setUp() {
        detector = MarafonaDetector()
    }

    @Test
    fun `detects marafona when player holds 3 2 and ace of trump`() {
        val hand = listOf("coins_3", "coins_2", "coins_1", "cups_king", "swords_7",
            "clubs_4", "cups_3", "swords_king", "clubs_horse", "cups_2")
        assertTrue(detector.hasMarafona(hand, Suit.COINS))
    }

    @Test
    fun `no marafona if missing one of the top three`() {
        // Missing 3 of coins
        val hand = listOf("coins_2", "coins_1", "cups_king", "swords_7",
            "clubs_4", "cups_3", "swords_king", "clubs_horse", "cups_2", "swords_2")
        assertFalse(detector.hasMarafona(hand, Suit.COINS))
    }

    @Test
    fun `marafona requires all three of the trump suit specifically`() {
        // Has 3,2,Ace but of CUPS not COINS
        val hand = listOf("cups_3", "cups_2", "cups_1", "coins_king", "swords_7",
            "clubs_4", "swords_3", "swords_king", "clubs_horse", "coins_2")
        assertFalse(detector.hasMarafona(hand, Suit.COINS))   // trump is coins
        assertTrue(detector.hasMarafona(hand, Suit.CUPS))     // trump is cups
    }

    @Test
    fun `detectMarafonaTeam returns team index 0 when team A has marafona`() {
        val players = mapOf(
            "alice" to Player("alice", "Alice", seatIndex = 0),  // Team 0
            "bob"   to Player("bob",   "Bob",   seatIndex = 1),  // Team 1
            "carol" to Player("carol", "Carol", seatIndex = 2),  // Team 0
            "dave"  to Player("dave",  "Dave",  seatIndex = 3)   // Team 1
        )
        val hands = mapOf(
            "alice" to listOf("coins_3", "coins_2", "coins_1", "cups_king", "swords_7",
                "clubs_4", "cups_horse", "swords_4", "clubs_horse", "cups_5"),
            "bob"   to listOf("cups_4", "swords_5", "clubs_6", "coins_4", "cups_6",
                "swords_6", "clubs_7", "cups_7", "swords_horse", "clubs_king"),
            "carol" to listOf("cups_3", "cups_2", "cups_jack", "coins_king", "swords_3",
                "clubs_3", "coins_horse", "swords_2", "clubs_2", "coins_jack"),
            "dave"  to listOf("coins_6", "coins_5", "swords_1", "clubs_1", "cups_1",
                "swords_jack", "clubs_jack", "coins_7", "swords_king", "clubs_5")
        )
        val result = detector.detectMarafonaTeam(players, hands, Suit.COINS)
        assertEquals(0, result)  // Alice (Team 0) has the marafona
    }

    @Test
    fun `detectMarafonaTeam returns -1 when no team has marafona`() {
        val players = mapOf(
            "alice" to Player("alice", "Alice", seatIndex = 0),
            "bob"   to Player("bob",   "Bob",   seatIndex = 1),
            "carol" to Player("carol", "Carol", seatIndex = 2),
            "dave"  to Player("dave",  "Dave",  seatIndex = 3)
        )
        val hands = mapOf(
            "alice" to listOf("coins_3", "coins_2", "cups_1", "cups_king", "swords_7",
                "clubs_4", "cups_horse", "swords_4", "clubs_horse", "cups_5"),
            "bob"   to listOf("coins_1", "swords_5", "clubs_6", "coins_4", "cups_6",
                "swords_6", "clubs_7", "cups_7", "swords_horse", "clubs_king"),
            "carol" to listOf("cups_3", "cups_2", "cups_jack", "coins_king", "swords_3",
                "clubs_3", "coins_horse", "swords_2", "clubs_2", "coins_jack"),
            "dave"  to listOf("coins_6", "coins_5", "swords_1", "clubs_1", "coins_7",
                "swords_jack", "clubs_jack", "swords_king", "clubs_5", "cups_4")
        )
        val result = detector.detectMarafonaTeam(players, hands, Suit.COINS)
        assertEquals(-1, result)
    }
}
