import { useState } from 'react'
import useGameStore from '../store'

const SEAT_LABELS = ['Posto 1', 'Posto 2', 'Posto 3', 'Posto 4']

export default function LobbyScreen() {
  const roomId       = useGameStore(s => s.roomId)
  const mySeat       = useGameStore(s => s.mySeat)
  const isOwner      = useGameStore(s => s.isOwner)
  const lobbyPlayers = useGameStore(s => s.lobbyPlayers)
  const startGame    = useGameStore(s => s.startGame)
  const swapSeats    = useGameStore(s => s.swapSeats)
  const kickPlayer   = useGameStore(s => s.kickPlayer)
  const promotePlayer = useGameStore(s => s.promotePlayer)
  const ownerSeat    = useGameStore(s => s.ownerSeat)
  const reset        = useGameStore(s => s.reset)

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
          <p className="lobby-hint">in attesa di giocatori…</p>
        </div>

        {/* Room code */}
        <button onClick={handleCopy} title="Clicca per copiare" className="lobby-code-box">
          <p className="lobby-code-label">{copied ? 'copiato!' : 'codice stanza'}</p>
          <p className="lobby-code-value">{roomId}</p>
        </button>

        {/* Swap hint */}
        {isOwner && (
          <p className="lobby-hint" style={{ marginTop: '-0.75rem' }}>
            {swapPending !== null
              ? `Seleziona il secondo posto da scambiare con Posto ${swapPending + 1}…`
              : 'Clicca due posti per scambiarli.'}
          </p>
        )}

        {/* Seats grid */}
        <div className="grid grid-cols-2 gap-3 w-full">
          {[0, 1, 2, 3].map(seat => {
            const player    = playerBySeat[seat]
            const isMe      = seat === mySeat
            const team      = seat % 2 === 0 ? 1 : 2
            const isPending = swapPending === seat
            const isOccupied = !!player
            const isClickable = isOwner && (isOccupied || swapPending !== null)

            return (
              <div
                key={seat}
                onClick={() => handleSeatClick(seat)}
                className={[
                  'lobby-seat',
                  isMe      ? 'is-me'      : '',
                  isPending ? 'is-pending' : '',
                  isClickable ? 'cursor-pointer' : '',
                  swapPending !== null && !isPending && !isOccupied ? 'border-dashed' : '',
                ].filter(Boolean).join(' ')}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="lobby-seat-label">{SEAT_LABELS[seat]}</span>
                  <span
                    className="lobby-seat-team"
                    style={{ color: team === 1 ? '#b45309' : '#1d4ed8' }}
                  >
                    Team {team}
                  </span>
                </div>

                {player ? (
                  <div className="flex items-center gap-2">
                    <div
                      className="w-2 h-2 rounded-full flex-shrink-0"
                      style={{ background: player.is_bot ? 'rgba(100,40,14,0.35)' : '#5c1a0a' }}
                    />
                    <span className="lobby-player-name truncate flex-1">
                      {seat === ownerSeat && <span style={{ color: '#b45309', marginRight: '0.2rem' }}>♛</span>}
                      {player.name}
                      {isMe && <span style={{ color: 'rgba(100,40,14,0.55)', fontSize: '0.78rem', marginLeft: '0.3rem' }}>(tu)</span>}
                    </span>
                    {isOwner && !isMe && !player.is_bot && (
                      <>
                        <button
                          onClick={e => { e.stopPropagation(); promotePlayer(seat) }}
                          title="Promuovi a owner"
                          className="home-back-btn"
                          style={{ padding: '0 0.3rem', fontSize: '0.82rem' }}
                        >
                          ♛
                        </button>
                        <button
                          onClick={e => { e.stopPropagation(); kickPlayer(seat) }}
                          title="Espelli giocatore"
                          className="home-back-btn"
                          style={{ padding: '0 0.3rem', fontSize: '0.82rem' }}
                        >
                          ✕
                        </button>
                      </>
                    )}
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: 'rgba(100,40,14,0.25)' }} />
                    <span className="lobby-empty-slot">in attesa…</span>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Team legend */}
        <div className="lobby-legend">
          <span><span className="lobby-team1-dot">■</span> Team 1 (posti 1 e 3)</span>
          <span><span className="lobby-team2-dot">■</span> Team 2 (posti 2 e 4)</span>
        </div>

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
