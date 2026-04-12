import { useEffect } from 'react'
import type { Notification as NotificationType } from '../types'

interface NotificationProps {
  notification: NotificationType
  onDismiss: () => void
}

export default function Notification({ notification, onDismiss }: NotificationProps) {
  const { text, subtitle, duration = 2500 } = notification

  useEffect(() => {
    const timer = setTimeout(onDismiss, duration)
    return () => clearTimeout(timer)
  }, [notification, duration, onDismiss])

  return (
    <div
      className="absolute bottom-44 left-1/2 -translate-x-1/2 z-30
                 bg-felt-900/95 border border-amber-800/50 rounded-xl
                 px-6 py-3 text-center shadow-xl animate-slide-up
                 backdrop-blur-sm cursor-pointer"
      onClick={onDismiss}
    >
      <p className="text-amber-200 font-semibold">{text}</p>
      {subtitle && (
        <p className="text-felt-500 text-xs mt-0.5">{subtitle}</p>
      )}
    </div>
  )
}
