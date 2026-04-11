package com.maraffa.beccaccino.engine

import com.maraffa.beccaccino.domain.engine.CardDealer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class CardDealerTest {

    private lateinit var dealer: CardDealer

    @Before
    fun setUp() {
        dealer = CardDealer()
    }

    @Test
    fun `deals 10 cards to each of 4 players`() {
        val uids = listOf("alice", "bob", "carol", "dave")
        val result = dealer.deal(uids)
        assertEquals(4, result.hands.size)
        result.hands.values.forEach { hand ->
            assertEquals(10, hand.size)
        }
    }

    @Test
    fun `deals all 40 unique cards`() {
        val uids = listOf("alice", "bob", "carol", "dave")
        val result = dealer.deal(uids)
        val allDealt = result.hands.values.flatten()
        assertEquals(40, allDealt.size)
        assertEquals(40, allDealt.distinct().size)  // No duplicates
    }

    @Test
    fun `trump caller holds 4 of coins`() {
        val uids = listOf("alice", "bob", "carol", "dave")
        val result = dealer.deal(uids)
        assertNotNull(result.trumpCallerUid)
        val callerHand = result.hands[result.trumpCallerUid]!!
        assertTrue("4 of Coins must be in caller's hand", "coins_4" in callerHand)
    }

    @Test
    fun `4 of coins appears exactly once across all hands`() {
        val uids = listOf("alice", "bob", "carol", "dave")
        val result = dealer.deal(uids)
        val allDealt = result.hands.values.flatten()
        assertEquals(1, allDealt.count { it == "coins_4" })
    }

    @Test(expected = IllegalArgumentException::class)
    fun `throws if not 4 players`() {
        dealer.deal(listOf("alice", "bob", "carol"))
    }

    @Test(expected = IllegalArgumentException::class)
    fun `throws if duplicate uid`() {
        dealer.deal(listOf("alice", "alice", "carol", "dave"))
    }
}
