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
  const screen = useGameStore(s => s.screen)
  const login  = useGameStore(s => s.login)
  const uuid   = useGameStore(s => s.uuid)

  const [displayedScreen, setDisplayedScreen] = useState<Screen>(screen)
  const [contentVisible, setContentVisible]   = useState(true)

  useEffect(() => {
    login()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const handleUnload = () => {
      if (uuid) {
        navigator.sendBeacon('/api/logout', new Blob([JSON.stringify({ uuid })], { type: 'application/json' }))
      }
    }
    window.addEventListener('beforeunload', handleUnload)
    return () => window.removeEventListener('beforeunload', handleUnload)
  }, [uuid])

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
    <div className="relative w-full h-full">
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
  )
}
