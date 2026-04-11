package com.maraffa.beccaccino.ui.screen.game.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.maraffa.beccaccino.data.model.Suit

@Composable
fun TrumpSelectionDialog(onTrumpSelected: (Suit) -> Unit) {
    AlertDialog(
        onDismissRequest = {},  // Cannot dismiss - must select
        title = {
            Text(
                "Scegli la Briscola",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold
            )
        },
        text = {
            Column {
                Text(
                    "Hai il 4 di Denari.\nScegli il seme briscola per questa mano.",
                    style = MaterialTheme.typography.bodyMedium,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth()
                )
                Spacer(modifier = Modifier.height(16.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceEvenly
                ) {
                    Suit.values().forEach { suit ->
                        SuitButton(suit = suit, onClick = { onTrumpSelected(suit) })
                    }
                }
            }
        },
        confirmButton = {}
    )
}

@Composable
private fun SuitButton(suit: Suit, onClick: () -> Unit) {
    val suitColor = when (suit) {
        Suit.COINS, Suit.CUPS -> Color(0xFFB71C1C)
        Suit.SWORDS, Suit.CLUBS -> Color(0xFF212121)
    }

    Card(
        modifier = Modifier
            .size(64.dp)
            .clickable { onClick() },
        colors = CardDefaults.cardColors(containerColor = Color(0xFFFFFDE7))
    ) {
        Column(
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Text(suit.symbol, color = suitColor, fontSize = 24.sp, fontWeight = FontWeight.Bold)
            Text(suit.displayName, color = suitColor, fontSize = 9.sp)
        }
    }
}
