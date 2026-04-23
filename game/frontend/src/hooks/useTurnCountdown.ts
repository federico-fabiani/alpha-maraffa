import { useEffect, useState } from 'react'

const COUNTDOWN_TICK_MS = 250

export function useTurnCountdown(turnDeadline: number | null): number | null {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!turnDeadline) {
      setNow(Date.now())
      return
    }

    const updateNow = () => {
      setNow(Date.now())
    }

    updateNow()
    const intervalId = window.setInterval(updateNow, COUNTDOWN_TICK_MS)

    return () => {
      window.clearInterval(intervalId)
    }
  }, [turnDeadline])

  if (!turnDeadline) {
    return null
  }

  return Math.max(0, Math.round((turnDeadline * 1000 - now) / 1000))
}