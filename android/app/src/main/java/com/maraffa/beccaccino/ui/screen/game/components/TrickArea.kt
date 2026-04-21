package com.maraffa.beccaccino.ui.screen.game.components

import androidx.compose.foundation.layout.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.maraffa.beccaccino.data.model.Card
import com.maraffa.beccaccino.data.model.PlayedCard
import com.maraffa.beccaccino.data.model.Player
import com.maraffa.beccaccino.data.model.Suit
import com.maraffa.beccaccino.data.model.Trick

/**
 * Displays the 4 cards played in the current trick arranged around the center.
 * Layout is relative to the local player's seat position:
 *  - Local player's card: bottom
 *  - Opposite partner: top
 *  - Left opponent: left
 *  - Right opponent: right
 */
@Composable
fun TrickArea(
    trick: Trick,
    players: Map<String, Player>,
    myUid: String,
    trumpSuit: Suit?,
    modifier: Modifier = Modifier
) {
    val mySeat = players[myUid]?.seatIndex ?: 0

    // Map played cards by relative position
    val playsByRelativePos = trick.plays.associate { play ->
        val playerSeat = players[play.playerUid]?.seatIndex ?: 0
        val relPos = (playerSeat - mySeat + 4) % 4  // 0=me, 1=left, 2=opposite, 3=right
        relPos to play
    }

    Box(modifier = modifier.size(240.dp), contentAlignment = Alignment.Center) {
        // Bottom (me - pos 0)
        playsByRelativePos[0]?.let { play ->
            TrickCard(play = play, trumpSuit = trumpSuit, modifier = Modifier.align(Alignment.BottomCenter))
        }
        // Top (opposite - pos 2)
        playsByRelativePos[2]?.let { play ->
            TrickCard(play = play, trumpSuit = trumpSuit, modifier = Modifier.align(Alignment.TopCenter))
        }
        // Left (pos 1 or 3 depending on seating)
        playsByRelativePos[1]?.let { play ->
            TrickCard(play = play, trumpSuit = trumpSuit, modifier = Modifier.align(Alignment.CenterStart))
        }
        // Right (pos 3)
        playsByRelativePos[3]?.let { play ->
            TrickCard(play = play, trumpSuit = trumpSuit, modifier = Modifier.align(Alignment.CenterEnd))
        }
    }
}

@Composable
private fun TrickCard(play: PlayedCard, trumpSuit: Suit?, modifier: Modifier = Modifier) {
    val card = runCatching { Card.fromId(play.cardId) }.getOrNull() ?: return
    CardFace(
        card = card,
        isTrump = trumpSuit != null && card.suit == trumpSuit,
        modifier = modifier
            .height(80.dp)
            .width(54.dp)
    )
}
