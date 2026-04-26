# Pipeline RL per Maraffa: Decisioni di Design

> Documento didattico — spiega ogni scelta architetturale, le alternative scartate, e perché.

---

## 1. Il Problema

Maraffa è un gioco di carte italiano 4 giocatori, 2 squadre. Ogni "mano" ha 10 turni. Ogni turno ogni giocatore gioca una carta. Chi vince il turno raccoglie i punti. La squadra che arriva a 41 punti totali vince.

Le complessità rilevanti per l'RL:

- **Informazione nascosta**: non vedi le carte degli altri
- **Azione variabile**: il numero di mosse legali cambia a ogni turno (dipende da mano, briscola, tavolo)
- **Dichiarazioni**: quando sei il primo a giocare devi anche dichiarare (striscio/busso/volo/niente)
- **Selezione briscola**: chi ha il re di bastoni sceglie il seme "atout"
- **Reward ritardato**: la mossa giusta in turno 3 potrebbe essere ripagata solo in turno 7

---

## 2. Algoritmo: PPO (Proximal Policy Optimization)

### Cosa è

PPO è un algoritmo di policy gradient on-policy con clipping. Addestra una rete neurale che mappa stato→azione, aggiornandola in mini-batch con un vincolo implicito che limita quanto cambia la policy a ogni step.

### Perché PPO

| Algoritmo | Motivo per escluderlo |
|---|---|
| **DQN / Rainbow** | Richiede Q(s,a) definita su spazio fisso. Le azioni legali cambiano ogni turno → tabella Q non funziona nativamente |
| **REINFORCE** | Varianza altissima. Con episodi di 80-200 decisioni il gradiente è rumoroso → convergenza lentissima |
| **A3C / IMPALA** | Più complesso da implementare, richiede architettura asincrona. PPO raggiunge qualità simile con meno codice |
| **SAC** | Progettato per spazi continui. Adattarlo a azioni discrete è possibile ma non naturale |
| **AlphaZero + MCTS** | Molto più potente, ma richiede milioni di partite e MCTS inference. Con 6GB VRAM e obiettivo "battere l'euristico" è overkill |
| **PPO ✓** | On-policy, azioni discrete, varianza moderata, stabile, ampiamente testato su board game e card game |

### Perché on-policy (non off-policy)

Off-policy (DQN, SAC) riusa vecchie esperienze da un replay buffer. In self-play questo crea problemi: le partite vecchie sono state giocate da una policy diversa. I dati "stantii" danneggiano la stabilità in giochi dove la policy avversaria cambia continuamente. PPO on-policy usa solo le partite dell'iterazione corrente.

---

## 3. Setup Self-Play

### Policy condivisa tra tutti e 4 i seat

Una singola rete controlla tutti e 4 i giocatori. Alternativa: reti separate per squadra o per seat.

**Motivo della scelta unica**:
- Efficienza parametri: impara più velocemente con 4× più esperienze per iterazione
- Generalizza su tutte le posizioni (seat 0, 1, 2, 3 hanno ruoli diversi)
- Standard nei giochi cooperativo-competitivi (simile ad AlphaZero in Go)

### 50% partite vs HeuristicAgent

Senza avversario fisso, self-play puro converge a **equilibri degeneri**: due policy che si "capiscono" ma non giocano bene contro qualcosa di esterno. Il 50% di partite contro l'euristico forza la policy a imparare pattern di gioco sensati.

Questo si chiama **curriculum learning** — prima impari da un insegnante (euristico), poi ti sfidi da solo.

---

## 4. Rete Neurale: Actor-Critic MLP

### Architettura

```
Input: matrice [K × 181] float32
       K = numero di mosse legali per questa decisione
       181 = feature per candidato (stessa encoding dell'XGBoost)

Per ogni candidato k:
    LayerNorm(181)
    → Linear(181→256) + LayerNorm + GELU
    → Linear(256→256) + LayerNorm + GELU
    → Linear(256→256) + LayerNorm + GELU
    → embedding[k] di dim 256

Policy head:  Linear(256→1) per ogni k  →  logits[K]  →  Categorical
Value head:   mean_pool(embeddings validi)  →  Linear(256→1)  →  V(s) scalare
```

### Perché MLP e non qualcosa di più sofisticato

