import { useEffect, useRef, useState } from 'react'
import useGameStore from '../store'
import titleImg from '../assets/title.png'
import arrowImg from '../assets/arrow.png'

type MenuOption = 'nuova_partita' | 'cerca_tavolo'

const MENU_OPTIONS: { key: MenuOption; label: string }[] = [
  { key: 'nuova_partita', label: 'Nuova partita' },
  { key: 'cerca_tavolo', label: 'Cerca un tavolo' },
]

export default function HomeScreen() {
  const playerName    = useGameStore(s => s.playerName)
  const error         = useGameStore(s => s.error)
  const setPlayerName = useGameStore(s => s.setPlayerName)
  const createRoom    = useGameStore(s => s.createRoom)
  const joinRoom      = useGameStore(s => s.joinRoom)

  const [selected, setSelected] = useState<MenuOption>('nuova_partita')
  const [showJoin, setShowJoin] = useState(false)
  const [roomCode, setRoomCode] = useState('')

  const nameRef = useRef<HTMLInputElement>(null)
  const roomRef = useRef<HTMLInputElement>(null)

  const canProceed = playerName.trim().length > 0

  const shakeNameInput = () => {
    const el = nameRef.current
    if (!el) return
    el.classList.remove('shake')
    void el.offsetWidth // force reflow
    el.classList.add('shake')
    el.focus()
  }

  const activate = (option: MenuOption) => {
    if (!canProceed) { shakeNameInput(); return }
    if (option === 'nuova_partita') {
      createRoom()
    } else {
      setShowJoin(true)
      setTimeout(() => roomRef.current?.focus(), 40)
    }
  }

  // Keyboard navigation
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (showJoin) return
      if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        e.preventDefault()
        setSelected(prev => prev === 'nuova_partita' ? 'cerca_tavolo' : 'nuova_partita')
      } else if (e.key === 'Enter' && document.activeElement !== nameRef.current) {
        activate(selected)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selected, showJoin, canProceed]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="relative flex items-center justify-center h-full">
      {/* DEMO badge */}
      <span
        className="absolute top-4 right-4 font-cinzel font-bold text-xs tracking-widest
                   px-3 py-1 rounded-full bg-red-800/80 text-amber-100 border border-red-700/50"
        style={{ animation: 'var(--animate-demo-blink)' }}
      >
        DEMO
      </span>

      <div className="flex flex-col items-center gap-7" style={{ marginTop: '-6vh' }}>
        {/* Title image */}
        <img
          src={titleImg}
          alt="MARAFONE"
          className="home-title animate-float"
        />

        {/* Name input */}
        <input
          ref={nameRef}
          type="text"
          placeholder="Il tuo nome…"
          value={playerName}
          onChange={e => setPlayerName(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !showJoin) activate(selected)
          }}
          className="home-name-input"
          maxLength={20}
          autoFocus
        />

        {/* Menu options */}
        {!showJoin ? (
          <div className="flex flex-col items-center gap-1">
            {MENU_OPTIONS.map(opt => (
              <div
                key={opt.key}
                className={`home-menu-item${!canProceed ? ' disabled' : ''}`}
                onClick={() => activate(opt.key)}
                onMouseEnter={() => setSelected(opt.key)}
              >
                <img
                  src={arrowImg}
                  alt=""
                  className="home-arrow home-arrow-left"
                  style={{ opacity: selected === opt.key ? 1 : 0 }}
                />
                <span>{opt.label}</span>
                <img
                  src={arrowImg}
                  alt=""
                  className="home-arrow home-arrow-right"
                  style={{ opacity: selected === opt.key ? 1 : 0 }}
                />
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-4 animate-fade-in">
            <input
              ref={roomRef}
              type="text"
              placeholder="Codice stanza (es. ROSSO-LUPO-7)"
              value={roomCode}
              onChange={e => setRoomCode(e.target.value.toUpperCase())}
              onKeyDown={e => e.key === 'Enter' && roomCode.trim() && joinRoom(roomCode.trim())}
              className="home-name-input"
              style={{ fontSize: '0.95rem' }}
            />
            <div
              className={`home-menu-item${!roomCode.trim() ? ' disabled' : ''}`}
              onClick={() => roomCode.trim() && joinRoom(roomCode.trim())}
            >
              <img src={arrowImg} alt="" className="home-arrow home-arrow-left" style={{ opacity: 1 }} />
              <span>Unisciti</span>
              <img src={arrowImg} alt="" className="home-arrow home-arrow-right" style={{ opacity: 1 }} />
            </div>
            <button
              className="home-back-btn"
              onClick={() => { setShowJoin(false); setRoomCode('') }}
            >
              ← Indietro
            </button>
          </div>
        )}

        {error && (
          <p
            className="animate-fade-in"
            style={{ fontFamily: "'IM Fell English', serif", color: '#8b1a06', fontSize: '0.95rem' }}
          >
            {error}
          </p>
        )}
      </div>
    </div>
  )
}
