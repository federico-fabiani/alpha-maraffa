import { getCardSizeStyle } from "../layout/layout";
import type { Card as CardType, Suit } from "../types";
import { RANK_FULL, SUIT_META } from "./cardMeta";

// ── Lookup tables ──────────────────────────────────────────────────────────────

const SUIT_ROW: Record<string, number> = {
  bastoni: 0,
  coppe: 1,
  denara: 2,
  spade: 3,
};

export interface CardSpriteCoords {
  col: number;
  row: number;
  xPct: number;
  yPct: number;
}

export function getCardSpriteCoords(
  card: Pick<CardType, "suit" | "rank">,
): CardSpriteCoords {
  const col = Math.max(0, Math.min(9, card.rank - 1));
  const row = SUIT_ROW[card.suit] ?? 0;
  const xPct = (col / 9) * 100;
  const yPct = (row / 3) * 100;
  return { col, row, xPct, yPct };
}

// ── Card face ──────────────────────────────────────────────────────────────────

interface CardProps {
  card: CardType;
  size?: "sm" | "md" | "lg" | "table";
  briscolaSuit?: Suit | null;
  onClick?: () => void;
  className?: string;
  style?: React.CSSProperties;
}

export function Card({
  card,
  size = "md",
  briscolaSuit = null,
  onClick,
  className = "",
  style,
}: CardProps) {
  const meta = SUIT_META[card.suit];
  const sizeStyle = getCardSizeStyle(size);
  const isPlayable = card.playable === true;
  const coords = getCardSpriteCoords(card);
  const isBriscola = card.suit === briscolaSuit;

  return (
    <div
      role={isPlayable ? "button" : undefined}
      tabIndex={isPlayable ? 0 : undefined}
      onClick={onClick}
      onKeyDown={
        isPlayable ? (e) => e.key === "Enter" && onClick?.() : undefined
      }
      title={`${RANK_FULL[card.rank]} di ${meta.label}`}
      data-sprite-coords={`${coords.col},${coords.row}`}
      style={
        {
          color: meta.color,
          width: sizeStyle.width,
          height: sizeStyle.height,
          "--card-sprite-x": `${coords.xPct}%`,
          "--card-sprite-y": `${coords.yPct}%`,
          "--card-accent": meta.color,
          ...style,
        } as React.CSSProperties
      }
      className={`
        card-face card-sprite
        ${isPlayable ? "playable" : ""}
        ${isBriscola ? "briscola-card" : ""}
        ${className}
      `}
    >
      <div className="card-art" />
    </div>
  );
}

// ── Card back ──────────────────────────────────────────────────────────────────

interface CardBackProps {
  size?: "sm" | "md" | "lg" | "table";
  className?: string;
  style?: React.CSSProperties;
}

export function CardBack({
  size = "md",
  className = "",
  style,
}: CardBackProps) {
  const sizeStyle = getCardSizeStyle(size);
  return (
    <div
      className={`card-back ${className}`}
      style={{ width: sizeStyle.width, height: sizeStyle.height, ...style }}
    />
  );
}
