import { APP_LAYOUT } from "../layout/layout";
import { useEffect } from "react";
import type {
  Notification as NotificationType,
  RoundTeamSummary,
} from "../types";

interface NotificationProps {
  notification: NotificationType;
  onDismiss: () => void;
}

function RoundSummaryRow({ team }: { team: RoundTeamSummary }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "baseline",
        gap: "0.5rem",
        justifyContent: "space-between",
      }}
    >
      <span
        className="game-popup-subtitle"
        style={{ fontSize: "0.7rem", opacity: 0.85, whiteSpace: "nowrap" }}
      >
        {team.names[0]} &amp; {team.names[1]}
      </span>
      <span
        style={{
          display: "flex",
          gap: "0.4rem",
          alignItems: "baseline",
          flexShrink: 0,
        }}
      >
        <span
          className="game-popup-title"
          style={{
            fontSize: "0.85rem",
            minWidth: "1.4rem",
            textAlign: "right",
          }}
        >
          {team.roundScore}
        </span>
        <span
          className="game-popup-subtitle"
          style={{
            fontSize: "0.65rem",
            opacity: 0.6,
            minWidth: "2rem",
            textAlign: "right",
          }}
        >
          ({team.totalScore})
        </span>
      </span>
    </div>
  );
}

export default function Notification({
  notification,
  onDismiss,
}: NotificationProps) {
  const { text, subtitle, duration = 2500, roundSummary } = notification;

  useEffect(() => {
    const timer = setTimeout(onDismiss, duration);
    return () => clearTimeout(timer);
  }, [notification, duration, onDismiss]);

  return (
    <div
      className="game-popup-overlay pointer-events-none"
      style={{ zIndex: 30, display: "block" }}
    >
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: "calc(var(--bg-render-top) + (var(--bg-render-height) * (var(--layout-playing-area-top) + (var(--layout-playing-area-height) / 2))))",
          transform: "translate(-50%, -50%)",
        }}
      >
        <div
          className="game-popup-card game-popup-card-interactive animate-slide-up cursor-pointer pointer-events-auto"
          style={{
            padding: `${APP_LAYOUT.notification.paddingY} ${APP_LAYOUT.notification.paddingX}`,
            minWidth: "11rem",
            maxWidth: "16rem",
          }}
          onClick={onDismiss}
        >
          <p className="game-popup-title">{text}</p>
          {roundSummary ? (
            <div
              style={{
                marginTop: "0.35rem",
                display: "flex",
                flexDirection: "column",
                gap: "0.2rem",
              }}
            >
              <RoundSummaryRow team={roundSummary.team1} />
              <RoundSummaryRow team={roundSummary.team2} />
            </div>
          ) : subtitle ? (
            <p className="game-popup-subtitle text-xs mt-1">{subtitle}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
