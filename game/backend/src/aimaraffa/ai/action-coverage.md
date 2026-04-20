# Copertura dell'Action Space

Questa nota documenta il cambiamento introdotto nel punto 2 della review: aumentare la copertura del dataset senza cambiare il paradigma di training basato su XGBoost.

## Problema di partenza

La pipeline originale generava il dataset quasi interamente da self-play della policy piu' recente, con una sola leva di diversificazione: `DATASET_EPSILON`.

Questo aveva due limiti pratici:

- la maggior parte degli stati visitati veniva prodotta sempre dalla stessa policy;
- per ogni stato, le azioni osservate tendevano a concentrarsi sulle stesse linee, quindi il modello vedeva poca varianza comportamentale.

In altre parole, la pipeline aveva un buon throughput ma una copertura limitata del comportamento plausibile attorno alla policy corrente.

## Scelta implementata

In questa iterazione ho introdotto due meccanismi complementari: un **mix di policy a livello di seat** per la copertura degli stati, e un **campionamento controfattuale delle azioni** per la copertura delle azioni.

La scelta implementata e' questa:

1. mantenere `epsilon`-greedy come fonte di esplorazione locale;
2. aggiungere un **mix di policy a livello di seat** durante la generazione del dataset di training;
3. aggiungere **rollout controfattuali** per stimare il valore delle azioni non scelte;
4. lasciare invariati analisi e tournament, che restano focalizzati sulla policy candidata pura.

## Come funziona il mix di policy

Nuovi parametri in `config.py`:

- `DATASET_EXPLORATION_TOP_K`;
- `DATASET_POLICY_MIX`.

Il training dataset viene ora generato campionando, per ogni seat di ogni partita, una policy da questa distribuzione:

```python
DATASET_POLICY_MIX = (
    ("latest", 0.60),
    ("prev1", 0.20),
    ("prev2", 0.10),
    ("random", 0.10),
)
```

Semantica dei label:

- `latest`: ultimo modello disponibile;
- `prev1`: modello immediatamente precedente;
- `prev2`: due versioni prima;
- `random`: agente uniforme sulle mosse legali.

Se `prev1` o `prev2` non esistono ancora, il label resta valido ma viene risolto a comportamento random. Questo rende il mix robusto anche nelle prime versioni della pipeline.

## Perche' seat-level e non solo game-level

La scelta e' seat-level, non partita-level, perche' l'obiettivo qui non e' solo avere partite diverse, ma tavoli eterogenei.

Questo produce tre effetti utili:

- espone il modello a stati che nascono da avversari e partner diversi;
- evita che tutta la traiettoria di una mano sia autogenerata dalla sola ultima policy;
- aumenta la probabilita' di vedere linee alternative rimanendo vicino alla policy corrente.

In pratica, e' una via di mezzo tra self-play puro e popolazione di agenti.

## Cosa migliora davvero

Questo cambiamento migliora soprattutto:

- la copertura degli **stati visitati**;
- la varieta' delle **azioni osservate**;
- la robustezza del training rispetto a tavoli non omogenei.

Non risolve completamente il problema teorico della supervisione parziale per stato: il counterfactual sampling (sezione successiva) completa il quadro stimando anche il valore delle azioni non scelte.

## Cosa non ho implementato qui

Deliberatamente fuori scope in questo step:

- training pairwise o ranking loss;
- replay buffer esplicito multi-epoca.

Queste opzioni restano possibili, ma richiedono un redesign piu' profondo del training loop.

## Counterfactual action sampling

Questa sezione documenta l'estensione implementata dopo il mix di policy: il campionamento controfattuale delle azioni.

### Problema residuo

Anche con il mix di policy, il dataset conteneva un solo outcome per ogni stato visitato: quello dell'azione effettivamente giocata. Il modello non vedeva mai "cosa sarebbe successo se avessi giocato un'altra carta nello stesso identico stato".

### Scelta implementata

Ad ogni decisione durante la generazione del dataset di training, con probabilita' configurabile:

1. si enumerano le azioni legali alternative (esclusa quella scelta);
2. si campionano 1-3 alternative, preferibilmente dal top-K del modello piu' una casuale;
3. per ciascuna alternativa, si clona lo stato corrente (incluse le assegnazioni seat→policy), si gioca la carta alternativa, e si simula il resto del round; ogni decisione nel rollout usa il modello assegnato a quel seat dal policy mix, cosi' il target CF resta coerente con la distribuzione di policy che ha generato la traiettoria originale;
4. il `future_pts_diff` risultante viene usato come target per la riga controfattuale.

