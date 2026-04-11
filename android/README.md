# Marafone Beccaccino - Android App

App Android per giocare a Marafone Beccaccino con multiplayer via internet.

## Setup

### 1. Crea un progetto Firebase

1. Vai su [Firebase Console](https://console.firebase.google.com)
2. Crea un nuovo progetto
3. Aggiungi un'app Android con package name: `com.maraffa.beccaccino`
4. Scarica `google-services.json` e posizionalo in `app/`
5. Abilita **Realtime Database** (modalità test inizialmente)
6. Abilita **Authentication → Anonymous**

### 2. Configura le Security Rules

Nel pannello Firebase Realtime Database → Rules, copia il contenuto di `firebase-database.rules.json`.

### 3. Build

```bash
cd android
./gradlew assembleDebug
```

> **Nota**: serve il file `app/google-services.json` per compilare.

## Architettura

```
data/
  model/       → Card, Suit, Rank, Player, GameState, Trick, Declaration
  repository/  → Interfacce GameRepository, LobbyRepository
  remote/      → Implementazioni Firebase

domain/
  engine/      → CardDealer, TrickEvaluator, ScoreCalculator, MarafonaDetector
  usecase/     → CreateRoom, JoinRoom, DealCards, PlayCard, DeclareTrump, MakeDeclaration

ui/
  screen/home/   → HomeScreen + HomeViewModel
  screen/lobby/  → LobbyScreen + LobbyViewModel
  screen/game/   → GameScreen + GameViewModel + components
  screen/result/ → ResultScreen + ResultViewModel

di/  → Hilt modules (AppModule, FirebaseModule, RepositoryModule)
```

## Regole del Gioco

- **4 giocatori** in 2 squadre (posti 0+2 vs 1+3)
- **Gerarchia**: 3 > 2 > Asso > Re > Cavallo > Fante > 7 > 6 > 5 > 4
- **Briscola**: chi ha il 4 di Denari chiama il seme
- **Obbligo di risposta** al seme; se non si può, carta libera
- **Punteggi**: Asso=1, 2/3/figure=⅓, altri=0; ultima presa=+1
- **Marafona**: 3+2+Asso di briscola = +3 punti bonus
- **Vince** la prima squadra a raggiungere **41 punti**

## Multiplayer

Lo stato di gioco è sincronizzato via **Firebase Realtime Database**:
- `/rooms/{id}` → sala (codice 6 char)
- `/gameStates/{id}` → stato condiviso (visibile a tutti)
- `/privateHands/{id}/{uid}` → mano privata (solo il proprietario può leggere)

Il giocatore con `seatIndex=0` (host) distribuisce le carte e gestisce la transizione tra le mani.
