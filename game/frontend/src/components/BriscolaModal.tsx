import { APP_LAYOUT } from "../layout/layout";
import { SUIT_META } from "./cardMeta";
import type { Suit } from "../types";

interface BriscolaModalProps {
  onSelect: (suit: Suit) => void;
  selectorName?: string;
}

const SUITS: Suit[] = ["bastoni", "denara", "spade", "coppe"];

export default function BriscolaModal({
  onSelect,
  selectorName,
}: BriscolaModalProps) {
  return (
    <div
      className="game-popup-overlay bg-felt-950/25 animate-fade-in"
      style={{
        zIndex: 20,
      }}
    >
      <div
        className="game-popup-card"
        style={{ width: APP_LAYOUT.briscolaModal.width }}
      >
        <h3 className="game-popup-title font-cinzel text-lg mb-1">
          SCEGLI LA BRISCOLA
        </h3>
        {selectorName && (
          <p className="game-popup-subtitle text-xs mb-5">{selectorName}</p>
        )}

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
                className="bg-felt-800 hover:bg-felt-700
                           border border-felt-700 hover:border-current
                           rounded-xl p-3 transition-all group"
                style={
                  {
                    display: "flex",
                    alignItems: "center",
                    gap: APP_LAYOUT.briscolaModal.gridGap,
                    "--tw-border-opacity": "0.6",
                    color: meta.color,
                  } as React.CSSProperties
                }
              >
                <span className="text-2xl">{meta.symbol}</span>
                <span className="font-semibold text-sm group-hover:text-current transition-colors text-amber-100">
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
