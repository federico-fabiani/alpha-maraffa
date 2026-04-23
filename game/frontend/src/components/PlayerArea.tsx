import { APP_LAYOUT } from '../layout/layout'
import { CardBack } from './Card'
import type { Declaration, Player } from '../types'

interface PlayerAreaProps {
  player: Player | undefined
  isActive: boolean
  position: 'top' | 'left' | 'right'
  declaration?: Declaration
  showCards?: boolean
}

type HandCardBackStyle = React.CSSProperties & Record<'--hand-index', string>

const TEAM_BADGE: Record<number, string> = {
  1: 'border-amber-500/60 text-amber-300',
  2: 'border-blue-500/60  text-blue-300',
}

const DECLARATION_LABEL: Record<string, string> = {
  busso: 'BUSSO',
  striscio: 'STRISCIO',
  volo: 'VOLO',
}

export default function PlayerArea({ player, isActive, position, declaration, showCards = true }: PlayerAreaProps) {
  const cardCount = player?.cards_count ?? 0

  // Orientation of the stacked card fan
  const isHorizontal = position === 'top'

  const team     = player ? player.team : null
  const badgeCls = team ? TEAM_BADGE[team] : 'border-felt-700 text-felt-500'
  const stackStyles = isHorizontal
    ? { display: 'flex', flexDirection: 'row' as const }
    : { display: 'flex', flexDirection: 'column' as const }
  const offsetStyle = isHorizontal
    ? { marginLeft: 'var(--layout-opponent-stack-overlap)' }
    : { marginTop: 'var(--layout-opponent-stack-overlap)' }
  const wrapperStyle = {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: position === 'top' ? 'center' : position === 'left' ? 'flex-end' : 'flex-start',
    gap: APP_LAYOUT.playerArea.gap,
  }
  const createCardBackStyle = (index: number): HandCardBackStyle => ({
    ...(index === 0 ? {} : offsetStyle),
    '--hand-index': `${index}`,
  })

  return (
    <div style={wrapperStyle}>
      {/* Declaration badge */}
      {declaration && (
        <div className="px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-widest uppercase bg-amber-900/60 border border-amber-500/50 text-amber-300">
          {DECLARATION_LABEL[declaration] ?? declaration}
        </div>
      )}

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
            {!player.is_connected && (
                player.is_bot
                  ? <span className="ml-1">🤖</span>
                  : <span className="ml-1 text-red-400">✕</span>
              )}
          </>
        ) : (
          <span className="italic text-felt-600">Attesa...</span>
        )}
      </div>

      {/* Stacked face-down cards */}
      {showCards && cardCount > 0 && (
        <div style={stackStyles}>
          {Array.from({ length: Math.min(cardCount, 6) }).map((_, i) => (
            <CardBack
              key={i}
              size={position === 'top' ? 'sm' : 'sm'}
              className="opponent-card-back"
              style={createCardBackStyle(i)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
