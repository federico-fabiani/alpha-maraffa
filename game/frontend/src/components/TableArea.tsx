import { Card } from './Card'
import type { TableCard } from '../types'

interface TableAreaProps {
  tableCards: TableCard[]
  mySeat: number
}

/** Position offsets for each seat's card on the table (relative to mySeat). */
function slotStyle(relativeSeat: number): React.CSSProperties {
  switch (relativeSeat) {
    case 0: return { bottom: '10px',  left: '50%', transform: 'translateX(-50%)' } // me
    case 1: return { right:  '10px',  top:  '50%', transform: 'translateY(-50%)' } // right
    case 2: return { top:    '10px',  left: '50%', transform: 'translateX(-50%)' } // opposite
    case 3: return { left:   '10px',  top:  '50%', transform: 'translateY(-50%)' } // left
    default: return {}
  }
}

export default function TableArea({ tableCards, mySeat }: TableAreaProps) {
  return (
    <div className="relative w-56 h-44 rounded-2xl bg-felt-800/40 border border-felt-700/30">

      {/* Felt centre circle */}
      <div className="absolute inset-4 rounded-xl bg-felt-700/20 border border-felt-600/10" />

      {tableCards.map(({ seat, card }) => {
        const relativeSeat = (seat - mySeat + 4) % 4
        return (
          <div
            key={seat}
            className="absolute animate-card-appear"
            style={slotStyle(relativeSeat)}
          >
            <Card card={card} size="table" />
          </div>
        )
      })}
    </div>
  )
}
