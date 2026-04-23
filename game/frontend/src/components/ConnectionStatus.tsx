import { APP_LAYOUT } from "../layout/layout";
import useGameStore from "../state/gameStore";
import type { PingStatus } from "../types";

const STATUS_CONFIG: Record<PingStatus, { dot: string; label: string }> = {
  good: { dot: "bg-green-400", label: "Ottimo" },
  ok: { dot: "bg-yellow-400", label: "OK" },
  bad: { dot: "bg-red-400", label: "Lento" },
  offline: { dot: "bg-gray-500", label: "Offline" },
};

export default function ConnectionStatus() {
  const connected = useGameStore((s) => s.connected);
  const pingMs = useGameStore((s) => s.pingMs);
  const pingStatus = useGameStore((s) => s.pingStatus);

  const status = connected ? pingStatus : "offline";
  const config = STATUS_CONFIG[status];
  const isPulsing = connected && status !== "offline";

  return (
    <div
      className="text-xs text-felt-400 select-none"
      style={{
        display: "flex",
        alignItems: "center",
        gap: APP_LAYOUT.connectionStatus.gap,
      }}
    >
      <div
        className={`rounded-full ${config.dot} ${isPulsing ? "animate-pulse" : ""}`}
        style={{
          width: APP_LAYOUT.connectionStatus.dotSize,
          height: APP_LAYOUT.connectionStatus.dotSize,
        }}
      />
      <span>
        {connected && pingMs !== null ? `${pingMs} ms` : config.label}
      </span>
    </div>
  );
}
