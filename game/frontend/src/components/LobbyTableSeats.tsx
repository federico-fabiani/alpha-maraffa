import type { CSSProperties } from "react";
import { APP_LAYOUT } from "../layout/layout";
import playerBadgesImg from "../assets/lobby/player_badges.png";
import type { LobbyPlayer } from "../types";

// seat order maps to SEAT_AREA index: 0=bottom, 1=right, 2=top, 3=left
const SEAT_AREA = ["bottom", "right", "top", "left"] as const;

type SeatArea = (typeof SEAT_AREA)[number];

type Bounds = {
  width: number;
  height: number;
};

type Anchor = {
  x: number;
  y: number;
};

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

// Sprite sheet: 1698×926px, 4 badges in 2×2 grid.
// Real badge centers measured via pixel scan (not symmetric 25%/75%).
const SPRITE_W = 1698;
const SPRITE_H = 926;
const SPRITE_BADGE_D = 377; // actual badge circle diameter in sprite pixels
// [col][row] → [centerX, centerY] in sprite pixels
const SPRITE_BADGE_CENTERS: [number, number][] = [
  [634, 266],  // 0: top-left
  [1064, 266], // 1: top-right
  [634, 660],  // 2: bottom-left
  [1064, 660], // 3: bottom-right
];

function getBadgeStyle(badgeIndex: number, badgeSize: number): CSSProperties {
  const scale = badgeSize / SPRITE_BADGE_D;
  const imgW = SPRITE_W * scale;
  const imgH = SPRITE_H * scale;
  const [bcX, bcY] = SPRITE_BADGE_CENTERS[badgeIndex] ?? SPRITE_BADGE_CENTERS[0];
  const cx = bcX * scale;
  const cy = bcY * scale;
  return {
    backgroundImage: `url(${playerBadgesImg})`,
    backgroundSize: `${imgW}px ${imgH}px`,
    backgroundPosition: `-${cx - badgeSize / 2}px -${cy - badgeSize / 2}px`,
    backgroundRepeat: "no-repeat",
  };
}

type LobbyTableSeatsProps = {
  bounds: Bounds;
  style?: CSSProperties;
  mySeat: number | null;
  ownerSeat: number | null;
  isOwner: boolean;
  playerBySeat: Record<number, LobbyPlayer | undefined>;
  badgeByName: Record<string, number>;
  swapPendingSeat: number | null;
  onSeatClick: (seat: number) => void;
  onPromotePlayer: (seat: number) => void;
  onKickPlayer: (seat: number) => void;
  tableHint: string;
};

