package com.maraffa.beccaccino.ui.screen.result

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.maraffa.beccaccino.ui.theme.TableGreen
import com.maraffa.beccaccino.ui.theme.TeamAColor
import com.maraffa.beccaccino.ui.theme.TeamBColor

@Composable
fun ResultScreen(
    onHome: () -> Unit,
    viewModel: ResultViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(TableGreen),
        contentAlignment = Alignment.Center
    ) {
        if (uiState.isLoading) {
            CircularProgressIndicator(color = Color.White)
        } else {
            Card(
                modifier = Modifier
                    .fillMaxWidth(0.9f)
                    .padding(16.dp),
                elevation = CardDefaults.cardElevation(8.dp)
            ) {
                Column(
                    modifier = Modifier
                        .padding(24.dp)
                        .fillMaxWidth(),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    // Win/Lose heading
                    Text(
                        text = if (uiState.myTeamWon) "Hai Vinto!" else "Hai Perso",
                        style = MaterialTheme.typography.headlineLarge,
                        fontWeight = FontWeight.Bold,
                        color = if (uiState.myTeamWon) Color(0xFF2E7D32) else MaterialTheme.colorScheme.error,
                        textAlign = TextAlign.Center
                    )

                    Text(
                        text = "${uiState.handNumber} mani giocate",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )

                    HorizontalDivider()

                    // Score comparison
                    Text("Punteggio Finale", style = MaterialTheme.typography.titleMedium)

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceEvenly
                    ) {
                        TeamScoreCard(
                            teamName = "Squadra A",
                            score = uiState.team0Score,
                            isWinner = uiState.winningTeam == 0,
                            isMyTeam = uiState.myTeamIndex == 0,
                            color = TeamAColor
                        )
                        TeamScoreCard(
                            teamName = "Squadra B",
                            score = uiState.team1Score,
                            isWinner = uiState.winningTeam == 1,
                            isMyTeam = uiState.myTeamIndex == 1,
                            color = TeamBColor
                        )
                    }

                    // Marafona note
                    if (uiState.marafonaTeam >= 0) {
                        val teamName = if (uiState.marafonaTeam == 0) "Squadra A" else "Squadra B"
                        Card(
                            colors = CardDefaults.cardColors(
                                containerColor = Color(0xFFFFD700).copy(alpha = 0.2f)
                            )
                        ) {
                            Text(
                                "★ $teamName ha dichiarato Marafona (+3 punti)",
                                modifier = Modifier.padding(8.dp),
                                style = MaterialTheme.typography.bodySmall,
                                color = Color(0xFFB8860B),
                                textAlign = TextAlign.Center
                            )
                        }
                    }

                    HorizontalDivider()

                    // Home button
                    Button(
                        onClick = onHome,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text("Torna alla Home")
                    }
                }
            }
        }
    }
}

@Composable
private fun TeamScoreCard(
    teamName: String,
    score: Float,
    isWinner: Boolean,
    isMyTeam: Boolean,
    color: Color
) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = if (isWinner) color.copy(alpha = 0.2f) else MaterialTheme.colorScheme.surfaceVariant
        ),
        modifier = Modifier.width(120.dp)
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(teamName, fontWeight = FontWeight.Bold, color = color, fontSize = 14.sp)
            if (isMyTeam) Text("(tu)", fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            Text(
                "%.1f".format(score),
                fontSize = 28.sp,
                fontWeight = FontWeight.Bold,
                color = if (isWinner) color else MaterialTheme.colorScheme.onSurface
            )
            Text("punti", fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (isWinner) {
                Text("★ Vincitore", color = color, fontSize = 11.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
}
