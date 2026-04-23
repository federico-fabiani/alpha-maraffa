import { useState } from 'react'
import useGameStore from '../state/gameStore'

const SEAT_AREA = ['bottom', 'right', 'top', 'left'] as const
const TEAM_COLOR = ['#c8922a', '#8b3a1a', '#c8922a', '#8b3a1a']

export default function LobbyScreen() {
  const roomId = useGameStore(state => state.roomId)
  const mySeat = useGameStore(state => state.mySeat)
  const isOwner = useGameStore(state => state.isOwner)
  const lobbyPlayers = useGameStore(state => state.lobbyPlayers)
  const startGame = useGameStore(state => state.startGame)
  const swapSeats = useGameStore(state => state.swapSeats)
  const kickPlayer = useGameStore(state => state.kickPlayer)
  const promotePlayer = useGameStore(state => state.promotePlayer)
  const ownerSeat = useGameStore(state => state.ownerSeat)
  const reset = useGameStore(state => state.reset)

  const [swapPendingSeat, setSwapPendingSeat] = useState<number | null>(null)
  const [copied, setCopied] = useState(false)

  const playerBySeat = Object.fromEntries(lobbyPlayers.map(player => [player.seat, player]))

  const handleCopyRoomId = () => {
    void navigator.clipboard.writeText(roomId).then(() => {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    })
  }

  const handleSeatClick = (seat: number) => {
    if (!isOwner) {
      return
    }

    if (swapPendingSeat === null) {
      if (!playerBySeat[seat]) {
        return
      }

      setSwapPendingSeat(seat)
      return
    }

    if (swapPendingSeat === seat) {
      setSwapPendingSeat(null)
      return
    }

    swapSeats(swapPendingSeat, seat)
    setSwapPendingSeat(null)
  }

  const rootStyle = { display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' } as const
  const actionsStyle = { display: 'flex', flexDirection: 'column' as const, gap: '0.75rem', width: '100%' }

  return (
    <div style={rootStyle}>
      <div className="lobby-wrap">

        {/* Header */}
        <div className="text-center">
          <h2 className="lobby-heading">Sala d'attesa</h2>
        </div>

        {/* Room code */}
        <button onClick={handleCopyRoomId} title="Clicca per copiare" className="lobby-code-box">
          <p className="lobby-code-label">{copied ? 'copiato!' : 'codice stanza'}</p>
          <p className="lobby-code-value">{roomId}</p>
        </button>

        {/* Physical table layout */}
        <div className="lobby-table">
          {[0, 1, 2, 3].map(seat => {
            const player      = playerBySeat[seat]
            const isMe        = seat === mySeat
            const teamColor   = TEAM_COLOR[seat]
            const isPending   = swapPendingSeat === seat
            const isClickable = isOwner && (!!player || swapPendingSeat !== null)
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
            {swapPendingSeat !== null
              ? `Seleziona il secondo posto da scambiare…`
              : 'Clicca due posti per scambiarli.'}
          </p>
        )}

        {/* Actions */}
        <div style={actionsStyle}>
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
