import { SUIT_META } from './Card'
import type { Suit } from '../types'

interface BriscolaModalProps {
  onSelect: (suit: Suit) => void
  selectorName?: string
}

const SUITS: Suit[] = ['bastoni', 'denara', 'spade', 'coppe']

export default function BriscolaModal({ onSelect, selectorName }: BriscolaModalProps) {
  return (
    <div className="absolute inset-0 bg-felt-950/25 flex items-center justify-center z-20 animate-fade-in">
      <div className="bg-felt-900 border border-amber-800/40 rounded-2xl p-6 w-80 shadow-2xl">
        <h3 className="font-cinzel text-center text-amber-400 text-lg font-bold mb-1">
          SCEGLI LA BRISCOLA
        </h3>
        {selectorName && (
          <p className="text-felt-500 text-xs text-center mb-5">{selectorName}</p>
        )}

        <div className="grid grid-cols-2 gap-3">
          {SUITS.map(suit => {
            const meta = SUIT_META[suit]
            return (
              <button
                key={suit}
                onClick={() => onSelect(suit)}
                className="flex items-center gap-3 bg-felt-800 hover:bg-felt-700
                           border border-felt-700 hover:border-current
                           rounded-xl p-3 transition-all group"
                style={{ '--tw-border-opacity': '0.6', color: meta.color } as React.CSSProperties}
              >
                <span className="text-2xl">{meta.symbol}</span>
                <span className="font-semibold text-sm group-hover:text-current transition-colors text-amber-100">
                  {meta.label}
                </span>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
