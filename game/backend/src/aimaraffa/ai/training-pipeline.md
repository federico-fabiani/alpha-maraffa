# Pipeline di Training AI

Questa cartella contiene la pipeline completa che addestra, valuta e promuove i modelli usati dal bot di Marafone.

L'entry point normale e' questo:

```bash
uv run python -m aimaraffa.ai
```

Dal root del repository esiste anche questo wrapper:

```bat
train_next_model.bat
```

La pipeline non ha flag CLI: i parametri stanno tutti in `config.py`.

Per l'uso operativo quotidiano, vedi anche `training-runbook.md`.
Per la strategia di copertura del dataset introdotta dopo la review, vedi anche `action-coverage.md`.

## Obiettivo

Ogni esecuzione produce una nuova versione `v<N+1>` a partire dalla migliore sorgente disponibile, poi decide se promuoverla in produzione.

Il ciclo e' sempre questo:

1. individua il modello sorgente;
2. genera un dataset di self-play;
3. addestra un nuovo modello XGBoost;
4. genera un dataset separato per l'analisi;
5. produce un report strategico in Markdown;
6. gioca un tournament head-to-head contro il modello sorgente;
7. promuove il nuovo modello solo se supera la soglia statistica configurata.

## Dove finiscono i file

Gli output del training vivono fuori dal package importabile, in:

```text
artifacts/training/
```

La pipeline usa due slot distinti:

- `artifacts/training/`: directory versionate con dataset, candidate model, importance e report di ogni iterazione.
- `src/scripts/artifacts/`: slot stabile di produzione letto dal backend e incluso nel container.

I file principali del training sono questi:

- `marafone_model.joblib`: modello XGBoost serializzato.
- `marafone_dataset.parquet`: dataset di training generato dal self-play.
- `marafone_analysis_dataset.parquet`: dataset separato per l'analisi post-training.
- `marafone_importance.csv`: feature importance esportate dopo il training.
- `strategy_report.md`: report analitico leggibile da umani.

I file stabili di produzione restano questi:

- `src/scripts/artifacts/marafone_model.joblib`
- `src/scripts/artifacts/PRODUCTION`

## Selezione della versione sorgente

La logica sta in `versions.py`.

Ordine di fallback:

1. ultima directory `v<N>` che contiene `marafone_model.joblib`;
2. file loose `src/scripts/artifacts/marafone_model.joblib`, trattato come baseline legacy `v0`;
3. nessun modello disponibile, quindi bootstrap da self-play random.

Questo significa che la primissima iterazione puo' partire anche senza un modello iniziale.

## Flusso completo

L'orchestrazione sta in `pipeline.py` e chiama cinque stage principali.

### 1. Generazione dataset di training

La funzione chiamata e':

```python
simulate(
    n_games=config.DATASET_GAMES,
    model_path=src_model,
    epsilon=config.DATASET_EPSILON,
    output_path=dataset_path,
)
```

Comportamento:

- se `model_path is None`, il self-play e' random uniforme sulle mosse legali;
- se `model_path` esiste, il self-play usa `MLAgent` e inferenza XGBoost;
- in modalita' ML e' possibile esplorare con epsilon-greedy;
- nella generazione del dataset di training, i seat possono essere campionati da un mix di policy (`latest`, `prev1`, `prev2`, `random`) definito in `config.py`;
- quando `output_path` e' presente, ogni giocata viene serializzata in Parquet.

Dettagli importanti del simulatore:

- scrive un record per-play, non un record per partita;
- usa un encoding role-relative della mano, per essere meno dipendente dal seme assoluto;
- registra storia delle carte gia' viste, stato dichiarazioni e contesto del turno;
- calcola a posteriori il target `future_pts_diff`, cioe' il differenziale di punti futuri della squadra del giocatore che ha preso la decisione.

Il dataset di training serve per insegnare al modello il valore atteso di una decisione locale dentro un round.

### Schema del dataset e delle feature

Il Parquet scritto da `simulator.py` contiene una riga per decisione candidata giocata in self-play, con abbastanza contesto da ricostruire lo stato locale del round.

Il dataset raw contiene questi gruppi di campi:

- identificazione e posizione: `game_id`, `round_num`, `turn_num`, `play_order`, `seat`, `team`;
- contesto briscola: `briscola_suit`, `briscola_selector_is_my_team`;
- carta candidata: `card_rank`, `card_is_briscola`, `card_is_lead`, `is_lead`, `lead_suit`, `declaration`;
- tavolo corrente: `table_0_*`, `table_1_*`, `table_2_*` per descrivere le carte gia' giocate nel turno;
- punteggi correnti: `round_score_t1`, `round_score_t2`, `total_score_t1`, `total_score_t2`;
- mano del giocatore in encoding role-relative:
    - `hand_briscola_<rank>`;
    - `hand_lead_<rank>`;
    - `hand_other_<rank>_count`;
- storia carte gia' viste, per ogni seme e rango:
    - `hist_<suit>_<rank>_is_my_team`;
    - `hist_<suit>_<rank>_turn`;
    - `hist_<suit>_<rank>_decl`;
