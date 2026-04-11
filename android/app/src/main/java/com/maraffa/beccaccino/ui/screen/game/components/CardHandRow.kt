package com.maraffa.beccaccino.ui.screen.game.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.maraffa.beccaccino.data.model.Card
import com.maraffa.beccaccino.data.model.Suit

@Composable
fun CardHandRow(
    cards: List<Card>,
    legalCards: Set<String>,
    selectedCard: Card?,
    onCardSelected: (Card) -> Unit,
    onCardPlayed: (Card) -> Unit,
    isMyTurn: Boolean,
    trumpSuit: Suit?,
    modifier: Modifier = Modifier
) {
    LazyRow(
        modifier = modifier,
        contentPadding = PaddingValues(horizontal = 8.dp),
        horizontalArrangement = Arrangement.spacedBy((-20).dp)
    ) {
        items(cards, key = { it.id }) { card ->
            val isLegal = isMyTurn && card.id in legalCards
            val isSelected = card == selectedCard
            val isTrump = trumpSuit != null && card.suit == trumpSuit

            CardFace(
                card = card,
                isLegal = isLegal || !isMyTurn,
                isSelected = isSelected,
                isTrump = isTrump,
                modifier = Modifier
                    .height(110.dp)
                    .width(72.dp)
                    .offset(y = if (isSelected) (-16).dp else 0.dp)
                    .clickable(enabled = isMyTurn && isLegal) {
                        if (isSelected) {
                            onCardPlayed(card)
                        } else {
                            onCardSelected(card)
                        }
                    }
            )
        }
    }
}
