import { useEffect, useState } from 'react'
import useGameStore from './store'
import HomeScreen from './screens/HomeScreen'
import LobbyScreen from './screens/LobbyScreen'
import GameScreen from './screens/GameScreen'
import GameOverScreen from './screens/GameOverScreen'
import ConnectionStatus from './components/ConnectionStatus'
import type { Screen } from './types'
import backgroundImg from './assets/background.png'

const screens = {
  home: HomeScreen,
  lobby: LobbyScreen,
  game: GameScreen,
  gameover: GameOverScreen,
} as const

export default function App() {
  const screen          = useGameStore(s => s.screen)
  const restoreSession  = useGameStore(s => s.restoreSession)

  const [displayedScreen, setDisplayedScreen] = useState<Screen>(screen)
  const [contentVisible, setContentVisible]   = useState(true)
  const [backendReady, setBackendReady]       = useState(false)

  useEffect(() => {
    let cancelled = false
    let retryTimer: number | null = null

    const pingBackend = async () => {
      try {
        const res = await fetch('/api/ping', { cache: 'no-store' })
        if (res.ok) {
          if (cancelled) return
          setBackendReady(true)
          restoreSession()
          return
        }
      } catch {
        // Backend still starting or temporarily unreachable
      }

      if (cancelled) return
      retryTimer = window.setTimeout(pingBackend, 1200)
    }

    pingBackend()

    return () => {
      cancelled = true
      if (retryTimer !== null) window.clearTimeout(retryTimer)
    }
  }, [restoreSession])

  // Cross-fade between screens: fade out → swap → fade in
  useEffect(() => {
    if (screen === displayedScreen) return
    setContentVisible(false)
    const timer = setTimeout(() => {
      setDisplayedScreen(screen)
      setContentVisible(true)
    }, 380)
    return () => clearTimeout(timer)
  }, [screen]) // eslint-disable-line react-hooks/exhaustive-deps

  const showRusticBg = displayedScreen === 'home' || displayedScreen === 'lobby'
  const Screen = screens[displayedScreen]

  return (
    <div className="relative w-full h-full overflow-hidden">
      <div className={`relative w-full h-full transition-[filter] duration-500 ${backendReady ? 'blur-0' : 'blur-[7px] pointer-events-none select-none'}`}>
        {/* Persistent rustic background — visible for home and lobby */}
        <div
          className="absolute inset-0 z-0"
          style={{
            backgroundImage: `url(${backgroundImg})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            opacity: showRusticBg ? 1 : 0,
            transition: 'opacity 0.55s ease',
          }}
        />

        {/* CRT overlay */}
        <div className="crt-overlay" />

        {/* Screen content */}
        <div
          className="screen-content relative w-full h-full z-10"
          style={{ opacity: contentVisible ? 1 : 0 }}
        >
          <Screen />
        </div>

        {displayedScreen !== 'home' && (
          <div className="absolute bottom-2 right-3 z-50">
            <ConnectionStatus />
          </div>
        )}
      </div>

      {!backendReady && (
        <div className="startup-loading-overlay absolute inset-0 z-[70] flex items-center justify-center">
          <div className="startup-loading-card flex flex-col items-center gap-4 px-7 py-6">
            <div className="startup-spinner" aria-hidden="true" />
            <p className="startup-loading-title">Connessione al tavolo</p>
            <p className="startup-loading-subtitle">Attendo risposta del backend...</p>
          </div>
        </div>
      )}
    </div>
  )
}
