import type { Card as CardType } from '../types'

// ── Lookup tables ──────────────────────────────────────────────────────────────

export const SUIT_META: Record<string, { symbol: string; label: string; color: string }> = {
  bastoni: { symbol: '🪵', label: 'Bastoni', color: '#d97706' },
  denara:  { symbol: '🪙', label: 'Denara',  color: '#16a34a' },
  spade:   { symbol: '🗡️', label: 'Spade',   color: '#3b82f6' },
  coppe:   { symbol: '🍷', label: 'Coppe',   color: '#ef4444' },
}

export const RANK_FULL: Record<number, string> = {
  1: 'Asso', 2: 'Due', 3: 'Tre', 4: 'Quattro', 5: 'Cinque',
  6: 'Sei',  7: 'Sette', 8: 'Fante', 9: 'Cavallo', 10: 'Re',
}

const SUIT_ROW: Record<string, number> = {
  bastoni: 0,
  coppe: 1,
  denara: 2,
  spade: 3,
}

export interface CardSpriteCoords {
  col: number
  row: number
  xPct: number
  yPct: number
}

export function getCardSpriteCoords(card: Pick<CardType, 'suit' | 'rank'>): CardSpriteCoords {
  const col = Math.max(0, Math.min(9, card.rank - 1))
  const row = SUIT_ROW[card.suit] ?? 0
  const xPct = (col / 9) * 100
  const yPct = (row / 3) * 100
  return { col, row, xPct, yPct }
}

const SIZE: Record<string, { width: string; height: string }> = {
  sm:    { width: 'w-10',  height: 'h-14' },
  md:    { width: 'w-16',  height: 'h-24' },
  lg:    { width: 'w-20',  height: 'h-28' },
  table: { width: 'w-12',  height: 'h-[72px]' },
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
  const coords = getCardSpriteCoords(card)

  return (
    <div
      role={isPlayable ? 'button' : undefined}
      tabIndex={isPlayable ? 0 : undefined}
      onClick={isPlayable ? onClick : undefined}
      onKeyDown={isPlayable ? (e) => e.key === 'Enter' && onClick?.() : undefined}
      title={`${RANK_FULL[card.rank]} di ${meta.label}`}
      data-sprite-coords={`${coords.col},${coords.row}`}
      style={{
        color: meta.color,
        '--card-sprite-x': `${coords.xPct}%`,
        '--card-sprite-y': `${coords.yPct}%`,
        '--card-accent': meta.color,
      } as React.CSSProperties}
      className={`
        card-face card-sprite ${sz.width} ${sz.height}
        ${isPlayable ? 'playable' : 'opacity-80'}
        ${className}
      `}
    >
      <div className="card-art" />
    </div>
  )
}

// ── Card back ──────────────────────────────────────────────────────────────────

interface CardBackProps {
  size?: 'sm' | 'md' | 'lg' | 'table'
  className?: string
  style?: React.CSSProperties
}

export function CardBack({ size = 'md', className = '', style }: CardBackProps) {
  const sz = SIZE[size]
  return (
    <div className={`card-back ${sz.width} ${sz.height} ${className}`} style={style} />
  )
}
