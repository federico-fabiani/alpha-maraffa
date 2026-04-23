import { useEffect } from 'react'
import useGameStore from './state/gameStore'
import { APP_LAYOUT, APP_SHELL_LAYOUT_STYLES, layoutCssVariables } from './layout/layout'
import { useAppBootstrap } from './hooks/useAppBootstrap'
import HomeScreen from './screens/HomeScreen'
import LobbyScreen from './screens/LobbyScreen'
import GameScreen from './screens/GameScreen'
import GameOverScreen from './screens/GameOverScreen'
import ConnectionStatus from './components/ConnectionStatus'
import backgroundImg from './assets/background.png'

const screens = {
  home: HomeScreen,
  lobby: LobbyScreen,
  game: GameScreen,
  gameover: GameOverScreen,
} as const

export default function App() {
  const screen = useGameStore(state => state.screen)
  const displayedScreen = useGameStore(state => state.displayedScreen)
  const screenTransitionPhase = useGameStore(state => state.screenTransitionPhase)
  const beginScreenTransition = useGameStore(state => state.beginScreenTransition)
  const completeScreenTransition = useGameStore(state => state.completeScreenTransition)
  const backendStatus = useAppBootstrap()

  useEffect(() => {
    if (screen === displayedScreen) {
      return
    }

    beginScreenTransition()
    const timerId = window.setTimeout(() => {
      completeScreenTransition()
    }, APP_LAYOUT.shell.screenFadeDurationMs)

    return () => {
      window.clearTimeout(timerId)
    }
  }, [beginScreenTransition, completeScreenTransition, displayedScreen, screen])

  const showRusticBg = displayedScreen === 'home' || displayedScreen === 'lobby'
  const Screen = screens[displayedScreen]
  const backendReady = backendStatus === 'ready'
  const contentVisible = screenTransitionPhase === 'visible'

  return (
    <div style={{ ...APP_SHELL_LAYOUT_STYLES.root, ...layoutCssVariables }}>
      <div
        className={backendReady ? '' : 'pointer-events-none select-none'}
        style={{
          ...APP_SHELL_LAYOUT_STYLES.frame,
          filter: backendReady ? 'none' : `blur(${APP_LAYOUT.shell.inactiveBlurRadius})`,
        }}
      >
        {/* Persistent rustic background — visible for home and lobby */}
        <div
          style={{
            ...APP_SHELL_LAYOUT_STYLES.background,
            backgroundImage: `url(${backgroundImg})`,
            opacity: showRusticBg ? 1 : 0,
          }}
        />

        {/* CRT overlay */}
        <div className="crt-overlay" />

        {/* Screen content */}
        <div
          className="screen-content"
          style={{
            ...APP_SHELL_LAYOUT_STYLES.content,
            opacity: contentVisible ? 1 : 0,
          }}
        >
          <Screen />
        </div>

        {displayedScreen !== 'home' && (
          <div style={APP_SHELL_LAYOUT_STYLES.connection}>
            <ConnectionStatus />
          </div>
        )}
      </div>

      {!backendReady && (
        <div className="startup-loading-overlay" style={APP_SHELL_LAYOUT_STYLES.startupOverlay}>
          <div className="startup-loading-card" style={APP_SHELL_LAYOUT_STYLES.startupCard}>
            <div className="startup-spinner" aria-hidden="true" />
            <p className="startup-loading-title">Connessione al tavolo</p>
            <p className="startup-loading-subtitle">Attendo risposta del backend...</p>
          </div>
        </div>
      )}
    </div>
  )
}
