package com.maraffa.beccaccino.ui.screen.game

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.maraffa.beccaccino.data.model.DeclarationType
import com.maraffa.beccaccino.data.model.GamePhase
import com.maraffa.beccaccino.data.model.Suit
import com.maraffa.beccaccino.ui.screen.game.components.*
import com.maraffa.beccaccino.ui.theme.TableGreen
import com.maraffa.beccaccino.ui.theme.TeamAColor
import com.maraffa.beccaccino.ui.theme.TeamBColor

@Composable
fun GameScreen(
    onGameOver: (String) -> Unit,
    viewModel: GameViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val gameState = uiState.gameState

    // Navigate when game over
    LaunchedEffect(gameState.phase) {
        if (gameState.phase == GamePhase.GAME_OVER) {
            onGameOver(gameState.roomId)
        }
    }

    // Trump selection dialog
    if (gameState.phase == GamePhase.TRUMP_SELECTION && uiState.isMyTurn) {
        TrumpSelectionDialog(onTrumpSelected = viewModel::onTrumpSelected)
    }

    // Marafona announcement
    if (uiState.showMarafonaAnnouncement && gameState.marafonaTeam >= 0) {
        val teamName = if (gameState.marafonaTeam == 0) "Squadra A" else "Squadra B"
        AlertDialog(
            onDismissRequest = viewModel::dismissMarafonaAnnouncement,
            title = { Text("MARAFONA!", fontWeight = FontWeight.Bold, fontSize = 24.sp) },
            text = { Text("$teamName ha la Marafona! +3 punti bonus.") },
            confirmButton = {
                TextButton(onClick = viewModel::dismissMarafonaAnnouncement) { Text("OK") }
            }
        )
    }

    // Declaration buttons state
    var showDeclarationMenu by remember { mutableStateOf(false) }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(TableGreen)
    ) {
        // ─── Score board (top-left) ─────────────────────────────────────
        val trumpSuit = Suit.fromFirebaseKeyOrNull(gameState.trumpSuit)
        ScoreBoard(
            team0Score = gameState.team0Score,
            team1Score = gameState.team1Score,
            trumpSuit = trumpSuit,
            handNumber = gameState.handNumber,
            modifier = Modifier
                .align(Alignment.TopStart)
                .padding(8.dp)
        )

        // ─── Top opponent (2 seats away = partner's opposite) ──────────
        val topPlayer = uiState.seatedPlayers.getOrNull(2)
        PlayerSeat(
            player = topPlayer,
            cardCount = if (topPlayer != null) (uiState.gameState.completedTricks.size.let { 10 - it }).coerceAtLeast(0) else 0,
            isCurrentTurn = topPlayer?.uid == gameState.currentTurnUid,
            isPartner = false,
            modifier = Modifier
                .align(Alignment.TopCenter)
                .padding(top = 8.dp)
        )

        // ─── Left opponent ─────────────────────────────────────────────
        val leftPlayer = uiState.seatedPlayers.getOrNull(1)
        PlayerSeat(
            player = leftPlayer,
            cardCount = 0,
            isCurrentTurn = leftPlayer?.uid == gameState.currentTurnUid,
            isPartner = false,
            modifier = Modifier
                .align(Alignment.CenterStart)
                .padding(start = 8.dp)
        )

        // ─── Right opponent ────────────────────────────────────────────
        val rightPlayer = uiState.seatedPlayers.getOrNull(3)
        PlayerSeat(
            player = rightPlayer,
            cardCount = 0,
            isCurrentTurn = rightPlayer?.uid == gameState.currentTurnUid,
            isPartner = false,
            modifier = Modifier
                .align(Alignment.CenterEnd)
                .padding(end = 8.dp)
        )

        // ─── Trick area (center) ───────────────────────────────────────
        TrickArea(
            trick = gameState.currentTrick,
            players = gameState.players,
            myUid = viewModel.myUid,
            trumpSuit = trumpSuit,
            modifier = Modifier.align(Alignment.Center)
        )

        // ─── Turn indicator ────────────────────────────────────────────
        if (uiState.isMyTurn && gameState.phase == GamePhase.PLAYING) {
            Text(
                text = "Il tuo turno",
                color = Color.Yellow,
                fontWeight = FontWeight.Bold,
                fontSize = 14.sp,
                modifier = Modifier
                    .align(Alignment.Center)
                    .offset(y = 80.dp)
            )
        }

        // ─── Declaration bar ───────────────────────────────────────────
        DeclarationBar(
            declaration = gameState.declarations.lastOrNull(),
            players = gameState.players,
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .padding(bottom = 148.dp)
        )

        // ─── Declaration buttons (top-right) ──────────────────────────
        if (uiState.isMyTurn && gameState.phase == GamePhase.PLAYING) {
            Column(
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(8.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                DeclarationChip("Busso") {
                    viewModel.onDeclaration(
                        DeclarationType.BUSSO,
                        trumpSuit ?: Suit.COINS
                    )
                }
                DeclarationChip("Volo") {
                    viewModel.onDeclaration(
                        DeclarationType.VOLO,
                        trumpSuit ?: Suit.COINS
                    )
                }
                DeclarationChip("Striscio") {
                    viewModel.onDeclaration(
                        DeclarationType.STRISCIO,
                        trumpSuit ?: Suit.COINS
                    )
                }
            }
        }

        // ─── My hand (bottom) ──────────────────────────────────────────
        Column(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
        ) {
            // Hint text for selected card
            uiState.selectedCard?.let { card ->
                Text(
                    text = "Tap di nuovo per giocare ${card.rank.displayName} di ${card.suit.displayName}",
                    color = Color.Yellow,
                    fontSize = 12.sp,
                    modifier = Modifier
                        .align(Alignment.CenterHorizontally)
                        .padding(bottom = 4.dp)
                )
            }

            CardHandRow(
                cards = uiState.myHand,
                legalCards = uiState.legalCards,
                selectedCard = uiState.selectedCard,
                onCardSelected = viewModel::onCardSelected,
                onCardPlayed = viewModel::onCardPlayed,
                isMyTurn = uiState.isMyTurn,
                trumpSuit = trumpSuit,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 8.dp)
            )
        }

        // ─── Error snackbar ────────────────────────────────────────────
        uiState.error?.let { error ->
            Snackbar(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 160.dp, start = 16.dp, end = 16.dp),
                action = {
                    TextButton(onClick = viewModel::clearError) { Text("OK") }
                }
            ) {
                Text(error)
            }
        }

        // ─── Loading overlay ───────────────────────────────────────────
        if (uiState.isLoading) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Color.Black.copy(alpha = 0.5f)),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = Color.White)
            }
        }
    }
}

@Composable
private fun DeclarationChip(label: String, onClick: () -> Unit) {
    SmallFloatingActionButton(
        onClick = onClick,
        containerColor = Color.Black.copy(alpha = 0.7f),
        contentColor = Color.White,
        modifier = Modifier.height(32.dp)
    ) {
        Text(label, fontSize = 11.sp, modifier = Modifier.padding(horizontal = 8.dp))
    }
}