| Architettura | Perché scartata |
|---|---|
| **Transformer** | Le 181 feature già codificano storia e stato del tavolo esplicitamente. L'attention sarebbe utile se avessimo rappresentazione raw (sequenza di carte giocate). Aggiunge complessità senza beneficio garantito |
| **LSTM / GRU** | La storia è già dentro le 181 feature (colonne `hist_*`). Non serve memoria recorrente esplicita |
| **CNN** | Nessuna struttura spaziale nelle carte. CNN non si applica |
| **Graph Neural Network** | Le carte hanno relazioni (stessa squadra, stesso seme) ma modellarle come grafo è overkill per 6GB VRAM |
| **MLP ✓** | Semplice, interpretabile, funziona bene su dati tabulari strutturati, facile debug |

### LayerNorm invece di BatchNorm

BatchNorm normalizza sulla dimensione batch. Con batch size variabile (K diverso per ogni decisione) e mini-batch da training, BatchNorm instabilizza. LayerNorm normalizza per sample → stabile in RL dove la distribuzione degli input cambia continuamente.

### GELU invece di ReLU

GELU ha gradiente non nullo per valori negativi (a differenza di ReLU che "muore"). Funziona meglio con LayerNorm. Standard nelle architetture moderne (GPT, BERT).

### Inizializzazione ortogonale, policy head gain=0.01

All'inizio del training vogliamo una policy quasi-uniforme (ogni mossa ha probabilità simile). Con gain=0.01 i logits iniziali sono quasi zero → distribuzione piatta → esplorazione massima al primo iter.

### Sophistication: **5/10**

Non è triviale (masking variabile, LayerNorm, candidate scoring, orthogonal init), ma è conservativo rispetto allo stato dell'arte. Una rete 8/10 userebbe embedding per carte, attention sul tavolo, belief state esplicito.

---

## 5. Rappresentazione delle Azioni: Candidate Scoring

### L'approccio scelto

Per ogni decisione costruiamo una matrice [K × 181]: ogni riga è una possibile mossa (carta + dichiarazione) con tutto il contesto già incorporato. La rete assegna un logit a ogni riga. Si campiona dalla Categorical risultante.

### Alternative scartate

**A) Policy su spazio fisso (40 carte × 4 dichiarazioni = 160 azioni)**
- Problema: la maggior parte è illegale ogni turno → mask enorme e rumorosa
- Il gradiente si "spreca" su azioni mai eseguibili

**B) Autoregressive: prima scegli carta, poi dichiarazione**
- Più naturale per l'umano
- Richiede 2 forward pass per decisione
- Complica il calcolo dei log_prob per PPO

**C) Candidate scoring ✓**
- K azioni sempre tutte legali (nessuna da mascherare tranne padding)
- Un solo forward pass
- Le 181 feature già includono il contesto completo della mossa candidata

---

## 6. Le 181 Feature

Stesso encoding dell'agente XGBoost (`_build_base_row` + `_expand_candidates`). Questo è un **transfer di feature engineering**: anni di lavoro sul modello supervisionato riusati gratis.

| Gruppo | Feature | Cosa codifica |
|---|---|---|
| Contesto round | round_num, turn_num, play_order | Posizione nella partita |
| Candidato | card_rank, is_briscola, is_lead, declaration | La mossa specifica |
| Tavolo | table_0/1/2 rank/suit/team | Le carte già giocate questo turno |
| Punteggio | round_score t1/t2, total_score t1/t2 | Stato della partita |
| Mano | hand_briscola_*, hand_lead_*, hand_other_* | Carte ancora in mano |
| Storia | hist_{carta}_is_my_team, _turn, _decl | Tutte le carte già giocate nei turni precedenti |
| Status avversari | partner/opp_left/opp_right suit_status | void/busso/striscio/unknown per ogni avversario |

### Perché non imparare embedding da zero

Con 1000 partite/iterazione e una rete che parte da zero, imparare anche la rappresentazione del gioco sarebbe troppo. Le 181 feature danno una "spalla" di conoscenza dominio che accelera la convergenza.

---

## 7. Reward Signal

### Segnale scelto: per-trick, denso

```python
reward = trick_points × (+1 se la mia squadra vince il turno, -1 se perde)
# ultimo turno: +1 bonus distribuito allo stesso modo
```

Ogni decisione che contribuisce a vincere un turno riceve il reward del turno retroattivamente (dopo la risoluzione).

### Perché non game-end reward

