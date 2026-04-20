# Runbook Operativa Training AI

Questa guida e' la checklist corta per lanciare una nuova iterazione di training e capire rapidamente se il risultato e' buono.

Per la descrizione completa dell'architettura, vedi `training-pipeline.md`.

## Comando standard

Dal backend:

```bash
uv run python -m aimaraffa.ai
```

Dal root del repository:

```bat
train_next_model.bat
```

## Prima di lanciare

Controlla `config.py` e in particolare:

- `DATASET_GAMES`;
- `DATASET_EPSILON`;
- `ANALYSIS_GAMES`;
- `TOURNEY_GAMES`;
- `PROMOTE_MIN_CI_LOWER`;
- `DEVICE`.

Regola pratica:

- usa meno partite se vuoi un giro rapido di debug;
- usa piu' partite se vuoi una decisione di promozione piu' affidabile;
- riduci `DATASET_EPSILON` se vuoi meno esplorazione;
- usa `cpu` se la macchina non ha una GPU CUDA stabile per XGBoost.

## Cosa aspettarsi durante il run

L'esecuzione attraversa sempre questi passaggi:

1. scoperta del modello sorgente;
2. generazione dataset di training;
3. training XGBoost;
4. generazione dataset di analisi;
5. report strategico;
6. tournament contro la baseline;
7. eventuale promozione.

Nei log vedrai esplicitamente il source version, il target version e la numerazione `[1/5]`, `[2/5]`, fino al tournament finale.

## Dove guardare dopo il run

Controlla la nuova directory sotto:

```text
artifacts/training/v<N>/
```

I file piu' utili sono:

- `marafone_model.joblib`;
- `marafone_dataset.parquet`;
- `marafone_analysis_dataset.parquet`;
- `marafone_importance.csv`;
- `strategy_report.md`;
- `tournament_vs_<baseline>.txt`.

Poi controlla anche questi due file stabili:

- `src/scripts/artifacts/marafone_model.joblib`;
- `src/scripts/artifacts/PRODUCTION`.

Se sono cambiati, il modello e' stato promosso.

## Come leggere il risultato velocemente

Ordine consigliato:

1. apri `tournament_vs_<baseline>.txt`;
2. controlla `A win-rate` e soprattutto `95% CI`;
3. verifica se `ci95_lo` supera `PROMOTE_MIN_CI_LOWER`;
4. apri `strategy_report.md` per capire che strategia sta emergendo;
5. guarda `marafone_importance.csv` se vuoi capire quali feature stanno guidando il modello.

Interpretazione minima del tournament:

- CI inferiore sopra la soglia: promozione sensata;
- CI che attraversa 50%: risultato inconcludente;
- win-rate alto ma CI inferiore troppo basso: il miglioramento non e' ancora robusto;
- margine medio positivo ma CI debole: possibile segnale utile, ma non ancora da promuovere.

## Come leggere il report strategico

Le sezioni che valgono di piu' in pratica sono queste:

- `Metriche del Modello`: conferma che il modello stia imparando qualcosa di consistente;
- `Feature Importance`: mostra quali segnali usa davvero;
- `Strategia Briscola`: utile per capire se le scelte iniziali sembrano plausibili;
- `Dichiarazioni`: dice come il modello sfrutta `busso`, `striscio`, `volo`;
- `Pattern di Vittoria dei Turni`: utile per capire se sta valorizzando le prese pesanti;
- `Forza della Mano`: aiuta a interpretare le correlazioni piu' forti.

## Quando un run e' sospetto

Segnali da controllare:

- dataset troppo piccolo rispetto al rumore del gioco;
- improvement nel training ma tournament inconcludente;
- feature importance dominate da segnali inattesi o poco robusti;
- report strategico che suggerisce comportamenti controintuitivi ripetuti;
- promozioni troppo frequenti con pochi game, sintomo di soglia o campionamento troppo aggressivi.

## Debug rapido

Se vuoi isolare un problema:

1. abbassa `DATASET_GAMES`, `ANALYSIS_GAMES` e `TOURNEY_GAMES`;
2. esegui la pipeline completa per verificare che il flusso resti integro;
3. se serve, lancia i singoli moduli manualmente come mostrato in `training-pipeline.md`;
4. confronta il contenuto di `strategy_report.md` tra due versioni consecutive.

## Decisione finale

Una run e' da considerare buona quando succedono tutte queste cose insieme:

1. il run termina senza errori e produce tutti gli artifact attesi;
2. il tournament mostra un vantaggio ripetibile, non solo un picco casuale;
3. il report strategico racconta un comportamento coerente con il dominio di gioco;
4. la promozione aggiorna `PRODUCTION` solo quando il bound inferiore del CI lo giustifica.

Se manca uno di questi quattro punti, il run e' utile come esperimento ma non ancora come nuova produzione.