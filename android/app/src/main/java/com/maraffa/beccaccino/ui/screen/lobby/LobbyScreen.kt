package com.maraffa.beccaccino.ui.screen.lobby

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PersonOutline
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.maraffa.beccaccino.data.model.Player
import com.maraffa.beccaccino.ui.theme.TableGreen
import com.maraffa.beccaccino.ui.theme.TeamAColor
import com.maraffa.beccaccino.ui.theme.TeamBColor

@Composable
fun LobbyScreen(
    onGameStarted: (String) -> Unit,
    onBack: () -> Unit,
    viewModel: LobbyViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(uiState.gameStarted) {
        if (uiState.gameStarted) onGameStarted(uiState.roomId)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(TableGreen)
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(modifier = Modifier.height(24.dp))

        Text(
            text = "Stanza",
            style = MaterialTheme.typography.headlineMedium,
            color = Color.White
        )

        // Room code display
        Card(
            modifier = Modifier.padding(16.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
        ) {
            Column(
                modifier = Modifier.padding(16.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text("Codice Stanza", style = MaterialTheme.typography.labelSmall)
                Text(
                    text = uiState.roomCode,
                    style = MaterialTheme.typography.headlineLarge,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.secondary
                )
                Text(
                    "Condividi con 3 amici",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        // Player seats
        Text(
            "Giocatori (${uiState.players.size}/4)",
            style = MaterialTheme.typography.titleMedium,
            color = Color.White
        )

        Spacer(modifier = Modifier.height(8.dp))

        // Team A
        TeamSection(
            teamName = "Squadra A",
            teamColor = TeamAColor,
            seats = listOf(0, 2),
            players = uiState.players
        )

        Spacer(modifier = Modifier.height(8.dp))

        // Team B
        TeamSection(
            teamName = "Squadra B",
            teamColor = TeamBColor,
            seats = listOf(1, 3),
            players = uiState.players
        )

        Spacer(modifier = Modifier.weight(1f))

        // Error
        uiState.error?.let {
            Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(8.dp))
        }

        // Start button (host only, 4 players needed)
        if (uiState.isHost) {
            Button(
                onClick = viewModel::onStartGame,
                enabled = uiState.canStart && !uiState.isLoading,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp)
            ) {
                if (uiState.isLoading) {
                    CircularProgressIndicator(modifier = Modifier.size(24.dp), color = Color.White)
                } else {
                    Text(
                        if (uiState.canStart) "Inizia Partita" else "In attesa dei giocatori...",
                        style = MaterialTheme.typography.titleMedium
                    )
                }
            }
        } else {
            Text(
                "In attesa che l'host avvii la partita...",
                style = MaterialTheme.typography.bodyMedium,
                color = Color.White.copy(alpha = 0.7f)
            )
        }

        Spacer(modifier = Modifier.height(16.dp))
    }
}

@Composable
private fun TeamSection(
    teamName: String,
    teamColor: Color,
    seats: List<Int>,
    players: List<Player>
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = teamColor.copy(alpha = 0.2f))
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(
                teamName,
                style = MaterialTheme.typography.titleMedium,
                color = teamColor,
                fontWeight = FontWeight.Bold
            )
            seats.forEach { seatIndex ->
                val player = players.firstOrNull { it.seatIndex == seatIndex }
                PlayerSlot(seatIndex = seatIndex, player = player)
            }
        }
    }
}

@Composable
private fun PlayerSlot(seatIndex: Int, player: Player?) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = if (player != null) Icons.Filled.Person else Icons.Filled.PersonOutline,
            contentDescription = null,
            tint = if (player != null) MaterialTheme.colorScheme.primary else Color.Gray,
            modifier = Modifier.size(24.dp)
        )
        Spacer(modifier = Modifier.width(8.dp))
        Column {
            Text(
                text = player?.displayName ?: "In attesa...",
                style = MaterialTheme.typography.bodyMedium,
                color = if (player != null) MaterialTheme.colorScheme.onSurface else Color.Gray
            )
            if (player != null && !player.isConnected) {
                Text(
                    "Disconnesso",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.error
                )
            }
        }
        Spacer(modifier = Modifier.weight(1f))
        Text(
            "Posto ${seatIndex + 1}",
            style = MaterialTheme.typography.labelSmall,
            color = Color.Gray
        )
    }
}
