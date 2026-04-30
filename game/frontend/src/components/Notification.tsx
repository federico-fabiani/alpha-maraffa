import { APP_LAYOUT } from "../layout/layout";
import { useEffect } from "react";
import type { Notification as NotificationType } from "../types";

interface NotificationProps {
  notification: NotificationType;
  onDismiss: () => void;
}

export default function Notification({
  notification,
  onDismiss,
}: NotificationProps) {
  const { text, subtitle, duration = 2500 } = notification;

  useEffect(() => {
    const timer = setTimeout(onDismiss, duration);
    return () => clearTimeout(timer);
  }, [notification, duration, onDismiss]);

  return (
    <div
      className="game-popup-overlay pointer-events-none"
      style={{
        zIndex: 30,
        display: "block",
      }}
    >
      <div
        className="game-popup-card game-popup-card-interactive animate-slide-up cursor-pointer pointer-events-auto"
        style={{
          position: "absolute",
          left: "50%",
          top: "calc(var(--bg-render-top) + (var(--bg-render-height) * (var(--layout-playing-area-top) + (var(--layout-playing-area-height) / 2))))",
          transform: "translate(-50%, -50%)",
          padding: `${APP_LAYOUT.notification.paddingY} ${APP_LAYOUT.notification.paddingX}`,
        }}
        onClick={onDismiss}
      >
        <p className="game-popup-title">{text}</p>
        {subtitle && (
          <p className="game-popup-subtitle text-xs mt-1">{subtitle}</p>
        )}
      </div>
    </div>
  );
}
