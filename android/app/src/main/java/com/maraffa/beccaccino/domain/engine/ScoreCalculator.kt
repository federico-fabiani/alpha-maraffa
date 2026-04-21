package com.maraffa.beccaccino.domain.engine

import com.maraffa.beccaccino.data.model.Card
import com.maraffa.beccaccino.data.model.HandScore
import com.maraffa.beccaccino.data.model.Player
import com.maraffa.beccaccino.data.model.Trick
import javax.inject.Inject

class ScoreCalculator @Inject constructor() {

    /**
     * Calculates the points earned by each team in a completed hand (10 tricks).
     *
     * Scoring:
     *  - Ace = 1.0 pt
     *  - 2, 3, King, Horse, Jack = 1/3 pt each
     *  - 7, 6, 5, 4 = 0 pt
     *  - Last trick winner gets +1 pt bonus
     *  - Marafona team gets +3 pt bonus
     *
     * Total distributable per hand = 4×1 + 8×(1/3) + 3×4×(1/3) + 1 = 4 + 8/3 + 4 + 1 = 11 pt
     *
     * @param completedTricks All 10 completed tricks for this hand
     * @param players Map of uid -> Player (needed to determine team from uid)
     * @param marafonaTeam Team index (0 or 1) that declared marafona, or -1 if none
     * @param handNumber Current hand number for the HandScore record
     */
    fun calculateHandScore(
        completedTricks: List<Trick>,
        players: Map<String, Player>,
        marafonaTeam: Int,
        handNumber: Int = 0
    ): HandScore {
        require(completedTricks.size == 10) { "A hand has exactly 10 tricks" }

        val teamPoints = mutableMapOf(0 to 0f, 1 to 0f)

        completedTricks.forEach { trick ->
            val winnerPlayer = players[trick.winnerUid]
                ?: error("Winner UID '${trick.winnerUid}' not found in players map")
            val winnerTeam = winnerPlayer.teamIndex

            val trickPipPoints = trick.plays.sumOf { play ->
                Card.fromId(play.cardId).rank.pointValue.toDouble()
            }.toFloat()

            teamPoints[winnerTeam] = (teamPoints[winnerTeam] ?: 0f) + trickPipPoints
        }

        // Last trick bonus (+1 pt)
        val lastTrickWinnerTeam = players[completedTricks.last().winnerUid]!!.teamIndex
        teamPoints[lastTrickWinnerTeam] = (teamPoints[lastTrickWinnerTeam] ?: 0f) + 1f

        // Marafona bonus (+3 pt)
        if (marafonaTeam in 0..1) {
            teamPoints[marafonaTeam] = (teamPoints[marafonaTeam] ?: 0f) + 3f
        }

        return HandScore(
            handNumber = handNumber,
            team0Points = teamPoints[0] ?: 0f,
            team1Points = teamPoints[1] ?: 0f,
            marafonaTeam = marafonaTeam
        )
    }

    fun isGameOver(team0Total: Float, team1Total: Float): Boolean =
        team0Total >= 41f || team1Total >= 41f

    fun getWinningTeam(team0Total: Float, team1Total: Float): Int =
        if (team0Total >= team1Total) 0 else 1
}
