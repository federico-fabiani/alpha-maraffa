package com.maraffa.beccaccino.ui.screen.game.components

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.maraffa.beccaccino.data.model.Card
import com.maraffa.beccaccino.data.model.Suit

@Composable
fun CardFace(
    card: Card,
    isLegal: Boolean = true,
    isSelected: Boolean = false,
    isTrump: Boolean = false,
    modifier: Modifier = Modifier
) {
    val suitColor = when (card.suit) {
        Suit.COINS, Suit.CUPS -> Color(0xFFB71C1C)
        Suit.SWORDS, Suit.CLUBS -> Color(0xFF212121)
    }

    val borderColor = when {
        isSelected -> Color(0xFFFFD700)         // Gold when selected
        isTrump -> Color(0xFFFF6F00)            // Orange when trump
        !isLegal -> Color.Gray.copy(alpha = 0.3f)
        else -> Color.LightGray.copy(alpha = 0.5f)
    }

    val borderWidth = if (isSelected || isTrump) 3.dp else 1.dp

    Card(
        modifier = modifier
            .alpha(if (!isLegal) 0.5f else 1f)
            .border(borderWidth, borderColor, RoundedCornerShape(8.dp)),
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFFFFFDE7)),
        elevation = CardDefaults.cardElevation(if (isSelected) 8.dp else 2.dp)
    ) {
        Box(modifier = Modifier.fillMaxSize().padding(4.dp)) {
            // Top-left rank + suit
            Column(
                modifier = Modifier.align(Alignment.TopStart),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = card.rank.displayName,
                    color = suitColor,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold,
                    lineHeight = 14.sp
                )
                Text(
                    text = card.suit.symbol,
                    color = suitColor,
                    fontSize = 11.sp,
                    lineHeight = 12.sp
                )
            }

            // Center suit symbol (large)
            Text(
                text = card.suit.symbol,
                color = suitColor,
                fontSize = 24.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.align(Alignment.Center),
                textAlign = TextAlign.Center
            )

            // Bottom-right rank + suit (rotated 180°)
            Column(
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .rotate(180f),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = card.rank.displayName,
                    color = suitColor,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold,
                    lineHeight = 14.sp
                )
                Text(
                    text = card.suit.symbol,
                    color = suitColor,
                    fontSize = 11.sp,
                    lineHeight = 12.sp
                )
            }
        }
    }
}

@Composable
fun CardBack(modifier: Modifier = Modifier) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(8.dp),
        colors = CardDefaults.cardColors(containerColor = Color(0xFF1A237E)),
        elevation = CardDefaults.cardElevation(2.dp)
    ) {
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center
        ) {
            Text("M", color = Color.White.copy(alpha = 0.3f), fontSize = 20.sp, fontWeight = FontWeight.Bold)
        }
    }
}
