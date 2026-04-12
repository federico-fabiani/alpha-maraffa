import { useShallow } from 'zustand/react/shallow'
import useGameStore from '../store'
import { Card as CardComponent } from '../components/Card'
import PlayerArea from '../components/PlayerArea'
import TableArea from '../components/TableArea'
import ScoreBoard from '../components/ScoreBoard'
import BriscolaIndicator from '../components/BriscolaIndicator'
import BriscolaModal from '../components/BriscolaModal'
import Notification from '../components/Notification'
import type { Card } from '../types'

export default function GameScreen() {
  const {
    mySeat, players, myHand, phase,
    briscola, currentPlayerSeat, tableCards,
    round, turn, totalScores, roundScores,
    notification, briscolaSelectorSeat,
  } = useGameStore(useShallow(s => ({
    mySeat: s.mySeat,
    players: s.players,
    myHand: s.myHand,
    phase: s.phase,
    briscola: s.briscola,
    currentPlayerSeat: s.currentPlayerSeat,
    tableCards: s.tableCards,
    round: s.round,
    turn: s.turn,
    totalScores: s.totalScores,
    roundScores: s.roundScores,
    notification: s.notification,
    briscolaSelectorSeat: s.briscolaSelectorSeat,
  })))

  const playCard        = useGameStore(s => s.playCard)
  const selectBriscola  = useGameStore(s => s.selectBriscola)
  const dismissNotif    = useGameStore(s => s.dismissNotification)

  const seat = mySeat ?? 0

  // Relative seat positions around the table
  const topSeat   = (seat + 2) % 4
  const rightSeat = (seat + 1) % 4
  const leftSeat  = (seat + 3) % 4

  const playerBySeat = Object.fromEntries(players.map(p => [p.seat, p]))

  const isMyTurn       = currentPlayerSeat === seat && phase === 'playing'
  const needsBriscola  = phase === 'briscola_selection' && currentPlayerSeat === seat

  const handleCardClick = (card: Card) => {
    if (isMyTurn && card.playable) playCard(card)
  }

  return (
    <div className="relative w-full h-full overflow-hidden select-none">

      {/* ── HUD ── */}
      <div className="absolute top-3 left-3 z-10">
        <ScoreBoard
          round={round}
          turn={turn}
          totalScores={totalScores}
          roundScores={roundScores}
        />
      </div>
      {briscola && (
        <div className="absolute top-3 right-3 z-10">
          <BriscolaIndicator suit={briscola} />
        </div>
      )}

      {/* ── Opponent — top ── */}
      <div className="absolute top-6 left-1/2 -translate-x-1/2">
        <PlayerArea
          player={playerBySeat[topSeat]}
          isActive={currentPlayerSeat === topSeat}
          position="top"
        />
      </div>

      {/* ── Opponent — left ── */}
      <div className="absolute left-4 top-1/2 -translate-y-1/2">
        <PlayerArea
          player={playerBySeat[leftSeat]}
          isActive={currentPlayerSeat === leftSeat}
          position="left"
        />
      </div>

      {/* ── Opponent — right ── */}
      <div className="absolute right-4 top-1/2 -translate-y-1/2">
        <PlayerArea
          player={playerBySeat[rightSeat]}
          isActive={currentPlayerSeat === rightSeat}
          position="right"
        />
      </div>

      {/* ── Centre table ── */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <TableArea tableCards={tableCards} mySeat={seat} />
      </div>

      {/* ── My name badge ── */}
      <div className="absolute bottom-36 left-1/2 -translate-x-1/2">
        {playerBySeat[seat] && (
          <div className={`
            px-3 py-1 rounded-full text-xs font-medium border
            ${playerBySeat[seat]?.team === 1
              ? 'border-amber-500/50 text-amber-300 bg-amber-900/20'
              : 'border-blue-500/50 text-blue-300 bg-blue-900/20'}
            ${isMyTurn ? 'animate-pulse-ring' : ''}
          `}>
            {playerBySeat[seat]?.name}
            {isMyTurn && <span className="ml-1 text-amber-400">●</span>}
          </div>
        )}
      </div>

      {/* ── My hand ── */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-1.5">
        {myHand.map((card, i) => (
          <CardComponent
            key={`${card.suit}-${card.rank}-${i}`}
            card={card}
            size="md"
            onClick={() => handleCardClick(card)}
          />
        ))}
      </div>

      {/* ── Briscola selection modal ── */}
      {needsBriscola && (
        <BriscolaModal onSelect={selectBriscola} selectorName={playerBySeat[briscolaSelectorSeat ?? seat]?.name} />
      )}

      {/* ── Turn notification ── */}
      {notification && (
        <Notification
          notification={notification}
          onDismiss={dismissNotif}
        />
      )}
    </div>
  )
}