- stato dedotto dei semi per partner e avversari: `partner_suit_status`, `opp_left_suit_status`, `opp_right_suit_status`;
- outcome retrospettivi del turno e del round: `turn_winner_seat`, `turn_winner_team`, `turn_pts`, `round_pts_t1`, `round_pts_t2`, `round_pts_player_team`, `round_pts_diff`;
- target finale: `future_pts_diff`.

Interpretazione dei gruppi principali:

- `hand_briscola_*` indica se il giocatore possiede quel rango nel seme di briscola;
- `hand_lead_*` indica se possiede quel rango nel seme di apertura, se non e' briscola;
- `hand_other_*_count` conta quante carte di quel rango restano nei semi neutri;
- `hist_*` rappresenta memoria perfetta delle carte gia' uscite nel round;
- `partner_suit_status` e analoghi condensano le informazioni implicite nelle dichiarazioni `busso`, `striscio`, `volo`.

Le categorie nominali sono fissate e devono restare coerenti tra training e inferenza:

- semi: `bastoni`, `coppe`, `denara`, `spade` nel preprocessing Pandas;
- dichiarazioni: `busso`, `striscio`, `volo`;
- suit status: `busso`, `has`, `unknown`, `void`.

### Cosa entra davvero nel modello

Il training non usa l'intero dataset raw cosi' com'e'. Prima di costruire `X`, vengono rimossi:

- identificatori: `game_id`, `seat`;
- campi di leakage o outcome noti solo dopo la decisione: `turn_winner_seat`, `turn_winner_team`, `turn_pts`, `round_pts_t1`, `round_pts_t2`, `round_pts_player_team`, `round_pts_diff`;
- target: `future_pts_diff`;
- `team`, che oggi viene escluso dal training ma resta gestito nel runtime per compatibilita' con modelli piu' vecchi.

Questo punto e' importante: il runtime di `aimaraffa.ml_agent` non assume ciecamente che il modello usi tutte le colonne attuali. Se il booster salvato ha una lista `feature_names` diversa, l'inferenza riallinea le colonne al subset richiesto dal modello.

In pratica:

- il dataset raw e' il contratto massimo disponibile;
- `train.py` e `analyze.py` definiscono il subset usato dai modelli nuovi;
- `ml_agent.py` mantiene la compatibilita' con i booster gia' salvati.

Se cambi una feature, devi verificare tutti e tre i livelli.

### 2. Training del modello

La funzione chiamata e':

```python
train.train(dataset_path, model_path, importance_path)
```

Caratteristiche del training:

- modello: `XGBRegressor`;
- target: `future_pts_diff`;
- split preferito per `game_id`, per evitare leakage tra righe della stessa partita;
- fallback a split per riga solo se ci sono troppe poche partite;
- categorical features gestite via categorie Pandas coerenti con l'inferenza runtime;
- early stopping a 50 round;
- supporto CPU o CUDA tramite `config.DEVICE`.

Output prodotti:

- nuovo `marafone_model.joblib` nella directory della versione corrente;
- `marafone_importance.csv` con le feature ordinate per importanza.

Metriche loggate:

- MAE;
- RMSE;
- $R^2$ su train e test.

## 3. Generazione dataset di analisi

Dopo il training, la pipeline non riusa il dataset usato per addestrare.

Genera invece un secondo dataset con:

- il modello appena addestrato;
- `epsilon = 0.0`;
- output su `marafone_analysis_dataset.parquet`.

Lo scopo e' osservare il comportamento del nuovo modello in self-play deterministico, senza rumore di esplorazione.

## 4. Analisi e report strategico

La funzione chiamata e':

```python
analyze.analyze(analysis_data_path, model_path, report_path)
```

Il report Markdown contiene piu' sezioni, costruite a partire dal dataset di analisi e dal modello addestrato.

Sezioni attuali:

- overview del dataset;
- metriche del modello sul dataset di analisi;
- top feature importance;
- valore medio delle carte per ruolo;
- carte che vincono piu' spesso i turni;
- strategia di scelta della briscola;
- impatto delle dichiarazioni `busso`, `striscio`, `volo`;
- effetto della posizione nel turno;
- pattern delle carte vincenti nei turni ad alto valore;
- correlazioni sulla forza iniziale della mano;
- opzionalmente analisi SHAP se `ANALYSIS_SHAP = True` e la dipendenza e' installata.

Il file risultante e' pensato per capire non solo se il modello funziona, ma anche che tipo di strategia sta emergendo.

## 5. Tournament head-to-head

La funzione chiamata e':

```python
tournament.tournament(
    model_a=new_model,
    model_b=source_model,
    games=config.TOURNEY_GAMES,
    seed=config.TOURNEY_SEED,
)
```

Il tournament serve a decidere se la nuova versione e' davvero migliore della sorgente.

Proprieta' importanti:

- meta' partite con A nel team 1;
- meta' partite con A nel team 2;
- side-swap per ridurre bias di posizione;
- supporta anche match contro agente random se il baseline e' assente.

