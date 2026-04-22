import { useEffect, useRef, useState } from 'react'
import { Card } from './Card'
import type { TableCard } from '../types'

interface TableAreaProps {
  tableCards: TableCard[]
  mySeat: number
  winnerSeat?: number | null
}

/** Position offsets for each seat's card on the table (relative to mySeat). */
function slotStyle(relativeSeat: number): React.CSSProperties {
  switch (relativeSeat) {
    case 0: return { left: '50%', top: 'calc(50% + var(--table-card-spread-y))', transform: 'translate(-50%, -50%) rotate(-4deg)' }
    case 1: return { left: 'calc(50% + var(--table-card-spread-x))', top: '50%', transform: 'translate(-50%, -50%) rotate(6deg)' }
    case 2: return { left: '50%', top: 'calc(50% - var(--table-card-spread-y))', transform: 'translate(-50%, -50%) rotate(3deg)' }
    case 3: return { left: 'calc(50% - var(--table-card-spread-x))', top: '50%', transform: 'translate(-50%, -50%) rotate(-6deg)' }
    default: return {}
  }
}

/**
 * Per-card converging vectors toward each winner's hand position.
 * Outer key = winner's relative seat (0=me/bottom, 1=right, 2=top, 3=left).
 * Inner key = card's relative seat (same encoding).
 * Values are pixel offsets from each card's slot to the winner's hand area.
 *
 * Slot centres relative to table centre (approx):
 *   0 (bottom): ( 0, +90)   1 (right): (+120,  0)
 *   2 (top):    ( 0, -90)   3 (left):  (-120,  0)
 * Target positions (relative to table centre):
 *   winner 0 → (0, +340)   winner 1 → (+320,  0)
 *   winner 2 → (0, -340)   winner 3 → (-320,  0)
 */
const COLLECT_VECTORS: Record<number, Record<number, { x: number; y: number }>> = {
  0: { 0: { x:    0, y:  350 }, 1: { x: -200, y:  480 }, 2: { x:    0, y:  600 }, 3: { x:  200, y:  480 } },
  1: { 0: { x:  520, y: -140 }, 1: { x:  320, y:    0 }, 2: { x:  520, y:  140 }, 3: { x:  700, y:    0 } },
  2: { 0: { x:    0, y: -600 }, 1: { x: -200, y: -480 }, 2: { x:    0, y: -350 }, 3: { x:  200, y: -480 } },
  3: { 0: { x: -520, y: -140 }, 1: { x: -700, y:    0 }, 2: { x: -520, y:  140 }, 3: { x: -320, y:    0 } },
}

export default function TableArea({ tableCards, mySeat, winnerSeat }: TableAreaProps) {
  const prevCardsRef   = useRef<TableCard[]>([])
  const savedWinnerRef = useRef<number | null>(null)

  const [collecting, setCollecting] = useState<{
    cards: TableCard[]
    relativeSeat: number
  } | null>(null)

  // Keep a ref to the last known winner seat (store clears it together with tableCards)
  useEffect(() => {
    if (winnerSeat != null) savedWinnerRef.current = winnerSeat
  }, [winnerSeat])

  // When cards are cleared by the server, fire the collection animation
  useEffect(() => {
    const prev = prevCardsRef.current
    prevCardsRef.current = tableCards

    if (prev.length > 0 && tableCards.length === 0 && savedWinnerRef.current != null) {
      const rel = (savedWinnerRef.current - mySeat + 4) % 4
      savedWinnerRef.current = null
      setCollecting({ cards: prev, relativeSeat: rel })
      const t = setTimeout(() => setCollecting(null), 550)
      return () => clearTimeout(t)
    }
  }, [tableCards, mySeat])

  return (
    <div className="table-area relative w-full h-full z-[2]">

      {/* Live cards */}
      {tableCards.map(({ seat, card }) => {
        const relativeSeat = (seat - mySeat + 4) % 4
        return (
          <div
            key={seat}
            className={`absolute table-card-slot animate-card-appear${seat === winnerSeat ? ' winning-card' : ''}`}
            style={slotStyle(relativeSeat)}
          >
            <Card
              card={card}
              size="table"
              style={{
                width: 'var(--table-card-width)',
                height: 'var(--table-card-height)',
              }}
            />
          </div>
        )
      })}

      {/* Collection animation overlay — cards fly toward the winner */}
      {collecting && collecting.cards.map(({ seat, card }, idx) => {
        const relativeSeat = (seat - mySeat + 4) % 4
        const vec = COLLECT_VECTORS[collecting.relativeSeat][relativeSeat]
        return (
          <div
            key={`collect-${seat}`}
            className="absolute table-card-slot collecting-card"
            style={{
              ...slotStyle(relativeSeat),
              '--collect-x': `${vec.x}px`,
              '--collect-y': `${vec.y}px`,
              '--card-index': idx,
            } as React.CSSProperties}
          >
            <Card
              card={card}
              size="table"
              style={{
                width: 'var(--table-card-width)',
                height: 'var(--table-card-height)',
              }}
            />
          </div>
        )
      })}
    </div>
  )
}