Le righe prodotte hanno lo stesso stato del giocatore (mano, tavolo, storia, punteggi) ma una carta diversa e un outcome diverso. Il campo `decision_id` raggruppa le azioni generate dallo stesso stato; `is_executed_action` distingue l'azione reale da quelle controfattuali; `action_source` indica se l'alternativa e' stata scelta dal modello (`topk`), a caso (`random`), o per enumerazione esaustiva (`exhaustive`).

### Parametri in `config.py`

```python
COUNTERFACTUAL_ENABLED      = True
COUNTERFACTUAL_PROBABILITY  = 0.30
COUNTERFACTUAL_ALTERNATIVES = 2
COUNTERFACTUAL_ROLLOUTS     = 3
COUNTERFACTUAL_WEIGHT       = 0.5
```

- `COUNTERFACTUAL_ENABLED`: attiva o disattiva il campionamento.
- `COUNTERFACTUAL_PROBABILITY`: probabilita' di generare alternative per ogni decisione.
- `COUNTERFACTUAL_ALTERNATIVES`: quante alternative campionare per ogni decisione selezionata.
- `COUNTERFACTUAL_ROLLOUTS`: quanti rollout per alternativa. I punteggi finali vengono mediati per ridurre la varianza del target. 1 = singolo rollout (veloce ma rumoroso). 3 = buon compromesso.
- `COUNTERFACTUAL_WEIGHT`: peso delle righe CF nel training XGBoost (`sample_weight`). 1.0 = uguale alle righe eseguite. 0.5 = il CF conta meta' nella loss.

### Schema del dataset

Tre nuovi campi alla fine del Parquet:

- `decision_id` (int32): identifica univocamente un punto di decisione all'interno della partita.
- `is_executed_action` (int8): 1 per l'azione realmente giocata, 0 per le alternative controfattuali.
- `action_source` (category): `"policy"`, `"topk"`, `"random"`, `"exhaustive"`.

### Impatto sul training

Il training XGBoost continua a fare regressione su `future_pts_diff`. I tre nuovi campi vengono droppati prima di costruire `X`. Le righe CF hanno peso ridotto nella loss (`COUNTERFACTUAL_WEIGHT`), in modo da non dominare l'obiettivo del modello. Il dataset contiene piu' righe per lo stesso stato, con target diversi: questo permette al modello di imparare un ranking implicito tra azioni a parita' di stato.

### Riduzione della varianza

Un singolo rollout per alternativa produce un target molto rumoroso: il valore di una mossa dipende da come cadono le carte successive. Per questo ogni alternativa viene simulata `COUNTERFACTUAL_ROLLOUTS` volte e il target viene calcolato sulla media dei punteggi finali. Questo riduce la varianza senza moltiplicare il costo proporzionalmente, dato che i rollout coprono solo il round residuo.

### Costi e tradeoff

- Il costo di simulazione aumenta in modo controllato: ogni rollout controfattuale copre solo il resto del round, non l'intera partita.
- Con `COUNTERFACTUAL_PROBABILITY = 0.30`, `COUNTERFACTUAL_ALTERNATIVES = 2` e `COUNTERFACTUAL_ROLLOUTS = 3`, il dataset cresce di circa il 60% in righe ma il tempo di simulazione puo' raddoppiare o triplicare.
- Il simulatore logga automaticamente il tempo speso nei rollout CF e il costo medio per rollout.
- Il rollout usa la policy del modello corrente (non random), quindi il target e' coerente con il self-play.
- Il mix di policy resta attivo: copre gli stati, il counterfactual copre le azioni.

## Impatto su runtime e costi

Il runtime di produzione non cambia.

Il costo extra e' solo nella fase di generazione del dataset di training, dove ora il simulatore puo' caricare piu' booster e raggruppare le decisioni per policy attiva. Il pattern di batching resta pero' lo stesso: si continua a predire in blocco per ridurre il costo di inferenza.

## Regole operative

Linee guida pratiche per usare il mix:

- non alzare troppo la quota `random`, altrimenti il dataset degrada in rumore;
- mantieni `latest` come componente dominante, per non perdere il focus sulla policy migliore disponibile;
- usa `DATASET_EPSILON` per esplorazione locale e `DATASET_POLICY_MIX` per diversita' strutturale;
- se il tournament smette di migliorare ma il report mostra piu' robustezza strategica, riduci gradualmente la quota random invece di toglierla subito.

## Sintesi

La pipeline usa due meccanismi complementari per ampliare la copertura del dataset:

- **Policy mix**: diversifica gli stati visitati campionando policy diverse per ogni seat.
- **Counterfactual sampling**: diversifica le azioni osservate stimando il valore delle mosse non scelte tramite rollout.

Insieme, coprono sia la dimensione degli stati che quella delle azioni, restando compatibili con l'attuale pipeline XGBoost senza introdurre un salto di complessita' sproporzionato.