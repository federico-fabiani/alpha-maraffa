import { useEffect, useMemo, useRef, useState } from "react";
import { APP_LAYOUT } from "../layout/layout";
import arrowImg from "../assets/arrow.png";
import useGameStore from "../state/gameStore";

const SEAT_AREA = ["bottom", "right", "top", "left"] as const;
const TEAM_COLOR = ["#c8922a", "#8b3a1a", "#c8922a", "#8b3a1a"];

type Rect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function intersectRect(rect: Rect, maxWidth: number, maxHeight: number): Rect {
  const left = clamp(rect.left, 0, maxWidth);
  const top = clamp(rect.top, 0, maxHeight);
  const right = clamp(rect.left + rect.width, 0, maxWidth);
  const bottom = clamp(rect.top + rect.height, 0, maxHeight);

  return {
    left,
    top,
    width: Math.max(0, right - left),
    height: Math.max(0, bottom - top),
  };
}

function computeLobbySafeRect(stageWidth: number, stageHeight: number): Rect {
  const frameRect = APP_LAYOUT.lobby.frameRect;
  const renderWidth = stageHeight * APP_LAYOUT.lobby.backgroundAspectRatio;
  const renderHeight = stageHeight;
  const renderLeft = (stageWidth - renderWidth) / 2;
  const projectedFrame = intersectRect(
    {
      left: renderLeft + renderWidth * frameRect.x,
      top: renderHeight * frameRect.y,
      width: renderWidth * frameRect.width,
      height: renderHeight * frameRect.height,
    },
    stageWidth,
    stageHeight,
  );

  return {
    left: projectedFrame.left + APP_LAYOUT.lobby.safeInsetX,
    top: projectedFrame.top + APP_LAYOUT.lobby.safeInsetY,
    width: Math.max(1, projectedFrame.width - APP_LAYOUT.lobby.safeInsetX * 2),
    height: Math.max(
      1,
      projectedFrame.height - APP_LAYOUT.lobby.safeInsetY * 2,
    ),
  };
}