```
win/lose ±1 al termine della partita
```

Con 80-200 decisioni per partita, il reward arriva troppo tardi. Il modello non capisce quale mossa specifica ha influenzato l'esito. Si chiama **sparse reward problem**.

### Perché non shaped reward più elaborato

Potremmo aggiungere bonus per dichiarazioni corrette, penalità per aver sprecato briscole, etc. Ma ogni reward shaping introduce bias. Il modello potrebbe ottimizzare il reward shaping e non il gioco reale. Il segnale per-trick è il minimo necessario.

### Alternativa: regret-based reward

Si potrebbe calcolare il rimpianto (quanto avresti vinto giocando la mossa ottimale). Richiede un oracolo o MCTS. Fuori scope per ora.

---

## 8. Loss Function PPO

### Formula completa

```
L_total = L_policy + 0.5 × L_value + 0.05 × L_entropy

L_policy  = -E[min(r_t × A_t,  clip(r_t, 1-ε, 1+ε) × A_t)]
            dove r_t = π(a|s) / π_old(a|s)   (importance ratio)
            e ε = 0.2

L_value   = 0.5 × E[(V(s) - R_t)²]    (MSE tra valore stimato e return)

L_entropy = -E[H(π(·|s))]              (negativo dell'entropia → massimizziamo esplorazione)
```

### GAE (Generalized Advantage Estimation)

Il vantaggio A_t dice "questa mossa era meglio o peggio di quanto mi aspettavo?". 

```
A_t = Σ (γλ)^k × δ_{t+k}
      dove δ_t = r_t + γ V(s_{t+1}) - V(s_t)
```

- `γ = 1.0`: nessun discount. Tutti i turni di una partita hanno lo stesso peso. Con partite brevi (10 turni/round) non ha senso scontare.
- `λ = 0.95`: bias-variance tradeoff. λ=1 è Monte Carlo (alta varianza), λ=0 è TD(0) (alto bias).

### Perché il clipping PPO

Senza clipping, un aggiornamento troppo grande cambia la policy drasticamente. La mossa che sembrava buona con la policy vecchia potrebbe diventare pessima con la nuova. Il clipping limita il ratio r_t ∈ [1-ε, 1+ε] = [0.8, 1.2], garantendo aggiornamenti stabili.

### Alternative alla loss

| Loss | Perché scartata |
|---|---|
| **TRPO** (Trust Region PO) | Implementa il vincolo con Lagrangian e KL constraint. Più teoricamente rigoroso di PPO ma molto più complesso da implementare |
| **A2C** | Stesso actor-critic ma senza clipping. Meno stabile di PPO in pratica |
| **V-trace** (IMPALA) | Pensato per off-policy distributed training. Overkill qui |
| **PPO ✓** | Semplicità + stabilità + performance. Standard de facto per card game RL |

### Return Normalization

Prima del PPO update, normalizziamo i returns:

```python
returns = (returns - returns.mean()) / (returns.std() + 1e-8)
```

Senza questo, la value loss era >13. I returns grezzi hanno scala ~[-50, +50] (somma di punti per turno). La rete fatica a stimarli. Normalizzarli a ~N(0,1) stabilizza il training: value loss scende a ~0.5.

---

## 9. Training Loop

### Pipeline per iterazione

```
[1] Rollout collection (8 worker CPU)
    → 1000 partite complete
    → ~150-250k decisioni totali
    → workers usano policy corrente in inferenza

[2] GAE computation (main process)
    → calcola advantages e returns per ogni episodio
    → normalizza returns

[3] PPO update (GPU, BF16, fused Adam)
    → 6 epoch su tutti i dati
    → mini-batch 2048 decisioni
    → TF32 + BF16 autocast → ~5x vs CPU

[4] Save checkpoint

[5] Tournament (2000 partite vs champion)
    → se CI lower bound ≥ 50.5%: promuovi a produzione
```

### Warmup learning rate

Primi 3 iter: lr parte da 3e-5 (10% del lr nominale) e scala a 3e-4. Motivazione: con weights casuali i gradienti iniziali sono rumorosi. Un lr basso evita aggiornamenti distruttivi all'inizio.

---

## 10. Configurazione Hardware e Scelte di Scala

### RTX 3060 Laptop, 6GB VRAM

Questo vincolo ha guidato molte scelte conservative:

