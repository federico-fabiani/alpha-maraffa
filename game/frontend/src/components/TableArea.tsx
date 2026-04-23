import { useEffect, useRef, useState } from "react";
import { getCollectVector, getGameTableSlotStyle } from "../layout/layout";
import { Card } from "./Card";
import type { Suit, TableCard } from "../types";

interface TableAreaProps {
  tableCards: TableCard[];
  mySeat: number;
  winnerSeat?: number | null;
  briscolaSuit?: Suit | null;
}

export default function TableArea({
  tableCards,
  mySeat,
  winnerSeat,
  briscolaSuit = null,
}: TableAreaProps) {
  const prevCardsRef = useRef<TableCard[]>([]);
  const savedWinnerRef = useRef<number | null>(null);

  const [collecting, setCollecting] = useState<{
    cards: TableCard[];
    relativeSeat: number;
  } | null>(null);

  // Keep a ref to the last known winner seat (store clears it together with tableCards)
  useEffect(() => {
    if (winnerSeat != null) savedWinnerRef.current = winnerSeat;
  }, [winnerSeat]);

  // When cards are cleared by the server, fire the collection animation
  useEffect(() => {
    const prev = prevCardsRef.current;
    prevCardsRef.current = tableCards;

    if (
      prev.length > 0 &&
      tableCards.length === 0 &&
      savedWinnerRef.current != null
    ) {
      const rel = (savedWinnerRef.current - mySeat + 4) % 4;
      savedWinnerRef.current = null;
      setCollecting({ cards: prev, relativeSeat: rel });
      const t = setTimeout(() => setCollecting(null), 550);
      return () => clearTimeout(t);
    }
  }, [tableCards, mySeat]);

  return (
    <div className="table-area relative w-full h-full z-[2]">
      {/* Live cards */}
      {tableCards.map(({ seat, card }) => {
        const relativeSeat = (seat - mySeat + 4) % 4;
        return (
          <div
            key={seat}
            className={`absolute table-card-slot animate-card-appear${seat === winnerSeat ? " winning-card" : ""}`}
            style={getGameTableSlotStyle(relativeSeat)}
          >
            <Card
              card={card}
              size="table"
              briscolaSuit={briscolaSuit}
              style={{
                width: "var(--table-card-width)",
                height: "var(--table-card-height)",
              }}
            />
          </div>
        );
      })}

      {/* Collection animation overlay — cards fly toward the winner */}
      {collecting &&
        collecting.cards.map(({ seat, card }, idx) => {
          const relativeSeat = (seat - mySeat + 4) % 4;
          const vec = getCollectVector(collecting.relativeSeat, relativeSeat);
          return (
            <div
              key={`collect-${seat}`}
              className="absolute table-card-slot collecting-card"
              style={
                {
                  ...getGameTableSlotStyle(relativeSeat),
                  "--collect-x": `${vec.x}px`,
                  "--collect-y": `${vec.y}px`,
                  "--card-index": idx,
                } as React.CSSProperties
              }
            >
              <Card
                card={card}
                size="table"
                briscolaSuit={briscolaSuit}
                style={{
                  width: "var(--table-card-width)",
                  height: "var(--table-card-height)",
                }}
              />
            </div>
          );
        })}
    </div>
  );
}
