import { useEffect, useRef, useState } from 'react'
import useGameStore from '../store'
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

  const requestFullscreen = () => {
    const isStandalonePwa =
      window.matchMedia('(display-mode: standalone)').matches ||
      ('standalone' in navigator && (navigator as Navigator & { standalone?: boolean }).standalone === true)

    if (!isStandalonePwa) return

    const el = document.documentElement
    if (el.requestFullscreen) el.requestFullscreen()
  }

  const activate = (option: MenuOption) => {
    if (!canProceed) { shakeNameInput(); return }
    requestFullscreen()
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

      <div className="flex flex-col items-center gap-10" style={{ marginTop: '-14vh' }}>
        {/* Title – individual animated letters */}
        {/* One SVG filter per letter: unique warp seed + unique grain seed → unique campitura */}
        <svg aria-hidden="true" style={{ position: 'absolute', width: 0, height: 0, overflow: 'hidden' }}>
          <defs>
            {([
              { id: 'ts0', warpSeed: 3,  grainSeed: 19, warpScale: 2.2, grainThresh: -2.1 },
              { id: 'ts1', warpSeed: 17, grainSeed: 5,  warpScale: 3.1, grainThresh: -2.4 },
              { id: 'ts2', warpSeed: 31, grainSeed: 42, warpScale: 1.8, grainThresh: -2.0 },
              { id: 'ts3', warpSeed: 8,  grainSeed: 27, warpScale: 2.7, grainThresh: -2.3 },
              { id: 'ts4', warpSeed: 53, grainSeed: 11, warpScale: 2.0, grainThresh: -2.5 },
              { id: 'ts5', warpSeed: 22, grainSeed: 38, warpScale: 3.4, grainThresh: -2.2 },
              { id: 'ts6', warpSeed: 44, grainSeed: 7,  warpScale: 2.4, grainThresh: -1.9 },
              { id: 'ts7', warpSeed: 13, grainSeed: 61, warpScale: 2.9, grainThresh: -2.6 },
            ] as const).map(({ id, warpSeed, grainSeed, warpScale, grainThresh }) => (
              <filter key={id} id={id} x="-4%" y="-10%" width="108%" height="125%" colorInterpolationFilters="sRGB">
                <feTurbulence type="fractalNoise" baseFrequency="0.04 0.07" numOctaves="3" seed={warpSeed} result="warp" />
                <feDisplacementMap in="SourceGraphic" in2="warp" scale={warpScale} xChannelSelector="R" yChannelSelector="G" result="rough" />
                <feTurbulence type="fractalNoise" baseFrequency="0.75 0.55" numOctaves="4" seed={grainSeed} result="grain" />
                <feColorMatrix type="matrix"
                  values={`0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  4 0 0 0 ${grainThresh}`}
                  in="grain" result="grainMask" />
                <feComposite in="rough" in2="grainMask" operator="in" result="textured" />
                <feBlend in="rough" in2="textured" mode="multiply" />
              </filter>
            ))}
          </defs>
        </svg>
        <div className="title-word mb-4" aria-label="MARAFONE">
          {([
            { l: 'M', anim: 'letter-drift-a', dur: '5.3s', delay: '0s',    filterId: 'ts0', color: '#6b1c0e' },
            { l: 'A', anim: 'letter-drift-c', dur: '4.8s', delay: '-0.65s', filterId: 'ts1', color: '#7a2010' },
            { l: 'R', anim: 'letter-drift-b', dur: '5.6s', delay: '-1.4s',  filterId: 'ts2', color: '#5e1a0c' },
            { l: 'A', anim: 'letter-drift-d', dur: '5.0s', delay: '-0.4s',  filterId: 'ts3', color: '#72200f' },
            { l: 'F', anim: 'letter-drift-a', dur: '5.9s', delay: '-2.3s',  filterId: 'ts4', color: '#63190b' },
            { l: 'O', anim: 'letter-drift-c', dur: '4.7s', delay: '-1.0s',  filterId: 'ts5', color: '#791f0e' },
            { l: 'N', anim: 'letter-drift-d', dur: '5.5s', delay: '-1.8s',  filterId: 'ts6', color: '#5b180b' },
            { l: 'E', anim: 'letter-drift-b', dur: '5.2s', delay: '-0.8s',  filterId: 'ts7', color: '#6f1d0d' },
          ] as const).map(({ l, anim, dur, delay, filterId, color }, i) => (
            <span
              key={i}
              className="title-letter"
              style={{
                animation: `${anim} ${dur} ease-in-out infinite`,
                animationDelay: delay,
                color,
                filter: `url(#${filterId}) drop-shadow(3px 4px 0 rgba(20, 4, 2, 0.3))`,
              }}
            >
              {l}
            </span>
          ))}
        </div>

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
