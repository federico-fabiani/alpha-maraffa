export const SUIT_META: Record<
  string,
  { symbol: string; label: string; color: string }
> = {
  bastoni: { symbol: "🪵", label: "Bastoni", color: "#d97706" },
  denara: { symbol: "🪙", label: "Denara", color: "#16a34a" },
  spade: { symbol: "🗡️", label: "Spade", color: "#3b82f6" },
  coppe: { symbol: "🍷", label: "Coppe", color: "#ef4444" },
};

export const RANK_FULL: Record<number, string> = {
  1: "Asso",
  2: "Due",
  3: "Tre",
  4: "Quattro",
  5: "Cinque",
  6: "Sei",
  7: "Sette",
  8: "Fante",
  9: "Cavallo",
  10: "Re",
};
