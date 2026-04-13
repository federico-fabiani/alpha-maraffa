import { useEffect, useMemo, useRef, useState } from 'react'
import { useShallow } from 'zustand/react/shallow'
import useGameStore from '../store'
import { Card as CardComponent, SUIT_META } from '../components/Card'
import PlayerArea from '../components/PlayerArea'
import TableArea from '../components/TableArea'
import ScoreBoard from '../components/ScoreBoard'
import BriscolaIndicator from '../components/BriscolaIndicator'
import BriscolaModal from '../components/BriscolaModal'
import Notification from '../components/Notification'
import type { BriscolaAnnouncement, Card, Suit } from '../types'

const SUIT_ORDER: Record<Suit, number> = {
  bastoni: 0,
  denara: 1,
  spade: 2,
  coppe: 3,
}

const CARD_ORDER: Record<number, number> = {
  3: 9,
  2: 8,
  1: 7,
  10: 6,
  9: 5,
  8: 4,
  7: 3,
  6: 2,
  5: 1,
  4: 0,
}
export default function GameScreen() {
  const {
    mySeat, players, myHand, phase,
    briscola, briscolaAnnouncement, currentPlayerSeat, tableCards, turnResultWinnerSeat,
    round, turn, totalScores,
    notification, briscolaSelectorSeat,
  } = useGameStore(useShallow(s => ({
    mySeat: s.mySeat,
    players: s.players,
    myHand: s.myHand,
    phase: s.phase,
    briscola: s.briscola,
    briscolaAnnouncement: s.briscolaAnnouncement,
    currentPlayerSeat: s.currentPlayerSeat,
    tableCards: s.tableCards,
    turnResultWinnerSeat: s.turnResultWinnerSeat,
    round: s.round,
    turn: s.turn,
    totalScores: s.totalScores,
    notification: s.notification,
    briscolaSelectorSeat: s.briscolaSelectorSeat,
  })))

  const playCard        = useGameStore(s => s.playCard)
  const selectBriscola  = useGameStore(s => s.selectBriscola)
  const showNotification = useGameStore(s => s.showNotification)
  const dismissNotif    = useGameStore(s => s.dismissNotification)

  // ── Drag-to-play state ────────────────────────────────────────────────────────
  const [drag, setDrag] = useState<{
    card: Card
    x: number
    y: number
    startX: number
    startY: number
  } | null>(null)
  const [showCornerBriscola, setShowCornerBriscola] = useState(false)
  const [cornerToastPop, setCornerToastPop] = useState(false)
  const [briscolaReveal, setBriscolaReveal] = useState<(BriscolaAnnouncement & { fadingOut: boolean }) | null>(null)
  const lastBriscolaEventRef = useRef<number | null>(null)

  const dragDist     = drag ? Math.hypot(drag.x - drag.startX, drag.y - drag.startY) : 0
  const isActiveDrag = dragDist > 8
  const isDragOver   = drag !== null && (drag.startY - drag.y) > 90

  const handleCardPointerDown = (e: React.PointerEvent, card: Card) => {
    if (!isMyTurn || !card.playable) return
    setDrag({ card, x: e.clientX, y: e.clientY, startX: e.clientX, startY: e.clientY })
  }

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!drag) return
    setDrag(prev => prev ? { ...prev, x: e.clientX, y: e.clientY } : null)
  }

  const handlePointerUp = (e: React.PointerEvent) => {
    if (!drag) return
    if ((drag.startY - e.clientY) > 90 && drag.card.playable && isMyTurn) {
      playCard(drag.card)
    }
    setDrag(null)
  }

  const seat = mySeat ?? 0

  // Relative seat positions around the table
  const topSeat   = (seat + 2) % 4
  const rightSeat = (seat + 1) % 4
  const leftSeat  = (seat + 3) % 4

  const playerBySeat = Object.fromEntries(players.map(p => [p.seat, p]))

  const isMyTurn       = currentPlayerSeat === seat && phase === 'playing'
  const needsBriscola  = phase === 'briscola_selection' && currentPlayerSeat === seat
  const briscolaChooserName = currentPlayerSeat != null
    ? playerBySeat[currentPlayerSeat]?.name ?? 'Un giocatore'
    : 'Un giocatore'

  const handleCardClick = (card: Card) => {
    if (!card.playable) {
      showNotification({
        text: 'Mossa non valida',
        subtitle: 'Questa carta non e giocabile in questo turno.',
        duration: 1400,
      })
      return
    }

    if (isMyTurn) playCard(card)
  }

  const sortedHand = useMemo(() => {
    return myHand.map((card, index) => ({ card, index })).sort((a, b) => {
      const suitDiff = SUIT_ORDER[a.card.suit] - SUIT_ORDER[b.card.suit]
      if (suitDiff !== 0) return suitDiff

      const pointsDiff = CARD_ORDER[b.card.rank] - CARD_ORDER[a.card.rank]
      if (pointsDiff !== 0) return pointsDiff

      const rankDiff = b.card.rank - a.card.rank
      if (rankDiff !== 0) return rankDiff

      return a.index - b.index
    })
  }, [myHand])

  useEffect(() => {
    if (!briscola) {
      setBriscolaReveal(null)
      setShowCornerBriscola(false)
      setCornerToastPop(false)
      lastBriscolaEventRef.current = null
      return
    }

    if (!briscolaAnnouncement) {
      setShowCornerBriscola(true)
      setCornerToastPop(false)
      return
    }

    if (lastBriscolaEventRef.current === briscolaAnnouncement.eventId) {
      setBriscolaReveal(null)
      setShowCornerBriscola(true)
      setCornerToastPop(false)
      return
    }

    setShowCornerBriscola(false)
    setCornerToastPop(false)
    setBriscolaReveal({ ...briscolaAnnouncement, fadingOut: false })

    const fadeTimer = window.setTimeout(() => {
      setBriscolaReveal(prev => {
        if (!prev || prev.eventId !== briscolaAnnouncement.eventId) return prev
        return { ...prev, fadingOut: true }
      })
    }, 980)

    const clearCenterTimer = window.setTimeout(() => {
      setBriscolaReveal(null)
    }, 1320)

    const cornerPopTimer = window.setTimeout(() => {
      setShowCornerBriscola(true)
      setCornerToastPop(true)
      lastBriscolaEventRef.current = briscolaAnnouncement.eventId
    }, 1400)

    const cornerPopOffTimer = window.setTimeout(() => {
      setCornerToastPop(false)
    }, 1850)

    return () => {
      window.clearTimeout(fadeTimer)
      window.clearTimeout(clearCenterTimer)
      window.clearTimeout(cornerPopTimer)
      window.clearTimeout(cornerPopOffTimer)
    }
  }, [briscola, briscolaAnnouncement])

  const revealMeta = briscolaReveal ? SUIT_META[briscolaReveal.suit] : null
  const isWaitingBriscola = phase === 'briscola_selection' && !needsBriscola && !briscolaReveal

  return (
    <div
      className="game-stage relative w-full h-full overflow-hidden select-none touch-none"
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={() => setDrag(null)}
      onPointerLeave={() => setDrag(null)}
    >
      <div className="game-stage-ambient" />
      <div className="game-stage-vignette" />

      {/* ── HUD ── */}
      <div className="absolute top-3 left-3 z-10">
        <ScoreBoard
          round={round}
          turn={turn}
          totalScores={totalScores}
        />
      </div>
      {briscola && (
        <div
          className={`absolute top-3 right-3 z-10 transform-gpu transition-opacity duration-300 ease-out ${showCornerBriscola ? 'opacity-100' : 'opacity-0 pointer-events-none'} ${cornerToastPop ? 'corner-toast-pop' : ''}`}
        >
          <BriscolaIndicator suit={briscola} />
        </div>
      )}

      {briscolaReveal && revealMeta && (
        <div
          className={`briscola-reveal ${briscolaReveal.fadingOut ? 'fade-out' : ''}`}
          style={{ '--briscola-accent': revealMeta.color } as React.CSSProperties}
        >
          <p className="briscola-reveal-title">
            {briscolaReveal.byName} ha scelto come briscola {revealMeta.label.toUpperCase()}
          </p>
          <p className="briscola-reveal-subtitle">Briscola scelta</p>
          <div className="briscola-reveal-icon" aria-hidden="true">{revealMeta.symbol}</div>
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
        <TableArea tableCards={tableCards} mySeat={seat} winnerSeat={turnResultWinnerSeat} />
      </div>

      {/* ── My name badge ── */}
      <div className="absolute bottom-[10.75rem] left-1/2 -translate-x-1/2 z-10">
        {playerBySeat[seat] && (
          <div className={`
            px-3.5 py-1.5 rounded-full text-xs font-semibold border shadow-lg backdrop-blur-sm
            ${playerBySeat[seat]?.team === 1
              ? 'border-amber-400/70 text-amber-100 bg-felt-950/85'
              : 'border-blue-400/70 text-blue-100 bg-felt-950/85'}
            ${isMyTurn ? 'animate-pulse-ring' : ''}
          `}>
            {playerBySeat[seat]?.name}
            {isMyTurn && <span className="ml-1 text-amber-400">●</span>}
          </div>
        )}
      </div>

      {/* ── Drop zone indicator (appears while dragging) ── */}
      {isActiveDrag && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-20">
          <div className={`
            rounded-full border-2 transition-all duration-200
            ${isDragOver
              ? 'w-36 h-36 border-amber-400/75 bg-amber-400/10 shadow-[0_0_32px_rgba(251,191,36,0.2)]'
              : 'w-28 h-28 border-white/15'
            }
          `} />
        </div>
      )}

      {/* ── My hand ── */}
      <div className={`absolute bottom-11 left-1/2 -translate-x-1/2 z-20 ${isActiveDrag ? 'pointer-events-none' : ''}`}>
        <div className="player-hand">
          {sortedHand.map(({ card }, i) => {
            const handOffset = i - (sortedHand.length - 1) / 2
            const isBeingDragged = isActiveDrag
              && drag?.card.suit === card.suit
              && drag?.card.rank === card.rank
            const isBriscolaIdle = phase === 'briscola_selection' && !card.playable
            return (
              <div
                key={`${card.suit}-${card.rank}`}
                className="hand-card-slot"
                style={{
                  '--hand-index': i,
                  '--hand-offset': handOffset,
                  '--hand-offset-abs': Math.abs(handOffset),
                } as React.CSSProperties}
                onPointerDown={(e) => handleCardPointerDown(e, card)}
              >
                <CardComponent
                  card={card}
                  size="md"
                  onClick={() => handleCardClick(card)}
                  className={`${isBeingDragged ? 'opacity-0' : ''} ${isBriscolaIdle ? 'idle-floating' : ''}`.trim()}
                />
              </div>
            )
          })}
        </div>
      </div>

      {/* ── Drag ghost ── */}
      {isActiveDrag && drag && (
        <div
          className="fixed pointer-events-none z-50"
          style={{
            left: drag.x - 36,
            top: drag.y - 54,
            transform: `rotate(-4deg) scale(${isDragOver ? 1.1 : 1.04})`,
            transition: 'transform 0.12s ease, filter 0.12s ease',
            filter: 'drop-shadow(0 10px 24px rgba(0,0,0,0.55))',
          }}
        >
          <CardComponent card={drag.card} size="md" />
        </div>
      )}

      {/* ── Briscola selection modal ── */}
      {needsBriscola && (
        <BriscolaModal onSelect={selectBriscola} selectorName={playerBySeat[briscolaSelectorSeat ?? seat]?.name} />
      )}

      {/* ── Briscola waiting banner ── */}
      {isWaitingBriscola && (
        <div className="absolute inset-0 z-30 pointer-events-none flex items-center justify-center px-6">
          <div className="bg-felt-900/92 border border-amber-800/50 rounded-2xl px-7 py-4 text-center shadow-2xl backdrop-blur-sm animate-fade-in">
            <p className="text-amber-200 font-semibold text-base md:text-lg">
              {briscolaChooserName} sta scegliendo le briscole...
            </p>
          </div>
        </div>
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
