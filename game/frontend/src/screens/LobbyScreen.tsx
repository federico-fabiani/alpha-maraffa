import { useState } from 'react'
import useGameStore from '../store'

const SEAT_AREA = ['bottom', 'right', 'top', 'left'] as const
const TEAM_COLOR = ['#c8922a', '#8b3a1a', '#c8922a', '#8b3a1a']

export default function LobbyScreen() {
  const roomId        = useGameStore(s => s.roomId)
  const mySeat        = useGameStore(s => s.mySeat)
  const isOwner       = useGameStore(s => s.isOwner)
  const lobbyPlayers  = useGameStore(s => s.lobbyPlayers)
  const startGame     = useGameStore(s => s.startGame)
  const swapSeats     = useGameStore(s => s.swapSeats)
  const kickPlayer    = useGameStore(s => s.kickPlayer)
  const promotePlayer = useGameStore(s => s.promotePlayer)
  const ownerSeat     = useGameStore(s => s.ownerSeat)
  const reset         = useGameStore(s => s.reset)

  const [swapPending, setSwapPending] = useState<number | null>(null)
  const [copied, setCopied] = useState(false)

  const playerBySeat = Object.fromEntries(lobbyPlayers.map(p => [p.seat, p]))

  const handleCopy = () => {
    navigator.clipboard.writeText(roomId).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const handleSeatClick = (seat: number) => {
    if (!isOwner) return
    if (swapPending === null) {
      if (!playerBySeat[seat]) return
      setSwapPending(seat)
    } else if (swapPending === seat) {
      setSwapPending(null)
    } else {
      swapSeats(swapPending, seat)
      setSwapPending(null)
    }
  }

  return (
    <div className="flex items-center justify-center h-full">
      <div className="lobby-wrap">

        {/* Header */}
        <div className="text-center">
          <h2 className="lobby-heading">Sala d'attesa</h2>
        </div>

        {/* Room code */}
        <button onClick={handleCopy} title="Clicca per copiare" className="lobby-code-box">
          <p className="lobby-code-label">{copied ? 'copiato!' : 'codice stanza'}</p>
          <p className="lobby-code-value">{roomId}</p>
        </button>

        {/* Physical table layout */}
        <div className="lobby-table">
          {[0, 1, 2, 3].map(seat => {
            const player      = playerBySeat[seat]
            const isMe        = seat === mySeat
            const teamColor   = TEAM_COLOR[seat]
            const isPending   = swapPending === seat
            const isClickable = isOwner && (!!player || swapPending !== null)
            const area        = SEAT_AREA[seat]

            return (
              <div
                key={seat}
                onClick={() => handleSeatClick(seat)}
                className={[
                  'lobby-seat-card',
                  `lobby-seat-${area}`,
                  isMe       ? 'is-me'      : '',
                  isPending  ? 'is-pending' : '',
                  isClickable ? 'cursor-pointer' : '',
                ].filter(Boolean).join(' ')}
                style={{ '--team-color': teamColor } as React.CSSProperties}
              >
                <div className={`lobby-avatar${player ? '' : ' empty'}`}>
                  {player
                    ? <span>{player.name.charAt(0).toUpperCase()}</span>
                    : <span>–</span>
                  }
                </div>

                {player ? (
                  <div className="lobby-seat-info">
                    <p className="lobby-seat-name">
                      {ownerSeat === seat && <span className="lobby-owner-crown">♛ </span>}
                      {player.name}
                      {isMe && <span className="lobby-me-tag"> (tu)</span>}
                    </p>
                    {isOwner && !isMe && !player.is_bot && (
                      <div className="lobby-seat-actions">
                        <button
                          onClick={e => { e.stopPropagation(); promotePlayer(seat) }}
                          title="Promuovi a owner"
                          className="lobby-action-btn"
                        >♛</button>
                        <button
                          onClick={e => { e.stopPropagation(); kickPlayer(seat) }}
                          title="Espelli"
                          className="lobby-action-btn"
                        >✕</button>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="lobby-seat-empty">Attesa…</p>
                )}
              </div>
            )
          })}
        </div>

        {/* Swap hint */}
        {isOwner && (
          <p className="lobby-hint" style={{ marginTop: '-0.5rem' }}>
            {swapPending !== null
              ? `Seleziona il secondo posto da scambiare…`
              : 'Clicca due posti per scambiarli.'}
          </p>
        )}

        {/* Actions */}
        <div className="flex flex-col gap-3 w-full">
          <button onClick={startGame} disabled={!isOwner} className="lobby-btn primary">
            INIZIA PARTITA
          </button>
          <p className="lobby-hint">
            {isOwner
              ? 'I posti liberi verranno riempiti da bot.'
              : 'Solo il proprietario della stanza può avviare la partita.'}
          </p>
          <button onClick={reset} className="home-back-btn" style={{ alignSelf: 'center' }}>
            ← Abbandona
          </button>
        </div>

      </div>
    </div>
  )
}
