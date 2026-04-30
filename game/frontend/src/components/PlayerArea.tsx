import type { CSSProperties } from "react";
import { APP_LAYOUT } from "../layout/layout";
import { CardBack } from "./Card";
import type { Declaration, Player } from "../types";

interface PlayerAreaProps {
  player: Player | undefined;
  isActive: boolean;
  position: "top" | "left" | "right";
  declaration?: Declaration;
  showCards?: boolean;
  declarationAside?: boolean;
}

type HandCardBackStyle = CSSProperties & Record<"--hand-index", string>;

const TEAM_BADGE: Record<number, string> = {
  1: "border-amber-500/60 text-amber-300",
  2: "border-blue-500/60  text-blue-300",
};

const DECLARATION_LABEL: Record<string, string> = {
  busso: "BUSSO",
  striscio: "STRISCIO",
  volo: "VOLO",
};

const DECLARATION_BADGE_GAP = "6px";

function getDeclarationBadgeStyle(
  position: "top" | "left" | "right",
  aside: boolean,
): CSSProperties {
  if (position === "top") {
    if (aside) {
      return {
        position: "absolute",
        top: "50%",
        left: "100%",
        transform: "translateY(-50%)",
        marginLeft: DECLARATION_BADGE_GAP,
        whiteSpace: "nowrap",
      };
    }
    return {
      position: "absolute",
      top: "100%",
      left: "50%",
      transform: "translateX(-50%)",
      marginTop: DECLARATION_BADGE_GAP,
      whiteSpace: "nowrap",
    };
  }
  if (position === "left") {
    return {
      position: "absolute",
      top: "100%",
      right: 0,
      marginTop: DECLARATION_BADGE_GAP,
      whiteSpace: "nowrap",
    };
  }
  return {
    position: "absolute",
    top: "100%",
    left: 0,
    marginTop: DECLARATION_BADGE_GAP,
    whiteSpace: "nowrap",
  };
}

export default function PlayerArea({
  player,
  isActive,
  position,
  declaration,
  showCards = true,
  declarationAside = false,
}: PlayerAreaProps) {
  const cardCount = player?.cards_count ?? 0;

  const isHorizontal = position === "top";

  const team = player ? player.team : null;
  const badgeCls = team ? TEAM_BADGE[team] : "border-felt-700 text-felt-500";
  const stackStyles = isHorizontal
    ? { display: "flex", flexDirection: "row" as const }
    : { display: "flex", flexDirection: "column" as const };
  const offsetStyle = isHorizontal
    ? { marginLeft: "var(--layout-opponent-stack-overlap)" }
    : { marginTop: "var(--layout-opponent-stack-overlap)" };
  const wrapperStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    alignItems:
      position === "top"
        ? "center"
        : position === "left"
          ? "flex-end"
          : "flex-start",
    gap: APP_LAYOUT.playerArea.gap,
    position: "relative",
  };
  const createCardBackStyle = (index: number): HandCardBackStyle => ({
    ...(index === 0 ? {} : offsetStyle),
    "--hand-index": `${index}`,
  });

  return (
    <div style={wrapperStyle}>
      {/* Name badge — always first so it never shifts when declaration appears */}
      <div
        className={`
        px-3 py-1 rounded-full text-xs font-medium border bg-felt-900/60
        ${badgeCls}
        ${isActive ? "animate-pulse-ring" : ""}
      `}
      >
        {player ? (
          <>
            {player.name}
            {isActive && <span className="ml-1 text-amber-400">●</span>}
            {!player.is_connected &&
              (player.is_bot ? (
                <span className="ml-1">🤖</span>
              ) : (
                <span className="ml-1 text-red-400">✕</span>
              ))}
          </>
        ) : (
          <span className="italic text-felt-600">Attesa...</span>
        )}
      </div>

      {/* Declaration badge — absolutely positioned so name never shifts */}
      {declaration && (
        <div
          className="px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-widest uppercase bg-amber-900/60 border border-amber-500/50 text-amber-300"
          style={getDeclarationBadgeStyle(position, declarationAside)}
        >
          {DECLARATION_LABEL[declaration] ?? declaration}
        </div>
      )}

      {/* Stacked face-down cards */}
      {showCards && cardCount > 0 && (
        <div style={stackStyles}>
          {Array.from({ length: Math.min(cardCount, 6) }).map((_, i) => (
            <CardBack
              key={i}
              size="sm"
              className="opponent-card-back"
              style={createCardBackStyle(i)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
