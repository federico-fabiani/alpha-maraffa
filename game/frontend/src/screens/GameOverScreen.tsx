import { APP_LAYOUT } from "../layout/layout";
import useGameStore from "../state/gameStore";

export default function GameOverScreen() {
  const gameOverData = useGameStore((s) => s.gameOverData);
  const mySeat = useGameStore((s) => s.mySeat);
  const reset = useGameStore((s) => s.reset);

  if (!gameOverData) return null;

  const myTeam = mySeat !== null ? (mySeat % 2 === 0 ? 1 : 2) : null;
  const didWin = myTeam === gameOverData.winner_team;
  const scores = gameOverData.scores;
  const rootStyle = {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    height: "100%",
  } as const;
  const panelStyle = {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    gap: APP_LAYOUT.gameOver.panelGap,
  };
  const actionStyle = {
    display: "flex",
    flexDirection: "column" as const,
    gap: "0.75rem",
    width: APP_LAYOUT.gameOver.actionWidth,
  };

  return (
    <div style={rootStyle}>
      <div className="animate-fade-in" style={panelStyle}>
        {/* Result */}
        <div className="text-center">
          <p className="font-cinzel text-lg tracking-widest text-felt-500 mb-2">
            {didWin ? "COMPLIMENTI!" : "SCONFITTA"}
          </p>
          <h1
            className={`font-cinzel text-5xl font-bold ${didWin ? "text-amber-400 glow-gold" : "text-blue-400"}`}
          >
            {didWin ? "HAI VINTO" : "HAI PERSO"}
          </h1>
          <p className="text-felt-500 mt-2 text-sm">
            Vince il Team {gameOverData.winner_team}
          </p>
          {gameOverData.forfeit_by && (
            <p className="text-felt-500 mt-1 text-xs italic">
              {gameOverData.forfeit_by} ha abbandonato la partita
            </p>
          )}
        </div>

        {/* Scores */}
        <div
          className="bg-felt-900 border border-felt-700 rounded-2xl p-6"
          style={{ width: APP_LAYOUT.gameOver.scoreWidth }}
        >
          <p className="text-felt-500 text-xs tracking-widest text-center mb-4">
            PUNTEGGIO FINALE
          </p>
          {[1, 2].map((team) => (
            <div
              key={team}
              className="flex justify-between items-center py-2 border-b border-felt-800 last:border-0"
            >
              <span
                className={`font-semibold ${team === gameOverData.winner_team ? "text-amber-300" : "text-felt-500"}`}
              >
                Team {team} {team === gameOverData.winner_team && "🏆"}
              </span>
              <span
                className={`font-cinzel text-2xl font-bold ${team === gameOverData.winner_team ? "text-amber-400" : "text-felt-500"}`}
              >
                {scores[String(team)] ?? 0}
              </span>
            </div>
          ))}
        </div>

        {/* Actions */}
        <div style={actionStyle}>
          <button
            onClick={reset}
            className="bg-amber-600 hover:bg-amber-500 text-white font-semibold
                       py-3 rounded-lg transition-colors font-cinzel tracking-wider"
          >
            NUOVA PARTITA
          </button>
        </div>
      </div>
    </div>
  );
}
