import type { CSSProperties } from "react";
import { APP_LAYOUT } from "../layout/layout";
import playerBadgesImg from "../assets/lobby/player_badges.png";
import type { LobbyPlayer } from "../types";

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

type LobbyTableSeatsProps = {
  bounds: Bounds;
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

function getLabelStyle(
  area: SeatArea,
  topLabelOffset: number,
  sideLabelOffset: number,
  topLabelWidth: number,
  sideLabelWidth: number,
): CSSProperties {
  switch (area) {
    case "top":
      return {
        width: `${topLabelWidth}px`,
        left: "0px",
        bottom: `${topLabelOffset}px`,
        transform: "translate(-50%, -100%)",
        alignItems: "center",
        textAlign: "center",
      };
    case "bottom":
      return {
        width: `${topLabelWidth}px`,
        left: "0px",
        top: `${sideLabelOffset}px`,
        transform: "translateX(-50%)",
        alignItems: "center",
        textAlign: "center",
      };
    case "left":
      return {
        width: `${sideLabelWidth}px`,
        right: `${sideLabelOffset}px`,
        top: "0px",
        transform: "translateY(-50%)",
        alignItems: "flex-end",
        textAlign: "right",
      };
    case "right":
      return {
        width: `${sideLabelWidth}px`,
        left: `${sideLabelOffset}px`,
        top: "0px",
        transform: "translateY(-50%)",
        alignItems: "flex-start",
        textAlign: "left",
      };
  }
}

function getAdaptiveNameFontSize(
  name: string,
  baseFontSize: number,
  area: SeatArea,
) {
  const overflowChars = Math.max(0, name.trim().length - 7);
  const shrinkRate = area === "left" || area === "right" ? 0.72 : 0.48;
  const minScale = area === "left" || area === "right" ? 0.58 : 0.68;

  return clamp(
    baseFontSize - overflowChars * shrinkRate,
    baseFontSize * minScale,
    baseFontSize,
  );
}

function getBadgeImageStyle(badgeIndex: number): CSSProperties {
  const column = badgeIndex % 2;
  const row = Math.floor(badgeIndex / 2);

  return {
    position: "absolute",
    width: "200%",
    height: "200%",
    maxWidth: "none",
    left: `${column * -100}%`,
    top: `${row * -100}%`,
    objectFit: "cover",
    pointerEvents: "none",
    userSelect: "none",
  };
}

export default function LobbyTableSeats({
  bounds,
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
  const seatLayout = APP_LAYOUT.lobby.seat;
  const tableLayout = APP_LAYOUT.lobby.table;
  const tableAspectRatio = tableLayout.displayAspectRatio;
  const labelGap = clamp(
    bounds.width * seatLayout.labelGapRatio,
    seatLayout.labelGapMinPx,
    seatLayout.labelGapMaxPx,
  );
  const innerInset = clamp(
    bounds.width * seatLayout.innerInsetRatio,
    seatLayout.innerInsetMinPx,
    seatLayout.innerInsetMaxPx,
  );
  const topLabelWidth = clamp(
    bounds.width * seatLayout.topLabelWidthRatio,
    seatLayout.topLabelWidthMinPx,
    seatLayout.topLabelWidthMaxPx,
  );
  const sideLabelWidth = clamp(
    bounds.width * seatLayout.sideLabelWidthRatio,
    seatLayout.sideLabelWidthMinPx,
    seatLayout.sideLabelWidthMaxPx,
  );
  const labelLaneDepth = clamp(
    bounds.height * seatLayout.labelLaneDepthRatio,
    seatLayout.labelLaneDepthMinPx,
    seatLayout.labelLaneDepthMaxPx,
  );
  const nameFontSize = clamp(
    bounds.width * seatLayout.nameFontSize.ratio,
    seatLayout.nameFontSize.minPx,
    seatLayout.nameFontSize.maxPx,
  );
  const metaFontSize = clamp(
    bounds.width * seatLayout.metaFontSize.ratio,
    seatLayout.metaFontSize.minPx,
    seatLayout.metaFontSize.maxPx,
  );
  const actionFontSize = clamp(
    bounds.width * seatLayout.actionFontSize.ratio,
    seatLayout.actionFontSize.minPx,
    seatLayout.actionFontSize.maxPx,
  );
  const usableWidth = Math.max(1, bounds.width - innerInset * 2);
  const usableHeight = Math.max(1, bounds.height - innerInset * 2);
  let tableWidth = Math.min(
    tableLayout.maxWidthPx,
    usableWidth -
      (sideLabelWidth + labelGap + seatLayout.badgeSizeMinPx / 2) * 2,
  );

  for (let iteration = 0; iteration < 3; iteration += 1) {
    const iterationBadgeSize = clamp(
      tableWidth * seatLayout.badgeSizeRatio,
      seatLayout.badgeSizeMinPx,
      seatLayout.badgeSizeMaxPx,
    );
    const iterationTopReserve =
      nameFontSize * 1.15 + labelGap + iterationBadgeSize / 2;
    const iterationBottomReserve =
      nameFontSize * 1.2 +
      metaFontSize * 1.2 +
      labelGap +
      iterationBadgeSize / 2;
    const iterationSideReserve =
      sideLabelWidth + labelGap + iterationBadgeSize / 2;
    const nextMaxTableWidth = Math.max(
      1,
      Math.min(
        usableWidth - iterationSideReserve * 2,
        (usableHeight - iterationTopReserve - iterationBottomReserve) *
          tableAspectRatio,
        tableLayout.maxWidthPx,
      ),
    );

    tableWidth = clamp(
      nextMaxTableWidth,
      tableLayout.minWidthPx,
      Math.min(tableLayout.maxWidthPx, nextMaxTableWidth),
    );
  }

  const tableHeight = tableWidth / tableAspectRatio;
  const badgeSize = clamp(
    tableWidth * seatLayout.badgeSizeRatio,
    seatLayout.badgeSizeMinPx,
    seatLayout.badgeSizeMaxPx,
  );
  const topLabelLaneDepth = nameFontSize * 1.18 + 6;
  const sideLabelLaneDepth = Math.max(
    nameFontSize * 1.18 + metaFontSize * 1.1 + 6,
    labelLaneDepth * 0.8,
  );
  const topLabelOffset = Math.max(2, badgeSize / 2 + labelGap - 12);
  const sideLabelOffset = badgeSize / 2 + labelGap;
  const actualTopReserve = topLabelOffset + topLabelLaneDepth;
  const actualBottomReserve =
    sideLabelOffset + sideLabelLaneDepth + actionFontSize * 2.4;
  const actualSideReserve = sideLabelWidth + sideLabelOffset;
  const clusterWidth = tableWidth + actualSideReserve * 2;
  const clusterHeight = tableHeight + actualTopReserve + actualBottomReserve;
  const clusterOffsetX = Math.max(0, (usableWidth - clusterWidth) / 2);
  const clusterOffsetY = Math.max(0, (usableHeight - clusterHeight) / 2);
  const tableLeft = innerInset + clusterOffsetX + actualSideReserve;
  const tableTop = innerInset + clusterOffsetY + actualTopReserve;
  const tableHintStyle = {
    width: `${(tableWidth * tableLayout.hintMaxWidthRatio).toFixed(1)}px`,
    maxWidth: `${(tableWidth * tableLayout.hintMaxWidthRatio).toFixed(1)}px`,
    fontSize: `${clamp(tableWidth * 0.085, 16, 22)}px`,
  } as const;

  const anchors: Record<SeatArea, Anchor> = {
    top: {
      x: tableLeft + tableWidth / 2,
      y: tableTop,
    },
    bottom: {
      x: tableLeft + tableWidth / 2,
      y: tableTop + tableHeight,
    },
    left: {
      x: tableLeft,
      y: tableTop + tableHeight / 2,
    },
    right: {
      x: tableLeft + tableWidth,
      y: tableTop + tableHeight / 2,
    },
  };

  const nameStyle = {
    fontSize: `${nameFontSize}px`,
    lineHeight: 1.05,
  } as const;
  const metaStyle = {
    fontSize: `${metaFontSize}px`,
    lineHeight: 1,
  } as const;
  const actionStyle = {
    fontSize: `${actionFontSize}px`,
  } as const;
  const badgeStyle = {
    width: `${badgeSize}px`,
    height: `${badgeSize}px`,
  } as const;

  return (
    <div className="lobby-table-seats-root">
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
        {isOwner && tableHint ? (
          <p className="lobby-table-hint" style={tableHintStyle}>
            {tableHint}
          </p>
        ) : null}
      </div>

      {[0, 1, 2, 3].map((seat) => {
        const area = SEAT_AREA[seat];
        const player = playerBySeat[seat];
        const badgeIndex = player ? (badgeByName[player.name] ?? 0) : 0;
        const isMe = seat === mySeat;
        const isPending = swapPendingSeat === seat;
        const labelStyle = getLabelStyle(
          area,
          topLabelOffset,
          sideLabelOffset,
          topLabelWidth,
          sideLabelWidth,
        );
        const resolvedName = player ? player.name : "IA";
        const resolvedNameFontSize = getAdaptiveNameFontSize(
          resolvedName,
          nameFontSize,
          area,
        );
        const resolvedNameStyle = {
          ...nameStyle,
          fontSize: `${resolvedNameFontSize}px`,
        } as const;
        const playerNameStyle = {
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        } as const;

        return (
          <div
            key={seat}
            className={`lobby-seat-anchor${isOwner ? " cursor-pointer" : ""}`}
            style={{
              left: `${anchors[area].x}px`,
              top: `${anchors[area].y}px`,
            }}
            onClick={() => onSeatClick(seat)}
          >
            <div
              className={`lobby-seat-badge-shell${isPending ? " is-pending" : ""}`}
              style={{
                ...badgeStyle,
                boxShadow:
                  "0 6px 0 rgba(69, 24, 11, 0.16), 0 10px 18px rgba(0, 0, 0, 0.24)",
              }}
            >
              {player ? (
                <div className="lobby-player-badge">
                  <img
                    src={playerBadgesImg}
                    alt=""
                    aria-hidden="true"
                    draggable={false}
                    style={getBadgeImageStyle(badgeIndex)}
                  />
                </div>
              ) : (
                <div className="lobby-seat-placeholder" />
              )}
            </div>

            <div
              className={`lobby-seat-name-block lobby-seat-name-block-${area}`}
              style={labelStyle}
            >
              <div
                className={`lobby-player-label${player ? "" : " is-ai"}`}
                style={resolvedNameStyle}
              >
                {player && ownerSeat === seat && (
                  <span className="lobby-crown">♛</span>
                )}
                <span className="lobby-player-name" style={playerNameStyle}>
                  {resolvedName}
                </span>
              </div>

              {player && isMe && (
                <div className="lobby-me-indicator" style={metaStyle}>
                  Tu
                </div>
              )}

              {player && isOwner && !isMe && !player.is_bot && (
                <div
                  className={`lobby-seat-actions lobby-seat-actions-${area}`}
                >
                  <button
                    onClick={(event) => {
                      event.stopPropagation();
                      onPromotePlayer(seat);
                    }}
                    className="lobby-action-btn"
                    style={actionStyle}
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
                    style={actionStyle}
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