export default function LobbyTableSeats({
  bounds,
  style,
  mySeat,
  ownerSeat,
  isOwner,
  playerBySeat,
  badgeByName,
  swapPendingSeat,
  onSeatClick,
  onPromotePlayer,
  onKickPlayer,
  tableHint,
}: LobbyTableSeatsProps) {
  const { seat: seatLayout, table: tableLayout } = APP_LAYOUT.lobby;

  // ── Badge size (scales with table width) ─────────────────────────────────
  // Use max badge size to pre-compute reserves without circular dependency.
  const edgeReserve =
    seatLayout.badgeSizeMaxPx / 2 +
    seatLayout.nameSeatGapPx +
    seatLayout.nameFontSize.maxPx * 2;

  // ── Table: fills all available space within bounds ────────────────────────
  const tableWidth = clamp(
    Math.min(
      bounds.width - edgeReserve * 2,
      (bounds.height - edgeReserve * 2) * tableLayout.displayAspectRatio,
    ),
    tableLayout.minWidthPx,
    tableLayout.maxWidthPx,
  );
  const tableHeight = tableWidth / tableLayout.displayAspectRatio;

  // Table centered in bounds
  const tableLeft = (bounds.width - tableWidth) / 2;
  const tableTop = (bounds.height - tableHeight) / 2;

  // ── Seat sizes (derived from actual tableWidth) ───────────────────────────
  const badgeSize = clamp(
    tableWidth * seatLayout.badgeSizeRatio,
    seatLayout.badgeSizeMinPx,
    seatLayout.badgeSizeMaxPx,
  );
  const nameFontSize = clamp(
    tableWidth * seatLayout.nameFontSize.ratio,
    seatLayout.nameFontSize.minPx,
    seatLayout.nameFontSize.maxPx,
  );

  // ── Seat anchors: one per table edge ─────────────────────────────────────
  const anchors: Record<SeatArea, Anchor> = {
    bottom: { x: tableLeft + tableWidth / 2, y: tableTop + tableHeight },
    right:  { x: tableLeft + tableWidth,     y: tableTop + tableHeight / 2 },
    top:    { x: tableLeft + tableWidth / 2, y: tableTop },
    left:   { x: tableLeft,                  y: tableTop + tableHeight / 2 },
  };

  // ── Name label positioning ─────────────────────────────────────────────
  // nameSeatGapPx = APP_LAYOUT.lobby.seat.nameSeatGapPx = constant gap
  // from badge edge to nearest edge of the name label, same for all 4 seats.
  const nameOffset = badgeSize / 2 + seatLayout.nameSeatGapPx;

  function getLabelStyle(area: SeatArea): CSSProperties {
    switch (area) {
      case "bottom":
        return {
          position: "absolute",
          top: `${nameOffset}px`,
          left: "0px",
          transform: "translateX(-50%)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "0.1rem",
          pointerEvents: "auto",
        };
      case "top":
        return {
          position: "absolute",
          bottom: `${nameOffset}px`,
          left: "0px",
          transform: "translateX(-50%)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "0.1rem",
          pointerEvents: "auto",
        };
      case "right":
        return {
          position: "absolute",
          left: `${nameOffset}px`,
          top: "0px",
          transform: "translateY(-50%)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "0.1rem",
          pointerEvents: "auto",
        };
      case "left":
        return {
          position: "absolute",
          right: `${nameOffset}px`,
          top: "0px",
          transform: "translateY(-50%)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "0.1rem",
          pointerEvents: "auto",
        };
    }
  }

  const tableHintStyle: CSSProperties = {
    width: `${tableWidth * tableLayout.hintMaxWidthRatio}px`,
    maxWidth: `${tableWidth * tableLayout.hintMaxWidthRatio}px`,
    fontSize: `${clamp(tableWidth * 0.085, 16, 22)}px`,
  };

  return (
    <div className="lobby-table-seats-root" style={style}>
      {/* ── Table frame ── */}
      <div
        className="lobby-table-container"
        style={{
          width: `${tableWidth}px`,
          height: `${tableHeight}px`,
          left: `${tableLeft}px`,
          top: `${tableTop}px`,
        }}
      >
        <div className="lobby-table-frame" />
        {isOwner && tableHint && (
          <p className="lobby-table-hint" style={tableHintStyle}>
            {tableHint}
          </p>
        )}
      </div>

      {/* ── Seats ── */}
      {[0, 1, 2, 3].map((seat) => {
        const area = SEAT_AREA[seat];
        const player = playerBySeat[seat];
        const badgeIndex = player ? (badgeByName[player.name] ?? 0) : 0;
        const isMe = seat === mySeat;
        const isPending = swapPendingSeat === seat;
        const isVertical = area === "left" || area === "right";
        const anchor = anchors[area];

        return (
          <div
            key={seat}
            className={`lobby-seat-anchor${isOwner ? " cursor-pointer" : ""}`}
            style={{ left: `${anchor.x}px`, top: `${anchor.y}px` }}
            onClick={() => onSeatClick(seat)}
          >
            {/* Badge — centered on anchor via CSS translate(-50%, -50%) */}
            <div
              className={`lobby-seat-badge-shell${isPending ? " is-pending" : ""}`}
              style={{
                width: `${badgeSize}px`,
                height: `${badgeSize}px`,
                boxShadow:
                  "0 6px 0 rgba(69, 24, 11, 0.16), 0 10px 18px rgba(0, 0, 0, 0.24)",
              }}
            >
              {player ? (
                <div
                  className="lobby-player-badge"
                  style={getBadgeStyle(badgeIndex, badgeSize)}
                />
              ) : (
                <div className="lobby-seat-placeholder" />
              )}
            </div>

            {/* Name label — north/south: horizontal; east/west: vertical */}
            <div style={getLabelStyle(area)}>
              {isVertical ? (
                // Vertical text for east/west to save horizontal space
                <span
                  className={`lobby-player-label${player ? "" : " is-ai"}`}
                  style={{
                    fontSize: `${nameFontSize}px`,
                    writingMode: "vertical-lr",
                    textOrientation: "mixed",
                    lineHeight: 1.1,
                    transform: area === "left" ? "rotate(180deg)" : undefined,
                  }}
                >
                  {player && ownerSeat === seat && "♛ "}
                  {player?.name ?? "IA"}
                </span>
              ) : (
                <div
                  className={`lobby-player-label${player ? "" : " is-ai"}`}
                  style={{ fontSize: `${nameFontSize}px`, whiteSpace: "nowrap" }}
                >
                  {player && ownerSeat === seat && (
                    <span className="lobby-crown">♛</span>
                  )}
                  <span className="lobby-player-name">{player?.name ?? "IA"}</span>
                </div>
              )}

              {/* Owner actions — always horizontal regardless of seat direction */}
              {player && isOwner && !isMe && !player.is_bot && (
                <div
                  className="lobby-seat-actions"
                  style={{ writingMode: "horizontal-tb" }}
                >
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      onPromotePlayer(seat);
                    }}
                    className="lobby-action-btn"
                    title="Passa corona"
                  >
                    Corona
                  </button>
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      onKickPlayer(seat);
                    }}
                    className="lobby-action-btn"
                    title="Espelli"
                  >
                    Espelli
                  </button>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