export default function LobbyScreen() {
  const roomId = useGameStore((state) => state.roomId);
  const mySeat = useGameStore((state) => state.mySeat);
  const isOwner = useGameStore((state) => state.isOwner);
  const lobbyPlayers = useGameStore((state) => state.lobbyPlayers);
  const startGame = useGameStore((state) => state.startGame);
  const swapSeats = useGameStore((state) => state.swapSeats);
  const kickPlayer = useGameStore((state) => state.kickPlayer);
  const promotePlayer = useGameStore((state) => state.promotePlayer);
  const ownerSeat = useGameStore((state) => state.ownerSeat);
  const reset = useGameStore((state) => state.reset);

  const rootRef = useRef<HTMLDivElement | null>(null);
  const [swapPendingSeat, setSwapPendingSeat] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);
  const [safeRect, setSafeRect] = useState<Rect>({
    left: 0,
    top: 0,
    width: APP_LAYOUT.lobby.basePanelWidth,
    height: APP_LAYOUT.lobby.basePanelHeight,
  });

  const playerBySeat = Object.fromEntries(
    lobbyPlayers.map((player) => [player.seat, player]),
  );

  useEffect(() => {
    const root = rootRef.current;
    if (!root) {
      return;
    }

    const updateSafeRect = () => {
      const nextWidth = root.clientWidth;
      const nextHeight = root.clientHeight;
      if (!nextWidth || !nextHeight) {
        return;
      }

      setSafeRect(computeLobbySafeRect(nextWidth, nextHeight));
    };

    updateSafeRect();

    const resizeObserver = new ResizeObserver(updateSafeRect);
    resizeObserver.observe(root);

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  const handleCopyRoomId = () => {
    void navigator.clipboard.writeText(roomId).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleSeatClick = (seat: number) => {
    if (!isOwner) {
      return;
    }

    if (swapPendingSeat === null) {
      if (!playerBySeat[seat]) {
        return;
      }

      setSwapPendingSeat(seat);
      return;
    }

    if (swapPendingSeat === seat) {
      setSwapPendingSeat(null);
      return;
    }

    swapSeats(swapPendingSeat, seat);
    setSwapPendingSeat(null);
  };

  const panelScale = useMemo(() => {
    const widthScale = safeRect.width / APP_LAYOUT.lobby.basePanelWidth;
    const heightScale = safeRect.height / APP_LAYOUT.lobby.basePanelHeight;

    return Math.min(widthScale, heightScale, 1);
  }, [safeRect.height, safeRect.width]);
  const ctaFontSize = clamp(
    safeRect.width * APP_LAYOUT.lobby.ctaFontSize.ratio,
    APP_LAYOUT.lobby.ctaFontSize.minPx,
    APP_LAYOUT.lobby.ctaFontSize.maxPx,
  );

  const panelHostStyle = {
    position: "absolute",
    left: `${safeRect.left}px`,
    top: `${safeRect.top}px`,
    width: `${safeRect.width}px`,
    height: `${safeRect.height}px`,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  } as const;
  const wrapStyle = {
    width: `${APP_LAYOUT.lobby.basePanelWidth}px`,
    height: `${APP_LAYOUT.lobby.basePanelHeight}px`,
    transform: `scale(${panelScale})`,
    transformOrigin: "center center",
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    justifyContent: "space-between",
  };
  const shellStyle = {
    display: "flex",
    flexDirection: "column" as const,
    width: "100%",
    height: "100%",
    gap: "0.9rem",
  };
  const headerStyle = {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "0.9rem",
    width: "100%",
  } as const;
  const bodyStyle = {
    display: "flex",
    flexDirection: "row" as const,
    alignItems: "stretch",
    justifyContent: "space-between",
    gap: "1.1rem",
    width: "100%",
    flex: 1,
    minHeight: 0,
  };
  const leftColumnStyle = {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    justifyContent: "center",
    flex: "1 1 0",
    width: "60%",
    minWidth: 0,
    minHeight: 0,
    gap: "0.45rem",
  };
  const rightColumnStyle = {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    justifyContent: "center",
    flex: "0 0 28%",
    width: "28%",
    minWidth: 0,
    gap: "0.7rem",
  };
  const rootStyle = {
    position: "relative",
    width: "100%",
    height: "100%",
  } as const;
  const actionsStyle = {
    display: "flex",
    flexDirection: "column" as const,
    gap: "0.7rem",
    width: "100%",
    alignItems: "center",
  };
  const ctaStyle = {
    fontSize: `${ctaFontSize}px`,
  } as const;
  const hintStyle = {
    maxWidth: "15rem",
  } as const;

  return (
    <div ref={rootRef} style={rootStyle}>
      <div style={panelHostStyle}>
        <div className="lobby-wrap" style={wrapStyle}>
          <div style={shellStyle}>
            <div style={headerStyle}>
              <h2 className="lobby-heading">Codice tavolo</h2>
              <button
                onClick={handleCopyRoomId}
                title="Clicca per copiare"
                className="lobby-code-box"
              >
                <p className="lobby-code-value">{copied ? "COPIATO" : roomId}</p>
              </button>
            </div>

            <div style={bodyStyle}>
              <div style={leftColumnStyle}>
                <div className="lobby-table">
          {[0, 1, 2, 3].map((seat) => {
            const player = playerBySeat[seat];
            const isMe = seat === mySeat;
            const teamColor = TEAM_COLOR[seat];
            const isPending = swapPendingSeat === seat;
            const isClickable =
              isOwner && (!!player || swapPendingSeat !== null);
            const area = SEAT_AREA[seat];

            return (
              <div
                key={seat}
                onClick={() => handleSeatClick(seat)}
                className={[
                  "lobby-seat-card",
                  `lobby-seat-${area}`,
                  isMe ? "is-me" : "",
                  isPending ? "is-pending" : "",
                  isClickable ? "cursor-pointer" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                style={{ "--team-color": teamColor } as React.CSSProperties}
              >
                <div className={`lobby-avatar${player ? "" : " empty"}`}>
                  {player ? (
                    <span>{player.name.charAt(0).toUpperCase()}</span>
                  ) : (
                    <span>–</span>
                  )}
                </div>

                {player ? (
                  <div className="lobby-seat-info">
                    <p className="lobby-seat-name">
                      {ownerSeat === seat && (
                        <span className="lobby-owner-crown">♛ </span>
                      )}
                      {player.name}
                      {isMe && <span className="lobby-me-tag"> (tu)</span>}
                    </p>
                    {isOwner && !isMe && !player.is_bot && (
                      <div className="lobby-seat-actions">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            promotePlayer(seat);
                          }}
                          title="Promuovi a owner"
                          className="lobby-action-btn"
                        >
                          ♛
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            kickPlayer(seat);
                          }}
                          title="Espelli"
                          className="lobby-action-btn"
                        >
                          ✕
                        </button>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="lobby-seat-empty">Attesa…</p>
                )}
              </div>
            );
          })}
                </div>

                {isOwner && (
                  <p className="lobby-hint">
                    {swapPendingSeat !== null
                      ? `Seleziona il secondo posto da scambiare…`
                      : "Clicca due posti per scambiarli."}
                  </p>
                )}
              </div>

              <div style={rightColumnStyle}>
                <div style={actionsStyle}>
                  <button
                    onClick={startGame}
                    disabled={!isOwner}
                    className={`home-menu-item lobby-home-cta${!isOwner ? " disabled" : ""}`}
                    style={ctaStyle}
                  >
                    <img
                      src={arrowImg}
                      alt=""
                      aria-hidden="true"
                      className="home-arrow home-arrow-left home-hover-arrow"
                    />
                    <span className="home-menu-label">Inizia</span>
                    <img
                      src={arrowImg}
                      alt=""
                      aria-hidden="true"
                      className="home-arrow home-hover-arrow"
                    />
                  </button>
                  <button
                    onClick={reset}
                    className="home-menu-item lobby-home-cta"
                    style={ctaStyle}
                  >
                    <img
                      src={arrowImg}
                      alt=""
                      aria-hidden="true"
                      className="home-arrow home-arrow-left home-hover-arrow"
                    />
                    <span className="home-menu-label">Esci</span>
                    <img
                      src={arrowImg}
                      alt=""
                      aria-hidden="true"
                      className="home-arrow home-hover-arrow"
                    />
                  </button>
                </div>
                <p className="lobby-hint" style={hintStyle}>
                  {isOwner
                    ? "I posti liberi verranno riempiti da bot."
                    : "Solo il proprietario del tavolo puo avviare la partita."}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
