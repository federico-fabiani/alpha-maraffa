const WIN_THRESHOLD = 41

interface ScoreBoardProps {
  round: number
  turn: number
  totalScores: Record<string, number>
  roundScores: Record<string, number>
}

export default function ScoreBoard({ round, turn, totalScores, roundScores }: ScoreBoardProps) {
  return (
    <div className="bg-felt-900/80 border border-felt-700/60 rounded-xl p-3 w-44 backdrop-blur-sm">
      <div className="flex justify-between text-xs text-felt-500 mb-2">
        <span>Round {round}</span>
        <span>Turno {turn}/10</span>
      </div>

      {[1, 2].map(team => {
        const total = totalScores[String(team)] ?? 0
        const round_ = roundScores[String(team)] ?? 0
        const pct    = Math.min((total / WIN_THRESHOLD) * 100, 100)

        return (
          <div key={team} className="mb-2 last:mb-0">
            <div className="flex justify-between items-center mb-1">
              <span className={`text-xs font-semibold ${team === 1 ? 'text-amber-300' : 'text-blue-300'}`}>
                Team {team}
              </span>
              <div className="flex items-baseline gap-1">
                <span className={`font-cinzel font-bold text-base ${team === 1 ? 'text-amber-400' : 'text-blue-400'}`}>
                  {total}
                </span>
                {round_ > 0 && (
                  <span className="text-xs text-felt-500">+{round_}</span>
                )}
              </div>
            </div>
            {/* Progress bar toward 41 */}
            <div className="h-1 rounded-full bg-felt-800 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${team === 1 ? 'bg-amber-500' : 'bg-blue-500'}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
