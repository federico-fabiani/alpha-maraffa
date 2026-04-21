package com.maraffa.beccaccino.ui.screen.game.components

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.maraffa.beccaccino.data.model.Declaration
import com.maraffa.beccaccino.data.model.DeclarationType
import com.maraffa.beccaccino.data.model.Player

@Composable
fun DeclarationBar(
    declaration: Declaration?,
    players: Map<String, Player>,
    modifier: Modifier = Modifier
) {
    AnimatedVisibility(
        visible = declaration != null,
        enter = slideInVertically() + fadeIn(),
        exit = slideOutVertically() + fadeOut(),
        modifier = modifier
    ) {
        if (declaration != null) {
            val player = players[declaration.playerUid]
            val declColor = when (declaration.type) {
                DeclarationType.BUSSO -> Color(0xFFFFD700)   // Gold
                DeclarationType.VOLO -> Color(0xFF64B5F6)    // Blue
                DeclarationType.STRISCIO -> Color(0xFFA5D6A7) // Green
            }

            Row(
                modifier = Modifier
                    .background(Color.Black.copy(alpha = 0.8f), RoundedCornerShape(20.dp))
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text(
                    text = declaration.type.displayName.uppercase(),
                    color = declColor,
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp
                )
                Text(
                    text = "— ${player?.displayName ?: "?"}",
                    color = Color.White,
                    fontSize = 12.sp
                )
                Text(
                    text = declaration.type.description,
                    color = Color.White.copy(alpha = 0.7f),
                    fontSize = 10.sp
                )
            }
        }
    }
}
