import { Card } from './Card'
import type { TableCard } from '../types'

interface TableAreaProps {
  tableCards: TableCard[]
  mySeat: number
}

/** Position offsets for each seat's card on the table (relative to mySeat). */
function slotStyle(relativeSeat: number): React.CSSProperties {
  switch (relativeSeat) {
    case 0: return { bottom: '12px',  left: '50%', transform: 'translateX(-50%) rotate(-4deg)' } // me
    case 1: return { right:  '12px',  top:  '50%', transform: 'translateY(-50%) rotate(6deg)' } // right
    case 2: return { top:    '12px',  left: '50%', transform: 'translateX(-50%) rotate(3deg)' } // opposite
    case 3: return { left:   '12px',  top:  '50%', transform: 'translateY(-50%) rotate(-6deg)' } // left
    default: return {}
  }
}

export default function TableArea({ tableCards, mySeat }: TableAreaProps) {
  return (
    <div className="table-area relative w-72 h-52 rounded-3xl">

      {/* Felt centre circle */}
      <div className="absolute inset-4 rounded-2xl table-area-inner" />

      {tableCards.map(({ seat, card }) => {
        const relativeSeat = (seat - mySeat + 4) % 4
        return (
          <div
            key={seat}
            className="absolute table-card-slot animate-card-appear"
            style={slotStyle(relativeSeat)}
          >
            <Card card={card} size="table" />
          </div>
        )
      })}
    </div>
  )
}