| Scelta conservativa | Alternativa possibile | Perché non ora |
|---|---|---|
| MLP 256×3 | Transformer 512×8 | Transformer richiederebbe 3-4× VRAM |
| 1000 partite/iter | 10000+ | Tempo training esagerato |
| Workers CPU | Workers CUDA | Con 6GB, GPU occupata dal training, non dai workers |
| Nessun MCTS | MCTS inference | Richiede 1000+ simulazioni/mossa, impraticabile real-time |

### Speedups implementati

- **CUDA + cuDNN** con torch 2.11+cu128
- **TF32**: matmul Ampere 10-bit mantissa, ~2-3x più veloce, loss trascurabile
- **BF16 autocast**: dimezza bandwidth memoria, nessuna perdita di accuratezza su Ampere
- **Fused Adam**: singolo kernel CUDA invece di loop Python
- **pin_memory + non_blocking**: trasferimento H→D asincrono, overlappa con compute
- **8 worker CPU**: satura i 16 core per rollout collection

---

## 11. Quanto è Sofisticata la Rete? 5/10

### Cosa la pone sopra il baseline

- Variable action space con masking (non banale)
- Candidate scoring (design non ovvio)
- LayerNorm + GELU (architettura moderna)
- Orthogonal init con gain calibrato
- Return normalization
- BF16 / TF32 / fused optimizer

### Cosa manca per arrivare a 8-9/10

| Feature | Beneficio stimato |
|---|---|
| **Card embeddings** (rank×suit → dense vector) | Cattura relazioni tra carte dello stesso seme |
| **Attention sul tavolo** (transformer mini su 4 carte giocate) | Modella esplicitamente "chi ha giocato cosa" |
| **Belief state esplicito** (distribuzione sulle carte nascoste) | Affrontare l'informazione nascosta in modo principled |
| **Population-based training** (pool di policy) | Evita overfitting a una specifica strategia avversaria |
| **Reward normalization online** (per-batch, non solo per-epoch) | Ulteriore stabilità |
| **MCTS a inference** | Salto di qualità enorme ma richiede simulatore veloce |

---

## 12. Cosa Sta Imparando il Modello

Il modello non riceve regole. Impara esclusivamente da reward (+/- punti per turno). Deve quindi scoprire autonomamente:

1. **Quando giocare briscola**: le briscole valgono di più ma sono risorse limitate
2. **Gestione delle dichiarazioni**: busso segnala forza al partner, volo segnala assenza del seme
3. **Quando sacrificare punti bassi**: perdere un 2 per far vincere un 3 al partner
4. **Lettura del tavolo**: se l'avversario ha già giocato briscola, puoi giocare più liberamente
5. **Coordinazione con il partner**: segnali impliciti attraverso le mosse
6. **Gestione del punteggio**: giocare diversamente a 38-40 rispetto a 10-10

Questi concetti emergono dal reward signal senza che nessuno li espliciti. È questo il punto dell'RL.

---

## 13. Aspettative Realistiche

| Iterazioni | Win rate vs heuristic atteso |
|---|---|
| 1-5 | 3-5% (casuale migliorato) |
| 10-20 | 10-25% (capisce mosse basiche) |
| 30-50 | 30-45% (gioca decentemente) |
| 80-150 | 50%+ (batte l'euristico) |
| 200+ | Superiore all'euristico in modo stabile |

Il margine punto sta già migliorando (da -17.9 a -16.4 in 4 iter). Il segnale c'è. Serve più tempo.

---

## 14. Conclusioni: Conservativo o Ottimale?

**Risposta onesta: conservativo, ma appropriato al contesto.**

Le scelte fatte privilegiano:
- Stabilità del training su scala ridotta
- Riuso del feature engineering esistente (181 feature da XGBoost)
- Semplicità implementativa (debug facile, iterazione rapida)
- Compatibilità con 6GB VRAM

Per battere l'euristico non serve una rete sofisticatissima. Serve principalmente:
1. Abbastanza iterazioni (50-150)
2. Reward signal pulito ✓ (risolto con return normalization)
3. Esplorazione sufficiente ✓ (entropy_coef=0.05)
4. Curriculum learning ✓ (50% heuristic games)

Le ottimizzazioni architetturali (transformer, belief state, MCTS) sarebbero il passo successivo **dopo** aver dimostrato che PPO+MLP batte l'euristico su questa base.
