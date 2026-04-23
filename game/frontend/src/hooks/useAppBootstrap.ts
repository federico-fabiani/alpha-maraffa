import { useEffect } from 'react'
import { APP_LAYOUT } from '../layout/layout'
import { pingBackend } from '../services/api'
import useGameStore from '../state/gameStore'

export function useAppBootstrap() {
  const backendStatus = useGameStore(state => state.backendStatus)
  const restoreSession = useGameStore(state => state.restoreSession)
  const setBackendStatus = useGameStore(state => state.setBackendStatus)

  useEffect(() => {
    if (backendStatus === 'ready') {
      return
    }

    let cancelled = false
    let retryTimer: number | null = null

    const checkBackend = async () => {
      const isReady = await pingBackend()

      if (cancelled) {
        return
      }

      if (isReady) {
        setBackendStatus('ready')
        restoreSession()
        return
      }

      retryTimer = window.setTimeout(checkBackend, APP_LAYOUT.shell.startupRetryMs)
    }

    void checkBackend()

    return () => {
      cancelled = true
      if (retryTimer !== null) {
        window.clearTimeout(retryTimer)
      }
    }
  }, [backendStatus, restoreSession, setBackendStatus])

  return backendStatus
}