Statistiche calcolate:

- vittorie A;
- vittorie B;
- pareggi;
- win-rate di A sulle partite decisive;
- intervallo di confidenza Wilson al 95%;
- margine medio punti di A contro B.

Viene anche scritto un log testuale nella directory della versione, con nome del tipo:

```text
tournament_vs_v7.txt
```

## Regola di promozione

La promozione non avviene sul solo win-rate puntuale.

Il nuovo modello viene promosso solo se:

```text
ci95_lo >= PROMOTE_MIN_CI_LOWER
```

Quindi la soglia usa il bound inferiore dell'intervallo al 95%, non la media osservata. E' una scelta conservativa per evitare promozioni rumorose.

Se la promozione passa:

- `artifacts/training/v<N>/marafone_model.joblib` viene copiato su `src/scripts/artifacts/marafone_model.joblib`;
- il file `src/scripts/artifacts/PRODUCTION` viene aggiornato con il nome versione.

Se non passa:

- la directory `v<N>` resta disponibile per ispezione;
- il modello di produzione non cambia.

## Caso bootstrap

Se non esiste alcun modello sorgente:

- il dataset di training viene generato con self-play random;
- il bootstrap disattiva automaticamente policy mix e counterfactual sampling, cosi' il percorso `random -> v1` resta il piu' veloce possibile;
- il primo modello viene addestrato;
- non si gioca alcun tournament;
- la nuova versione viene promossa automaticamente.

Questo e' il meccanismo che crea il primo modello utile del sistema.

## Contratto tra training e runtime

Il punto piu' delicato della pipeline e' la compatibilita' tra:

- schema del dataset scritto da `simulator.py`;
- preprocessing in `train.py` e `analyze.py`;
- encoding usato da `aimaraffa.ml_agent` in inferenza.

In pratica, ordine colonne, categorie e semantica delle feature devono restare allineati. Se cambi una feature in uno di questi punti, devi verificare anche gli altri due.

## Parametri da toccare di solito

I parametri operativi sono in `config.py`.

Quelli piu' importanti sono:

- `DATASET_GAMES`: quante partite generare per il training;
- `DATASET_EPSILON`: quanta esplorazione usare durante il self-play di training;
- `DATASET_EXPLORATION_TOP_K`: ampiezza del top-K usato quando scatta l'esplorazione epsilon-greedy;
- `DATASET_POLICY_MIX`: mix di policy usato per assegnare partner e avversari durante il dataset self-play;
- `ANALYSIS_GAMES`: quante partite usare per l'analisi;
- `TOURNEY_GAMES`: quante partite giocare nel confronto head-to-head;
- `PROMOTE_MIN_CI_LOWER`: soglia statistica di promozione;
- `DEVICE`: `cpu` o `cuda`.

Le principali manopole del modello sono:

- `N_ESTIMATORS`;
- `LEARNING_RATE`;
- `MAX_DEPTH`;
- `SUBSAMPLE`;
- `TEST_SIZE`.

## Esecuzione normale

Workflow consigliato:

1. aggiorna i parametri in `config.py` se serve;
2. esegui `uv run python -m aimaraffa.ai`;
3. controlla la nuova cartella `v<N>` in `artifacts/training/`;
4. leggi `strategy_report.md` e il file `tournament_vs_*.txt`;
5. verifica se `PRODUCTION` e `marafone_model.joblib` sono stati aggiornati.

## Uso dei singoli moduli

Per debug o sviluppo puoi chiamare gli stage separatamente:

```python
from pathlib import Path

from aimaraffa.ai import analyze, simulator, train, tournament

dataset = Path("artifacts/training/vNEXT/marafone_dataset.parquet")
model = Path("artifacts/training/vNEXT/marafone_model.joblib")
importance = Path("artifacts/training/vNEXT/marafone_importance.csv")
analysis_dataset = Path("artifacts/training/vNEXT/marafone_analysis_dataset.parquet")
report = Path("artifacts/training/vNEXT/strategy_report.md")

simulator.simulate(n_games=1000, model_path=None, epsilon=0.1, output_path=dataset)
train.train(dataset, model, importance)
simulator.simulate(n_games=500, model_path=model, epsilon=0.0, output_path=analysis_dataset)
analyze.analyze(analysis_dataset, model, report)
res = tournament.tournament(model, None, games=500)
print(tournament.format_report("candidate", "random", res))
```

## Cosa carica il backend in produzione

Il backend non usa automaticamente l'ultima `v<N>`.

Usa il file stabile:

```text
src/scripts/artifacts/marafone_model.joblib
```

Per questo la fase di promozione e' separata dalla sola fase di training e il training output non vive piu' nella stessa directory semantica del runtime.

## In sintesi

La pipeline e' costruita per fare tre cose in sequenza:

1. generare esperienza sintetica tramite self-play;
2. trasformarla in un modello che stima il valore delle decisioni;
3. promuovere il nuovo modello solo se batte in modo sufficientemente robusto la baseline corrente.

Questo mantiene separati sperimentazione, analisi e deployment del modello attivo.