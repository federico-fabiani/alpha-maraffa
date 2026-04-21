import useGameStore from '../store'

export default function GameOverScreen() {
  const gameOverData = useGameStore(s => s.gameOverData)
  const mySeat       = useGameStore(s => s.mySeat)
  const reset        = useGameStore(s => s.reset)

  if (!gameOverData) return null

  const myTeam    = mySeat !== null ? (mySeat % 2 === 0 ? 1 : 2) : null
  const didWin    = myTeam === gameOverData.winner_team
  const scores    = gameOverData.scores

  return (
    <div className="flex items-center justify-center h-full">
      <div className="flex flex-col items-center gap-8 animate-fade-in">

        {/* Result */}
        <div className="text-center">
          <p className="font-cinzel text-lg tracking-widest text-felt-500 mb-2">
            {didWin ? 'COMPLIMENTI!' : 'SCONFITTA'}
          </p>
          <h1 className={`font-cinzel text-5xl font-bold ${didWin ? 'text-amber-400 glow-gold' : 'text-blue-400'}`}>
            {didWin ? 'HAI VINTO' : 'HAI PERSO'}
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
        <div className="bg-felt-900 border border-felt-700 rounded-2xl p-6 w-72">
          <p className="text-felt-500 text-xs tracking-widest text-center mb-4">PUNTEGGIO FINALE</p>
          {[1, 2].map(team => (
            <div key={team} className="flex justify-between items-center py-2 border-b border-felt-800 last:border-0">
              <span className={`font-semibold ${team === gameOverData.winner_team ? 'text-amber-300' : 'text-felt-500'}`}>
                Team {team} {team === gameOverData.winner_team && '🏆'}
              </span>
              <span className={`font-cinzel text-2xl font-bold ${team === gameOverData.winner_team ? 'text-amber-400' : 'text-felt-500'}`}>
                {scores[String(team)] ?? 0}
              </span>
            </div>
          ))}
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-3 w-64">
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
  )
}
