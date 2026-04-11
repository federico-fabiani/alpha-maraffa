package com.maraffa.beccaccino.ui.screen.game.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.maraffa.beccaccino.data.model.Suit
import com.maraffa.beccaccino.ui.theme.TeamAColor
import com.maraffa.beccaccino.ui.theme.TeamBColor

@Composable
fun ScoreBoard(
    team0Score: Float,
    team1Score: Float,
    trumpSuit: Suit?,
    handNumber: Int,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .background(Color.Black.copy(alpha = 0.6f), RoundedCornerShape(8.dp))
            .padding(8.dp),
        horizontalAlignment = Alignment.Start
    ) {
        // Trump indicator
        if (trumpSuit != null) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Briscola: ", color = Color.White, fontSize = 11.sp)
                Text(
                    trumpSuit.displayName,
                    color = when (trumpSuit) {
                        Suit.COINS, Suit.CUPS -> Color(0xFFEF5350)
                        else -> Color.White
                    },
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold
                )
            }
            Spacer(modifier = Modifier.height(2.dp))
        }

        // Hand number
        Text("Mano: $handNumber", color = Color.White.copy(alpha = 0.7f), fontSize = 10.sp)

        Spacer(modifier = Modifier.height(4.dp))

        // Scores
        ScoreRow(label = "A", score = team0Score, color = TeamAColor)
        ScoreRow(label = "B", score = team1Score, color = TeamBColor)

        // Target
        Text("(41 per vincere)", color = Color.White.copy(alpha = 0.5f), fontSize = 9.sp)
    }
}

@Composable
private fun ScoreRow(label: String, score: Float, color: Color) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            modifier = Modifier
                .size(16.dp)
                .background(color, RoundedCornerShape(3.dp)),
            contentAlignment = Alignment.Center
        ) {
            Text(label, color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Bold)
        }
        Spacer(Modifier.width(4.dp))
        Text(
            "%.1f".format(score),
            color = Color.White,
            fontSize = 14.sp,
            fontWeight = FontWeight.Bold
        )
    }
}
