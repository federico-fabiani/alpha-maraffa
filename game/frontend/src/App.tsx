import { useEffect } from 'react'
import useGameStore from './store'
import HomeScreen from './screens/HomeScreen'
import LobbyScreen from './screens/LobbyScreen'
import GameScreen from './screens/GameScreen'
import GameOverScreen from './screens/GameOverScreen'
import ConnectionStatus from './components/ConnectionStatus'

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

  // Login on first mount to obtain a session UUID
  useEffect(() => {
    login()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Logout when the tab/window closes
  useEffect(() => {
    const handleUnload = () => {
      if (uuid) {
        navigator.sendBeacon('/api/logout', new Blob([JSON.stringify({ uuid })], { type: 'application/json' }))
      }
    }
    window.addEventListener('beforeunload', handleUnload)
    return () => window.removeEventListener('beforeunload', handleUnload)
  }, [uuid])

  const Screen = screens[screen]
  return (
    <div className="relative w-full h-full">
      <Screen />
      {screen !== 'home' && (
        <div className="absolute bottom-2 right-3 z-50">
          <ConnectionStatus />
        </div>
      )}
    </div>
  )
}
