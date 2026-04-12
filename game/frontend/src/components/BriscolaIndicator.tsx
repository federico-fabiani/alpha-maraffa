import { SUIT_META } from './Card'
import type { Suit } from '../types'

interface BriscolaIndicatorProps {
  suit: Suit
}

export default function BriscolaIndicator({ suit }: BriscolaIndicatorProps) {
  const meta = SUIT_META[suit]
  return (
    <div
      className="bg-felt-900/80 border border-felt-700/60 rounded-xl px-4 py-2
                 backdrop-blur-sm flex items-center gap-2"
      style={{ borderColor: `${meta.color}40` }}
    >
      <span className="text-xl leading-none">{meta.symbol}</span>
      <div>
        <p className="text-xs text-felt-500 leading-none">Briscola</p>
        <p className="text-sm font-semibold leading-tight" style={{ color: meta.color }}>
          {meta.label}
        </p>
      </div>
    </div>
  )
}
