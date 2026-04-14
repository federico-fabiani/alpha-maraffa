import type { Declaration } from '../types'

interface DeclarationPanelProps {
  onDeclare: (declaration: Declaration) => void
}

const DECLARATIONS: { value: NonNullable<Declaration>; label: string; desc: string }[] = [
  { value: 'busso',    label: 'Busso',    desc: 'Ho la carta più alta del seme' },
  { value: 'striscio', label: 'Striscio', desc: 'Gioco senza pretese' },
  { value: 'volo',     label: 'Volo',     desc: 'Ho tutte le carte alte' },
]

export default function DeclarationPanel({ onDeclare }: DeclarationPanelProps) {
  return (
    <div className="absolute inset-0 bg-felt-950/25 flex items-center justify-center z-30 animate-fade-in">
      <div className="bg-felt-900 border border-amber-800/40 rounded-2xl p-6 w-72 shadow-2xl">
        <h3 className="font-cinzel text-center text-amber-400 text-base font-bold mb-1 tracking-wider">
          DICHIARAZIONE
        </h3>
        <p className="text-felt-500 text-xs text-center mb-4">Prima di giocare, vuoi dichiarare?</p>

        <div className="flex flex-col gap-2 mb-4">
          {DECLARATIONS.map(d => (
            <button
              key={d.value}
              onClick={() => onDeclare(d.value)}
              className="flex items-center gap-3 bg-felt-800 hover:bg-felt-700
                         border border-felt-700 hover:border-amber-600/60
                         rounded-xl px-4 py-3 transition-all text-left group"
            >
              <div>
                <p className="font-semibold text-sm text-amber-100 group-hover:text-amber-300 transition-colors">
                  {d.label}
                </p>
                <p className="text-xs text-felt-500">{d.desc}</p>
              </div>
            </button>
          ))}
        </div>

        <button
          onClick={() => onDeclare(null)}
          className="w-full text-center text-xs text-felt-600 hover:text-felt-400 transition-colors py-1"
        >
          Gioca senza dichiarare
        </button>
      </div>
    </div>
  )
}
