import { useMemo, useState } from "react";
import { APP_LAYOUT } from "../layout/layout";
import { clamp } from "../layout/rusticBackground";
import LobbyTableSeats from "../components/LobbyTableSeats";
import useGameStore from "../state/gameStore";
import ArrowCtaButton from "../components/ArrowCtaButton";
import ContentRectDebugOverlay from "../components/ContentRectDebugOverlay";
import { DEBUG_MODE } from "../config/debug";
import { useRusticContentRect } from "../hooks/useRusticContentRect";

function hashString(value: string) {
  let hash = 0;

  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }

  return hash;
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
  const { stageRef: rootRef, contentRect } = useRusticContentRect();
  const [swapPendingSeat, setSwapPendingSeat] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);

  const playerBySeat = Object.fromEntries(
    lobbyPlayers.map((player) => [player.seat, player]),
  );
  const badgeByName = useMemo(() => {
    const assigned = new Set<number>();
    const next: Record<string, number> = {};

    [...lobbyPlayers]
      .sort(
        (left, right) =>
          left.name.localeCompare(right.name) || left.seat - right.seat,
      )
      .forEach((player) => {
        let badgeIndex = hashString(player.name) % 4;

        while (assigned.has(badgeIndex)) {
          badgeIndex = (badgeIndex + 1) % 4;
        }

        assigned.add(badgeIndex);
        next[player.name] = badgeIndex;
      });

    return next;
  }, [lobbyPlayers]);

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

  const headerReservedHeight = clamp(
    contentRect.height * APP_LAYOUT.lobby.headerReservedHeight.ratio,
    APP_LAYOUT.lobby.headerReservedHeight.minPx,
    APP_LAYOUT.lobby.headerReservedHeight.maxPx,
  );
  const headerGap = clamp(
    contentRect.height * APP_LAYOUT.lobby.headerGap.ratio,
    APP_LAYOUT.lobby.headerGap.minPx,
    APP_LAYOUT.lobby.headerGap.maxPx,
  );
  const contentPaddingX = clamp(
    contentRect.width * APP_LAYOUT.lobby.contentPaddingX.ratio,
    APP_LAYOUT.lobby.contentPaddingX.minPx,
    APP_LAYOUT.lobby.contentPaddingX.maxPx,
  );
  const contentPaddingY = clamp(
    contentRect.height * APP_LAYOUT.lobby.contentPaddingY.ratio,
    APP_LAYOUT.lobby.contentPaddingY.minPx,
    APP_LAYOUT.lobby.contentPaddingY.maxPx,
  );
  const sectionGap = clamp(
    contentRect.width * APP_LAYOUT.lobby.sectionGap.ratio,
    APP_LAYOUT.lobby.sectionGap.minPx,
    APP_LAYOUT.lobby.sectionGap.maxPx,
  );
  const contentWidth = Math.max(1, contentRect.width - contentPaddingX * 2);
  const contentHeight = Math.max(
    1,
    contentRect.height - contentPaddingY * 2 - headerReservedHeight - headerGap,
  );
  const tableAreaWidth = clamp(
    contentWidth * APP_LAYOUT.lobby.tableArea.widthRatio,
    APP_LAYOUT.lobby.tableArea.minWidthPx,
    Math.min(
      APP_LAYOUT.lobby.tableArea.maxWidthPx,
      Math.max(
        APP_LAYOUT.lobby.tableArea.minWidthPx,
        contentWidth - APP_LAYOUT.lobby.ctaArea.minWidthPx - sectionGap,
      ),
    ),
  );
  const ctaAreaWidth = clamp(
    contentWidth - tableAreaWidth - sectionGap,
    APP_LAYOUT.lobby.ctaArea.minWidthPx,
    APP_LAYOUT.lobby.ctaArea.maxWidthPx,
  );
  const ctaFontSize = clamp(
    contentRect.width * APP_LAYOUT.lobby.ctaFontSize.ratio,
    APP_LAYOUT.lobby.ctaFontSize.minPx,
    APP_LAYOUT.lobby.ctaFontSize.maxPx,
  );

  const shellStyle = {
    position: "absolute",
    left: `${contentRect.left}px`,
    top: `${contentRect.top}px`,
    width: `${contentRect.width}px`,
    height: `${contentRect.height}px`,
    padding: `${contentPaddingY}px ${contentPaddingX}px`,
    boxSizing: "border-box" as const,
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "stretch",
    justifyContent: "flex-start",
    gap: `${headerGap}px`,
    overflow: "hidden",
  } as const;
  const headerStyle = {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "0.8rem",
    width: "100%",
    minHeight: `${headerReservedHeight}px`,
    flex: "0 0 auto",
  } as const;
  const bodyStyle = {
    display: "flex",
    flexDirection: "row" as const,
    alignItems: "stretch",
    justifyContent: "flex-start",
    gap: `${sectionGap}px`,
    width: "100%",
    height: `${contentHeight}px`,
    flex: "1 1 auto",
    minHeight: 0,
  };
  const tableAreaStyle = {
    display: "flex",
    flex: "0 0 auto",
    width: `${tableAreaWidth}px`,
    maxWidth: `${tableAreaWidth}px`,
    minWidth: 0,
    minHeight: `${contentHeight}px`,
    height: "100%",
  };
  const ctaAreaStyle = {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "stretch",
    justifyContent: "center",
    flex: "0 0 auto",
    width: `${ctaAreaWidth}px`,
    maxWidth: `${ctaAreaWidth}px`,
    minWidth: 0,
    minHeight: `${contentHeight}px`,
  };
  const rootStyle = {
    position: "relative",
    width: "100%",
    height: "100%",
  } as const;
  const actionsStyle = {
    display: "flex",
    flexDirection: "column" as const,
    gap: "0.45rem",
    width: "100%",
    alignItems: "center",
  };
  const ctaStyle = {
    fontSize: `${ctaFontSize}px`,
  } as const;
  const hintStyle = {
    maxWidth: "100%",
  } as const;
  const tableHint = isOwner
    ? "Clicca su due posti occupati per scambiarli."
    : "Attendi altri giocatori o avvio partita.";

  return (
    <div ref={rootRef} style={rootStyle}>
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
          <div style={tableAreaStyle}>
            <LobbyTableSeats
              bounds={{ width: tableAreaWidth, height: contentHeight }}
              mySeat={mySeat}
              ownerSeat={ownerSeat}
              isOwner={isOwner}
              playerBySeat={playerBySeat}
              badgeByName={badgeByName}
              swapPendingSeat={swapPendingSeat}
              onSeatClick={handleSeatClick}
              onPromotePlayer={promotePlayer}
              onKickPlayer={kickPlayer}
              tableHint={tableHint}
            />
          </div>

          <div style={ctaAreaStyle}>
            <div className="lobby-actions-panel">
              <div style={actionsStyle}>
                <ArrowCtaButton
                  label="Inizia"
                  onClick={startGame}
                  disabled={!isOwner}
                  className={`home-menu-item lobby-home-cta${!isOwner ? " disabled" : ""}`}
                  style={ctaStyle}
                  ariaLabel="Inizia"
                />
                <ArrowCtaButton
                  label="Esci"
                  onClick={reset}
                  className="home-menu-item lobby-home-cta"
                  style={ctaStyle}
                  ariaLabel="Esci"
                />
              </div>
              <p className="lobby-hint" style={hintStyle}>
                {isOwner
                  ? "I posti liberi verranno riempiti da bot quando inizi."
                  : "Solo proprietario del tavolo puo avviare partita."}
              </p>
            </div>
          </div>
        </div>
      </div>

      <ContentRectDebugOverlay rect={contentRect} enabled={DEBUG_MODE} />
    </div>
  );
}
