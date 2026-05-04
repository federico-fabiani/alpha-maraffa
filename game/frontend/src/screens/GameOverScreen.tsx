import useGameStore from "../state/gameStore";

export default function GameOverScreen() {
  const gameOverData = useGameStore((s) => s.gameOverData);
  const mySeat = useGameStore((s) => s.mySeat);
  const players = useGameStore((s) => s.players);
  const reset = useGameStore((s) => s.reset);

  if (!gameOverData) return null;

  const myTeam = mySeat !== null ? (mySeat % 2 === 0 ? 1 : 2) : null;
  const didWin = myTeam === gameOverData.winner_team;
  const isSpectator = myTeam === null;
  const scores = gameOverData.scores;

  const teamNames = (team: 1 | 2) =>
    players
      .filter((p) => p.team === team)
      .map((p) => p.name)
      .join(" & ");

  return (
    <div
      style={{
        height: "100%",
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "clamp(0.75rem, 2vh, 1.5rem) clamp(1rem, 4vw, 2rem)",
        boxSizing: "border-box",
      }}
    >
      <div
        className="animate-fade-in"
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "clamp(0.6rem, 2.5vmin, 1.5rem)",
          width: "100%",
          maxWidth: "min(88vw, 22rem)",
        }}
      >
        {/* Result header */}
        <div className="text-center">
          <h1
            className={`font-cinzel font-bold tracking-widest ${
              isSpectator
                ? "text-felt-400"
                : didWin
                  ? "text-amber-400 glow-gold"
                  : "text-blue-400"
            }`}
            style={{
              fontSize: "clamp(1.6rem, 8vmin, 3.5rem)",
              lineHeight: 1.1,
            }}
          >
            {isSpectator
              ? `VINCE TEAM ${gameOverData.winner_team}`
              : didWin
                ? "HAI VINTO"
                : "HAI PERSO"}
          </h1>
          {gameOverData.forfeit_by && (
            <p
              className="text-felt-500 italic"
              style={{
                fontSize: "clamp(0.65rem, 2vmin, 0.8rem)",
                marginTop: "0.25em",
              }}
            >
              {gameOverData.forfeit_by} ha abbandonato la partita
            </p>
          )}
        </div>

        {/* Score card */}
        <div
          className="bg-felt-900 border border-felt-700 rounded-2xl w-full"
          style={{ padding: "clamp(0.65rem, 2.5vmin, 1.25rem)" }}
        >
          <p
            className="text-felt-500 tracking-widest text-center"
            style={{
              fontSize: "clamp(0.55rem, 1.8vmin, 0.72rem)",
              marginBottom: "clamp(0.4rem, 1.5vmin, 0.75rem)",
            }}
          >
            PUNTEGGIO FINALE
          </p>
          {([1, 2] as const).map((team) => {
            const isWinner = team === gameOverData.winner_team;
            const names = teamNames(team);
            return (
              <div
                key={team}
                className="flex justify-between items-center border-b border-felt-800 last:border-0"
                style={{ paddingBlock: "clamp(0.35rem, 1.2vmin, 0.6rem)" }}
              >
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.1em",
                  }}
                >
                  <span
                    className={`font-semibold ${isWinner ? "text-amber-300" : "text-felt-500"}`}
                    style={{ fontSize: "clamp(0.78rem, 2.8vmin, 0.95rem)" }}
                  >
                    {isWinner ? "🏆 " : ""}Team {team}
                  </span>
                  {names && (
                    <span
                      className={
                        isWinner ? "text-amber-200/70" : "text-felt-600"
                      }
                      style={{ fontSize: "clamp(0.6rem, 2vmin, 0.75rem)" }}
                    >
                      {names}
                    </span>
                  )}
                </div>
                <span
                  className={`font-cinzel font-bold ${isWinner ? "text-amber-400" : "text-felt-500"}`}
                  style={{ fontSize: "clamp(1.2rem, 5vmin, 1.8rem)" }}
                >
                  {scores[String(team)] ?? 0}
                </span>
              </div>
            );
          })}
        </div>

        {/* Action */}
        <button
          onClick={reset}
          className="bg-amber-600 hover:bg-amber-500 text-white font-semibold rounded-lg transition-colors font-cinzel tracking-wider w-full"
          style={{
            paddingBlock: "clamp(0.5rem, 1.8vmin, 0.8rem)",
            fontSize: "clamp(0.78rem, 2.8vmin, 0.95rem)",
          }}
        >
          NUOVA PARTITA
        </button>
      </div>
    </div>
  );
}
