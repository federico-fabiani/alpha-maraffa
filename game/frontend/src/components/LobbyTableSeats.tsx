import type { CSSProperties } from "react";
import { useEffect, useRef, useState } from "react";
import { APP_LAYOUT } from "../layout/layout";
import badgeRooster from "../assets/lobby/badge_rooster.png";
import badgeKeys from "../assets/lobby/badge_keys.png";
import badgeGrapes from "../assets/lobby/badge_grapes.png";
import badgeVase from "../assets/lobby/badge_vase.png";
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

const BADGE_IMAGES = [badgeRooster, badgeKeys, badgeGrapes, badgeVase];

function getBadgeStyle(badgeIndex: number): CSSProperties {
  return {
    backgroundImage: `url(${BADGE_IMAGES[badgeIndex] ?? BADGE_IMAGES[0]})`,
    backgroundSize: "cover",
    backgroundPosition: "center",
    backgroundRepeat: "no-repeat",
  };
}

type SeatAnimState = "entering" | "swapping" | null;
const EMPTY_ANIM: Record<number, SeatAnimState> = {
  0: null,
  1: null,
  2: null,
  3: null,
};

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
  nameSeatGapPx?: number;
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
  nameSeatGapPx,
}: LobbyTableSeatsProps) {
  const { seat: seatLayout, table: tableLayout } = APP_LAYOUT.lobby;
  const resolvedNameSeatGapPx = nameSeatGapPx ?? seatLayout.nameSeatGapPx;

  // ── Animation tracking ────────────────────────────────────────────────────
  const prevNamesRef = useRef<Record<number, string | null>>({
    0: null,
    1: null,
    2: null,
    3: null,
  });
  const [seatAnim, setSeatAnim] =
    useState<Record<number, SeatAnimState>>(EMPTY_ANIM);

  useEffect(() => {
    const prev = prevNamesRef.current;
    const curr: Record<number, string | null> = {
      0: null,
      1: null,
      2: null,
      3: null,
    };
    for (let s = 0; s < 4; s++) {
      const p = playerBySeat[s];
      curr[s] = p && !p.is_bot ? p.name : null;
    }

    // Detect seats whose names cross-matched → they swapped
    const swapping = new Set<number>();
    for (let a = 0; a < 4; a++) {
      for (let b = a + 1; b < 4; b++) {
        if (curr[a] && curr[b] && curr[a] === prev[b] && curr[b] === prev[a]) {
          swapping.add(a);
          swapping.add(b);
        }
      }
    }

    const newAnim: Record<number, SeatAnimState> = {
      0: null,
      1: null,
      2: null,
      3: null,
    };
    let hasChange = false;

    for (let s = 0; s < 4; s++) {
      if (curr[s] !== prev[s]) {
        hasChange = true;
        if (swapping.has(s)) {
          newAnim[s] = "swapping";
        } else if (curr[s] !== null) {
          newAnim[s] = "entering";
        }
      }
    }

    prevNamesRef.current = curr;

    if (hasChange) {
      setSeatAnim(newAnim);
      const timer = setTimeout(() => setSeatAnim(EMPTY_ANIM), 900);
      return () => clearTimeout(timer);
    }
  }, [playerBySeat]);

  // ── Badge size (scales with table width) ─────────────────────────────────
  // Use max badge size to pre-compute reserves without circular dependency.
  const edgeReserve =
    seatLayout.badgeSizeMaxPx / 2 +
    resolvedNameSeatGapPx +
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
    right: { x: tableLeft + tableWidth, y: tableTop + tableHeight / 2 },
    top: { x: tableLeft + tableWidth / 2, y: tableTop },
    left: { x: tableLeft, y: tableTop + tableHeight / 2 },
  };

  // ── Name label positioning ─────────────────────────────────────────────
  const nameOffset = badgeSize / 2 + resolvedNameSeatGapPx;

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
        const isHuman = player && !player.is_bot;
        const badgeIndex = isHuman ? (badgeByName[player.name] ?? 0) : 0;
        const isMe = seat === mySeat;
        const isPending = swapPendingSeat === seat;
        const isVertical = area === "left" || area === "right";
        const anchor = anchors[area];
        const anim = seatAnim[seat];

        return (
          <div
            key={seat}
            className="lobby-seat-anchor"
            style={{ left: `${anchor.x}px`, top: `${anchor.y}px` }}
          >
            {/* Badge — centered on anchor via CSS translate(-50%, -50%) */}
            {/* onClick lives here (not on the 0x0 anchor) so iOS hit-testing works */}
            <div
              className={[
                "lobby-seat-badge-shell",
                isPending ? "is-pending" : "",
                anim === "entering" ? "is-entering" : "",
                anim === "swapping" ? "is-swapping" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              style={{
                width: `${badgeSize}px`,
                height: `${badgeSize}px`,
                boxShadow:
                  "0 6px 0 rgba(69, 24, 11, 0.16), 0 10px 18px rgba(0, 0, 0, 0.24)",
                cursor: isOwner ? "pointer" : "default",
                touchAction: "manipulation",
              }}
              onClick={() => onSeatClick(seat)}
            >
              {isHuman ? (
                <div
                  className="lobby-player-badge"
                  style={getBadgeStyle(badgeIndex)}
                />
              ) : (
                <div className="lobby-seat-placeholder" />
              )}
            </div>

            {/* Name label — north/south: horizontal; east/west: vertical */}
            <div style={getLabelStyle(area)} onClick={() => onSeatClick(seat)}>
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
                  {player && ownerSeat === seat && (
                    <span className="lobby-crown">♛</span>
                  )}
                  {player?.name ?? "IA"}
                </span>
              ) : (
                <div
                  className={`lobby-player-label${player ? "" : " is-ai"}`}
                  style={{
                    fontSize: `${nameFontSize}px`,
                    whiteSpace: "nowrap",
                  }}
                >
                  {player && ownerSeat === seat && (
                    <span className="lobby-crown">♛</span>
                  )}
                  <span className="lobby-player-name">
                    {player?.name ?? "IA"}
                  </span>
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
