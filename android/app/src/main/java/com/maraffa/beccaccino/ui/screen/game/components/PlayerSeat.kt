package com.maraffa.beccaccino.ui.screen.game.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.maraffa.beccaccino.data.model.Player
import com.maraffa.beccaccino.ui.theme.TeamAColor
import com.maraffa.beccaccino.ui.theme.TeamBColor

@Composable
fun PlayerSeat(
    player: Player?,
    cardCount: Int,
    isCurrentTurn: Boolean,
    isPartner: Boolean,
    modifier: Modifier = Modifier
) {
    val teamColor = when (player?.teamIndex) {
        0 -> TeamAColor
        1 -> TeamBColor
        else -> Color.Gray
    }

    Column(
        modifier = modifier.padding(4.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        // Avatar + turn indicator
        Box(contentAlignment = Alignment.Center) {
            Box(
                modifier = Modifier
                    .size(40.dp)
                    .background(
                        if (player != null) teamColor else Color.Gray.copy(alpha = 0.3f),
                        CircleShape
                    )
                    .then(
                        if (isCurrentTurn) Modifier.border(3.dp, Color.Yellow, CircleShape)
                        else Modifier
                    ),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = player?.displayName?.firstOrNull()?.uppercase() ?: "?",
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                    fontSize = 16.sp
                )
            }

            // Connection status indicator
            if (player != null && !player.isConnected) {
                Box(
                    modifier = Modifier
                        .size(12.dp)
                        .background(Color.Red, CircleShape)
                        .align(Alignment.BottomEnd)
                )
            }
        }

        // Name
        Text(
            text = player?.displayName ?: "...",
            color = Color.White,
            fontSize = 11.sp,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.widthIn(max = 70.dp)
        )

        // Partner label
        if (isPartner) {
            Text(
                "compagno",
                color = Color.White.copy(alpha = 0.6f),
                fontSize = 9.sp
            )
        }

        // Card count (face-down cards)
        Row(horizontalArrangement = Arrangement.spacedBy((-8).dp)) {
            repeat(minOf(cardCount, 5)) {
                CardBack(modifier = Modifier.height(30.dp).width(22.dp))
            }
            if (cardCount > 5) {
                Text("+${cardCount - 5}", color = Color.White, fontSize = 9.sp)
            }
        }
    }
}
