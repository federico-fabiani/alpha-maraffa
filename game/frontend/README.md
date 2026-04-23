# marafone-frontend

React 19 + TypeScript + Tailwind 4 client for **Marafone**, the Italian 4-player card game.

## Quick start

Make sure the backend is running first (`cd game/backend && uv run uvicorn aimaraffa.api:app --reload`), then:

```bash
npm install   # first time only
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).  
API calls and WebSocket connections are proxied automatically to `localhost:8000`.

## Scripts

| Command           | Description                                   |
| ----------------- | --------------------------------------------- |
| `npm run dev`     | Start the Vite dev server with hot reload     |
| `npm run build`   | Type-check and build for production (`dist/`) |
| `npm run preview` | Serve the production build locally            |
| `npm run test`    | Run unit and component tests with Vitest      |
| `npm run test:ui` | Open the Vitest browser UI                    |

## Structure

```
src/
├── App.tsx                # App shell + screen switching
├── index.css              # Theme, animations, and layout-backed CSS rules
├── types.ts               # Shared TypeScript interfaces
├── components/
│   ├── Card.tsx           # Card face + CardBack
│   ├── PlayerArea.tsx     # Opponent display (name + face-down cards)
│   ├── TableArea.tsx      # Centre table with played cards
│   ├── BriscolaModal.tsx  # Trump suit selection overlay
│   ├── BriscolaSuitGif.tsx# Briscola intro playback
│   ├── ConnectionStatus.tsx
│   └── Notification.tsx   # Auto-dismissing toast
├── hooks/
│   ├── useAppBootstrap.ts     # Backend readiness polling
│   ├── useBriscolaIntro.ts    # Briscola intro flow
│   ├── useGameScreenController.ts
│   ├── useGameStageLayout.ts  # Stage geometry -> CSS variables
│   └── useTurnCountdown.ts    # Turn timer state
├── layout/
│   └── layout.ts          # Centralized layout authority
├── services/
│   ├── api.ts             # REST calls
│   ├── gameConnection.ts  # WebSocket lifecycle
│   └── sessionStorage.ts  # Session persistence
├── screens/
│   ├── HomeScreen.tsx     # Name input + create/join room
│   ├── LobbyScreen.tsx    # Waiting room with seat grid
│   ├── GameScreen.tsx     # Main game table
│   └── GameOverScreen.tsx # Result screen
├── state/
│   ├── gameStore.ts       # Centralized Zustand state model
│   └── storeTypes.ts      # Store contracts
└── tests/
    ├── store.test.ts      # 11 tests — Zustand state transitions
    └── Card.test.tsx      # 8 tests  — Card rendering and interaction
```

## Testing strategy

**Unit/component tests (Vitest + React Testing Library)** cover:

- All WebSocket message handlers (`_processMessage`) — verifies every state transition
- `Card` rendering — rank label, suit symbol, playable state, click handling

**Full game flow** is tested manually: start both backend and frontend, open two browser tabs, create a room in one and join with the other, then play through a game. The backend test suite (`game/backend`) already covers the complete game loop with bots end-to-end.
