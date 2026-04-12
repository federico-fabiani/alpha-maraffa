import type { Card as CardType } from '../types'

// ── Lookup tables ──────────────────────────────────────────────────────────────

export const SUIT_META: Record<string, { symbol: string; label: string; color: string }> = {
  bastoni: { symbol: '🪵', label: 'Bastoni', color: '#d97706' },
  denara:  { symbol: '🪙', label: 'Denara',  color: '#16a34a' },
  spade:   { symbol: '🗡️', label: 'Spade',   color: '#3b82f6' },
  coppe:   { symbol: '🍷', label: 'Coppe',   color: '#ef4444' },
}

export const RANK_SHORT: Record<number, string> = {
  1: 'A', 2: '2', 3: '3', 4: '4', 5: '5',
  6: '6', 7: '7', 8: 'F', 9: 'C', 10: 'R',
}

export const RANK_FULL: Record<number, string> = {
  1: 'Asso', 2: 'Due', 3: 'Tre', 4: 'Quattro', 5: 'Cinque',
  6: 'Sei',  7: 'Sette', 8: 'Fante', 9: 'Cavallo', 10: 'Re',
}

const SIZE: Record<string, { width: string; height: string; text: string; symbol: string }> = {
  sm:    { width: 'w-10',  height: 'h-14',  text: 'text-xs', symbol: 'text-base' },
  md:    { width: 'w-16',  height: 'h-24',  text: 'text-sm', symbol: 'text-xl'  },
  lg:    { width: 'w-20',  height: 'h-28',  text: 'text-base', symbol: 'text-2xl' },
  table: { width: 'w-12',  height: 'h-[72px]', text: 'text-xs', symbol: 'text-sm' },
}

// ── Card face ──────────────────────────────────────────────────────────────────

interface CardProps {
  card: CardType
  size?: 'sm' | 'md' | 'lg' | 'table'
  onClick?: () => void
  className?: string
}

export function Card({ card, size = 'md', onClick, className = '' }: CardProps) {
  const meta = SUIT_META[card.suit]
  const sz   = SIZE[size]
  const isPlayable = card.playable === true

  return (
    <div
      role={isPlayable ? 'button' : undefined}
      tabIndex={isPlayable ? 0 : undefined}
      onClick={isPlayable ? onClick : undefined}
      onKeyDown={isPlayable ? (e) => e.key === 'Enter' && onClick?.() : undefined}
      title={`${RANK_FULL[card.rank]} di ${meta.label}`}
      style={{ color: meta.color }}
      className={`
        card-face ${sz.width} ${sz.height}
        flex flex-col items-center justify-between p-1
        ${isPlayable ? 'playable' : 'opacity-80'}
        ${className}
      `}
    >
      <span className={`self-start font-bold leading-none ${sz.text}`}>
        {RANK_SHORT[card.rank]}
      </span>
      <span className={`leading-none ${sz.symbol}`}>{meta.symbol}</span>
      <span className={`self-end font-bold leading-none rotate-180 ${sz.text}`}>
        {RANK_SHORT[card.rank]}
      </span>
    </div>
  )
}

// ── Card back ──────────────────────────────────────────────────────────────────

interface CardBackProps {
  size?: 'sm' | 'md' | 'lg' | 'table'
  className?: string
}

export function CardBack({ size = 'md', className = '' }: CardBackProps) {
  const sz = SIZE[size]
  return (
    <div className={`card-back ${sz.width} ${sz.height} ${className}`} />
  )
}
