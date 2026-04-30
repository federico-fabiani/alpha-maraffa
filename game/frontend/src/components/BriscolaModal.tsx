import { APP_LAYOUT } from "../layout/layout";
import { SUIT_META } from "./cardMeta";
import type { Suit } from "../types";

interface BriscolaModalProps {
  onSelect: (suit: Suit) => void;
}

const SUITS: Suit[] = ["bastoni", "denara", "spade", "coppe"];

export default function BriscolaModal({ onSelect }: BriscolaModalProps) {
  const playingAreaCenterY =
    "calc(var(--bg-render-top) + (var(--bg-render-height) * (var(--layout-playing-area-top) + (var(--layout-playing-area-height) / 2))))";
  const maxAllowedCenterY =
    `calc(var(--bg-render-top) + (var(--bg-render-height) * (var(--layout-playing-area-top) + var(--layout-playing-area-height))) + var(--hand-playing-area-delta) + ${APP_LAYOUT.cards.hand.hoverTranslate} - ${APP_LAYOUT.briscolaModal.handClearance} - (${APP_LAYOUT.briscolaModal.estimatedHeight} / 2))`;

  return (
    <div
      className="game-popup-overlay bg-felt-950/25 animate-fade-in"
      style={{
        zIndex: 20,
        display: "block",
      }}
    >
      <div
        className="game-popup-card"
        style={{
          position: "absolute",
          left: "50%",
          top: `min(${playingAreaCenterY}, ${maxAllowedCenterY})`,
          transform: "translate(-50%, -50%)",
          width: APP_LAYOUT.briscolaModal.width,
          padding: `${APP_LAYOUT.briscolaModal.cardPaddingY} ${APP_LAYOUT.briscolaModal.cardPaddingX}`,
        }}
      >
        <h3
          className="game-popup-title font-cinzel mb-2"
          style={{ fontSize: APP_LAYOUT.briscolaModal.titleFontSize }}
        >
          SCEGLI LA BRISCOLA
        </h3>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
            gap: APP_LAYOUT.briscolaModal.gridGap,
          }}
        >
          {SUITS.map((suit) => {
            const meta = SUIT_META[suit];
            return (
              <button
                key={suit}
                onClick={() => onSelect(suit)}
                className="bg-felt-800 hover:bg-felt-700 border border-felt-700 hover:border-current rounded-lg transition-all group"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: APP_LAYOUT.briscolaModal.gridGap,
                  padding: `${APP_LAYOUT.briscolaModal.buttonPaddingY} ${APP_LAYOUT.briscolaModal.buttonPaddingX}`,
                  color: meta.color,
                } as React.CSSProperties}
              >
                <span style={{ fontSize: APP_LAYOUT.briscolaModal.buttonIconSize }}>{meta.symbol}</span>
                <span
                  className="font-semibold group-hover:text-current transition-colors text-amber-100"
                  style={{ fontSize: APP_LAYOUT.briscolaModal.buttonLabelSize }}
                >
                  {meta.label}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
