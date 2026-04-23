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
      className="bg-felt-900/95 border border-amber-800/50 rounded-xl
                 text-center shadow-xl animate-slide-up
                 backdrop-blur-sm cursor-pointer"
      style={{
        position: "absolute",
        bottom: APP_LAYOUT.notification.bottom,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 30,
        padding: `${APP_LAYOUT.notification.paddingY} ${APP_LAYOUT.notification.paddingX}`,
      }}
      onClick={onDismiss}
    >
      <p className="text-amber-200 font-semibold">{text}</p>
      {subtitle && <p className="text-felt-500 text-xs mt-0.5">{subtitle}</p>}
    </div>
  );
}
