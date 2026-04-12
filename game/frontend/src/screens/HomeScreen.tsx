import { useState } from 'react'
import useGameStore from '../store'

type Mode = 'menu' | 'create' | 'join'

export default function HomeScreen() {
  const playerName = useGameStore(s => s.playerName)
  const error      = useGameStore(s => s.error)
  const setPlayerName = useGameStore(s => s.setPlayerName)
  const createRoom    = useGameStore(s => s.createRoom)
  const joinRoom      = useGameStore(s => s.joinRoom)

  const [mode, setMode]         = useState<Mode>('menu')
  const [roomCode, setRoomCode] = useState('')

  const canProceed = playerName.trim().length > 0

  return (
    <div className="flex items-center justify-center h-full">
      <div className="flex flex-col items-center gap-8">

        {/* Logo */}
        <div className="text-center animate-float">
          <h1 className="font-cinzel text-6xl font-bold text-amber-400 glow-gold tracking-[0.15em]">
            MARAFONE
          </h1>
          <p className="text-felt-500 text-xs tracking-[0.3em] mt-2 uppercase">
            Il gioco di carte italiano
          </p>
        </div>

        {/* Suit icons */}
        <div className="flex gap-5 text-2xl opacity-50 select-none">
          <span>🪵</span><span>🪙</span><span>🗡️</span><span>🍷</span>
        </div>

        {/* Name input */}
        <input
          type="text"
          placeholder="Il tuo nome..."
          value={playerName}
          onChange={e => setPlayerName(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && canProceed && setMode('create')}
          className="w-64 bg-felt-900 border border-amber-900/40 text-amber-100
                     rounded-lg px-4 py-3 text-center placeholder:text-felt-500
                     focus:outline-none focus:border-amber-500/60 transition-colors"
          maxLength={20}
        />

        {/* Main menu */}
        {mode === 'menu' && (
          <div className="flex flex-col gap-3 w-64 animate-fade-in">
            <button
              onClick={() => setMode('create')}
              disabled={!canProceed}
              className="bg-amber-600 hover:bg-amber-500 disabled:opacity-40 disabled:cursor-not-allowed
                         text-white font-semibold py-3 rounded-lg transition-colors font-cinzel tracking-wider"
            >
              CREA PARTITA
            </button>
            <button
              onClick={() => setMode('join')}
              disabled={!canProceed}
              className="bg-felt-700 hover:bg-felt-600 disabled:opacity-40 disabled:cursor-not-allowed
                         border border-amber-900/30 text-amber-200 font-semibold
                         py-3 rounded-lg transition-colors font-cinzel tracking-wider"
            >
              UNISCITI
            </button>
          </div>
        )}

        {/* Create flow */}
        {mode === 'create' && (
          <div className="flex flex-col gap-3 w-64 animate-slide-up">
            <p className="text-amber-200/60 text-sm text-center leading-relaxed">
              Verrà creata una nuova stanza.<br />
              Condividi il codice con gli amici.
            </p>
            <button
              onClick={() => createRoom()}
              className="bg-amber-600 hover:bg-amber-500 text-white font-semibold
                         py-3 rounded-lg transition-colors font-cinzel tracking-wider"
            >
              CREA
            </button>
            <button onClick={() => setMode('menu')} className="text-felt-500 hover:text-felt-400 text-sm transition-colors">
              ← Indietro
            </button>
          </div>
        )}

        {/* Join flow */}
        {mode === 'join' && (
          <div className="flex flex-col gap-3 w-64 animate-slide-up">
            <input
              type="text"
              placeholder="Codice stanza (es. ROSSO-LUPO-7)"
              value={roomCode}
              onChange={e => setRoomCode(e.target.value.toUpperCase())}
              onKeyDown={e => e.key === 'Enter' && roomCode.trim() && joinRoom(roomCode.trim())}
              className="bg-felt-900 border border-amber-900/40 text-amber-100
                         rounded-lg px-4 py-3 text-center text-sm placeholder:text-felt-500
                         focus:outline-none focus:border-amber-500/60 transition-colors"
            />
            <button
              onClick={() => joinRoom(roomCode.trim())}
              disabled={!roomCode.trim()}
              className="bg-amber-600 hover:bg-amber-500 disabled:opacity-40 disabled:cursor-not-allowed
                         text-white font-semibold py-3 rounded-lg transition-colors font-cinzel tracking-wider"
            >
              UNISCITI
            </button>
            <button onClick={() => setMode('menu')} className="text-felt-500 hover:text-felt-400 text-sm transition-colors">
              ← Indietro
            </button>
          </div>
        )}

        {/* Connection error */}
        {error && (
          <p className="text-red-400 text-sm animate-fade-in">{error}</p>
        )}
      </div>
    </div>
  )
}
