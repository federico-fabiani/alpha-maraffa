import { useState } from 'react'
import useGameStore from '../store'

const SEAT_LABELS = ['Posto 1', 'Posto 2', 'Posto 3', 'Posto 4']
const TEAM_COLORS: Record<number, string> = {
  1: 'border-amber-500/60 text-amber-300',
  2: 'border-blue-500/60 text-blue-300',
}

export default function LobbyScreen() {
  const roomId       = useGameStore(s => s.roomId)
  const mySeat       = useGameStore(s => s.mySeat)
  const isOwner      = useGameStore(s => s.isOwner)
  const lobbyPlayers = useGameStore(s => s.lobbyPlayers)
  const startGame    = useGameStore(s => s.startGame)
  const swapSeats    = useGameStore(s => s.swapSeats)
  const reset        = useGameStore(s => s.reset)

  const [swapPending, setSwapPending] = useState<number | null>(null)

  const playerBySeat = Object.fromEntries(lobbyPlayers.map(p => [p.seat, p]))

  const handleSeatClick = (seat: number) => {
    if (!isOwner) return
    if (swapPending === null) {
      if (!playerBySeat[seat]) return   // first click must be on an occupied seat
      setSwapPending(seat)
    } else if (swapPending === seat) {
      setSwapPending(null)              // deselect
    } else {
      swapSeats(swapPending, seat)      // empty or occupied: both valid as destination
      setSwapPending(null)
    }
  }

  return (
    <div className="flex items-center justify-center h-full">
      <div className="flex flex-col items-center gap-8 w-96">

        {/* Header */}
        <div className="text-center">
          <h2 className="font-cinzel text-3xl font-bold text-amber-400 glow-gold">SALA D'ATTESA</h2>
          <p className="text-felt-500 text-xs tracking-widest mt-1">IN ATTESA DI GIOCATORI</p>
        </div>

        {/* Room code */}
        <div className="bg-felt-900 border border-amber-800/40 rounded-xl px-8 py-4 text-center">
          <p className="text-felt-500 text-xs tracking-widest mb-1">CODICE STANZA</p>
          <p className="font-cinzel text-xl text-amber-300 tracking-wider">{roomId}</p>
        </div>

        {/* Swap hint */}
        {isOwner && (
          <p className="text-felt-500 text-xs text-center -mt-4">
            {swapPending !== null
              ? `Seleziona il secondo posto da scambiare con Posto ${swapPending + 1}…`
              : 'Clicca due posti per scambiarli.'}
          </p>
        )}

        {/* Seats grid */}
        <div className="grid grid-cols-2 gap-3 w-full">
          {[0, 1, 2, 3].map(seat => {
            const player   = playerBySeat[seat]
            const isMe     = seat === mySeat
            const team     = seat % 2 === 0 ? 1 : 2
            const teamCls  = TEAM_COLORS[team]
            const isPending = swapPending === seat
            const isOccupied = !!player
            // Clickable on first-click only if occupied; always clickable as destination
            const isClickable = isOwner && (isOccupied || swapPending !== null)

            return (
              <div
                key={seat}
                onClick={() => handleSeatClick(seat)}
                className={`rounded-xl border bg-felt-900/60 p-4 transition-all
                  ${isMe ? 'border-amber-400/80 ring-1 ring-amber-400/30' : 'border-felt-700'}
                  ${isPending ? 'ring-2 ring-amber-400 border-amber-400' : ''}
                  ${isClickable && !isPending ? 'cursor-pointer hover:border-amber-600/60' : ''}
                  ${isPending ? 'cursor-pointer' : ''}
                  ${swapPending !== null && !isPending && !isOccupied ? 'border-dashed border-amber-800/50' : ''}
                `}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-felt-500 text-xs">{SEAT_LABELS[seat]}</span>
                  <div className="flex items-center gap-1.5">
                    {isOwner && player && (
                      <span className="text-felt-600 text-xs">
                        {isPending ? '✕' : '⇄'}
                      </span>
                    )}
                    <span className={`text-xs font-semibold ${teamCls}`}>Team {team}</span>
                  </div>
                </div>

                {player ? (
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${player.is_bot ? 'bg-felt-500' : 'bg-green-400'}`} />
                    <span className="text-amber-100 text-sm font-medium truncate">
                      {player.name}
                      {isMe && <span className="text-amber-500 text-xs ml-1">(tu)</span>}
                    </span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-felt-700 animate-pulse" />
                    <span className="text-felt-500 text-sm italic">in attesa...</span>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Team legend */}
        <div className="flex gap-6 text-xs text-felt-500">
          <span><span className="text-amber-400">■</span> Team 1 (posti 1 e 3)</span>
          <span><span className="text-blue-400">■</span> Team 2 (posti 2 e 4)</span>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-3 w-full">
          <button
            onClick={startGame}
            className="bg-amber-600 hover:bg-amber-500 text-white font-semibold
                       py-3 rounded-lg transition-colors font-cinzel tracking-wider"
          >
            INIZIA PARTITA
          </button>
          <p className="text-felt-500 text-xs text-center">
            I posti liberi verranno riempiti da bot.
          </p>
          <button onClick={reset} className="text-felt-500 hover:text-felt-400 text-sm transition-colors">
            ← Abbandona
          </button>
        </div>
      </div>
    </div>
  )
}
