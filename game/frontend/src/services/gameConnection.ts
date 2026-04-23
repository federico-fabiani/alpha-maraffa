import type { Screen } from "../types";
import type { GameMessage, GameStoreState } from "../state/storeTypes";

const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_BASE_DELAY_MS = 2000;
const PING_INTERVAL_MS = 5000;

type ConnectionStatePatch = Partial<
  Pick<GameStoreState, "connected" | "pingStatus" | "pingMs" | "error">
>;

interface CreateGameConnectionControllerOptions {
  onStateChange: (patch: ConnectionStatePatch) => void;
  onMessage: (message: GameMessage) => void;
  getReconnectContext: () => { screen: Screen; roomId: string };
}

interface ConnectParams {
  roomId: string;
  playerName: string;
  uuid: string;
}

export function createGameConnectionController({
  onStateChange,
  onMessage,
  getReconnectContext,
}: CreateGameConnectionControllerOptions) {
  let currentSocket: WebSocket | null = null;
  let pingIntervalId: ReturnType<typeof setInterval> | null = null;
  let lastPingTime = 0;
  let reconnectAttempts = 0;
  let reconnectTimeoutId: ReturnType<typeof setTimeout> | null = null;
  let briscolaAnnouncementSequence = 0;

  const clearPingInterval = () => {
    if (!pingIntervalId) {
      return;
    }

    clearInterval(pingIntervalId);
    pingIntervalId = null;
  };

  const clearReconnectTimeout = () => {
    if (!reconnectTimeoutId) {
      return;
    }

    clearTimeout(reconnectTimeoutId);
    reconnectTimeoutId = null;
  };

  const scheduleReconnect = (params: ConnectParams) => {
    const reconnectContext = getReconnectContext();
    if (
      reconnectContext.screen !== "game" ||
      reconnectAttempts >= MAX_RECONNECT_ATTEMPTS
    ) {
      return;
    }

    reconnectAttempts += 1;
    const delay = RECONNECT_BASE_DELAY_MS * reconnectAttempts;
    reconnectTimeoutId = setTimeout(() => {
      reconnectTimeoutId = null;
      connect({ ...params, roomId: reconnectContext.roomId });
    }, delay);
  };

  const connect = (params: ConnectParams) => {
    clearReconnectTimeout();
    clearPingInterval();

    if (
      currentSocket &&
      (currentSocket.readyState === WebSocket.OPEN ||
        currentSocket.readyState === WebSocket.CONNECTING)
    ) {
      currentSocket.close();
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/ws/${params.roomId}?player_name=${encodeURIComponent(params.playerName)}&uuid=${encodeURIComponent(params.uuid)}`;
    const socket = new WebSocket(url);
    currentSocket = socket;

    socket.onopen = () => {
      reconnectAttempts = 0;
      clearReconnectTimeout();
      onStateChange({ connected: true, pingStatus: "offline", pingMs: null });

      clearPingInterval();
      pingIntervalId = setInterval(() => {
        if (currentSocket?.readyState !== WebSocket.OPEN) {
          return;
        }

        lastPingTime = Date.now();
        currentSocket.send(JSON.stringify({ type: "ping" }));
      }, PING_INTERVAL_MS);
    };

    socket.onmessage = (event) => {
      onMessage(JSON.parse(event.data as string) as GameMessage);
    };

    socket.onclose = () => {
      if (currentSocket === socket) {
        currentSocket = null;
      }

      clearPingInterval();
      onStateChange({ connected: false, pingStatus: "offline" });
      scheduleReconnect(params);
    };

    socket.onerror = () => {
      onStateChange({ error: "Errore di connessione" });
    };
  };

  const send = (message: unknown) => {
    if (currentSocket?.readyState !== WebSocket.OPEN) {
      return;
    }

    currentSocket.send(JSON.stringify(message));
  };

  const disconnect = ({
    intentional = false,
  }: { intentional?: boolean } = {}) => {
    if (intentional) {
      reconnectAttempts = MAX_RECONNECT_ATTEMPTS;
    }

    clearReconnectTimeout();
    clearPingInterval();

    if (!currentSocket) {
      onStateChange({ connected: false, pingStatus: "offline" });
      return;
    }

    const socketToClose = currentSocket;
    currentSocket = null;

    if (
      socketToClose.readyState === WebSocket.OPEN ||
      socketToClose.readyState === WebSocket.CONNECTING
    ) {
      socketToClose.close();
    }

    onStateChange({ connected: false, pingStatus: "offline" });
  };

  return {
    connect,
    disconnect,
    send,
    getLatency: () => Date.now() - lastPingTime,
    nextAnnouncementEventId: () => {
      briscolaAnnouncementSequence += 1;
      return briscolaAnnouncementSequence;
    },
  };
}
