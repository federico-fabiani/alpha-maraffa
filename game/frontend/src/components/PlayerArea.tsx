import { CardBack } from './Card'
import type { Player } from '../types'

interface PlayerAreaProps {
  player: Player | undefined
  isActive: boolean
  position: 'top' | 'left' | 'right'
}

const TEAM_BADGE: Record<number, string> = {
  1: 'border-amber-500/60 text-amber-300',
  2: 'border-blue-500/60  text-blue-300',
}

export default function PlayerArea({ player, isActive, position }: PlayerAreaProps) {
  const cardCount = player?.cards_count ?? 0

  // Orientation of the stacked card fan
  const isHorizontal = position === 'top'
  const stackClass   = isHorizontal ? 'flex-row' : 'flex-col'
  const offsetClass  = isHorizontal ? '-ml-5 first:ml-0' : '-mt-5 first:mt-0'

  const team     = player ? player.team : null
  const badgeCls = team ? TEAM_BADGE[team] : 'border-felt-700 text-felt-500'

  return (
    <div className={`flex flex-col items-center gap-2 ${position === 'top' ? '' : position === 'left' ? 'items-end' : 'items-start'}`}>
      {/* Name badge */}
      <div className={`
        px-3 py-1 rounded-full text-xs font-medium border bg-felt-900/60
        ${badgeCls}
        ${isActive ? 'animate-pulse-ring' : ''}
      `}>
        {player ? (
          <>
            {player.name}
            {isActive && <span className="ml-1 text-amber-400">●</span>}
            {!player.is_connected && <span className="ml-1 text-red-400">✕</span>}
          </>
        ) : (
          <span className="italic text-felt-600">Attesa...</span>
        )}
      </div>

      {/* Stacked face-down cards */}
      {cardCount > 0 && (
        <div className={`flex ${stackClass}`}>
          {Array.from({ length: Math.min(cardCount, 6) }).map((_, i) => (
            <CardBack
              key={i}
              size={position === 'top' ? 'sm' : 'sm'}
              className={`${offsetClass} ${i === 0 ? '' : offsetClass}`}
            />
          ))}
        </div>
      )}
    </div>
  )
}
