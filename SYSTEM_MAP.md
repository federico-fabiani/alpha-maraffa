# SYSTEM_MAP

Frontend contract for `game/frontend`.

## 2.1 State Model

### Central state model

Authority: `game/frontend/src/state/gameStore.ts`

- `connected`: websocket connectivity flag.
- `roomId`: active room code.
- `mySeat`: current player seat.
- `playerName`: current player name.
- `uuid`: player identity token.
- `isOwner`: owner flag for the current room.
- `ownerSeat`: owner seat index.
- `screen`: canonical target screen.
- `displayedScreen`: rendered screen during transitions.
- `screenTransitionPhase`: app-shell screen fade phase.
- `backendStatus`: backend bootstrap readiness.
- `lobbyPlayers`: lobby roster.
- `phase`: server-driven game phase.
- `briscola`: active briscola suit.
- `currentPlayerSeat`: seat currently on turn.
- `tableCards`: live cards on the table.
- `lastTrickCards`: snapshot of the last completed trick.
- `myHand`: local player hand.
- `players`: full player state list.
- `totalScores`: match totals by team.
- `turnResultWinnerSeat`: winner seat used for collection animation.
- `briscolaAnnouncement`: announcement payload for the intro sequence.
- `currentDeclaration`: current declaration for the active trick.
- `notification`: active toast payload.
- `gameOverData`: end-of-match payload.
- `error`: current blocking error.
- `pingMs`: latest measured latency.
- `pingStatus`: latency bucket.
- `turnDeadline`: server deadline for the active turn.

### Allowed local UI state

Authority: hook-local or component-local view state only.

- `HomeScreen.selectedOption`: keyboard/hover menu selection.
- `HomeScreen.showJoinPanel`: join-panel toggle.
- `HomeScreen.roomCode`: unsubmitted room-code input.
- `LobbyScreen.swapPendingSeat`: pending swap interaction.
- `LobbyScreen.copied`: clipboard feedback toggle.
- `useGameScreenController.showForfeitConfirm`: forfeit dialog toggle.
- `useGameScreenController.pendingDeclaration`: unsubmitted declaration choice.
- `useGameScreenController.drag`: drag interaction payload.
- `useBriscolaIntro.briscolaIntro`: intro animation finite-state machine.
- `useBriscolaIntro.briscolaGifMeta`: replay token and suit for the GIF overlay.
- `useTurnCountdown.now`: timer tick source used to derive remaining seconds.
- `TableArea.collecting`: last-trick collection animation payload.
- `BriscolaSuitGif.fallbackToImg`: GIF decode fallback flag.

## 2.2 Component Tree

### App shell

- `App`
  props: none
  state read: `displayedScreen`, `screenTransitionPhase`, `backendStatus`
  actions triggered: `restoreSession`, `setBackendStatus`, `beginScreenTransition`, `completeScreenTransition`
  children: `HomeScreen | LobbyScreen | GameScreen | GameOverScreen`, `ConnectionStatus`

### Home flow

- `HomeScreen`
  props: none
  state read: `playerName`, `error`; local `selectedOption`, `showJoinPanel`, `roomCode`
  actions triggered: `setPlayerName`, `createRoom`, `joinRoom`
  children: none

### Lobby flow

- `LobbyScreen`
  props: none
  state read: `roomId`, `mySeat`, `isOwner`, `ownerSeat`, `lobbyPlayers`; local `swapPendingSeat`, `copied`
  actions triggered: `startGame`, `swapSeats`, `kickPlayer`, `promotePlayer`, `reset`
  children: none

### Game flow

- `GameScreen`
  props: none
  state read: `mySeat`, `players`, `myHand`, `phase`, `briscola`, `briscolaAnnouncement`, `currentPlayerSeat`, `tableCards`, `turnResultWinnerSeat`, `lastTrickCards`, `totalScores`, `notification`, `currentDeclaration`, `turnDeadline`; local `showForfeitConfirm`, `pendingDeclaration`, `drag`, `briscolaIntro`, `briscolaGifMeta`, `now`
  actions triggered: `playCard`, `selectBriscola`, `showNotification`, `dismissNotification`, `forfeit`
  children: `PlayerArea` x3, `TableArea`, `BriscolaSuitGif`, `BriscolaModal`, `Notification`, `Card`

- `PlayerArea`
  props: `player`, `isActive`, `position`, `declaration`, `showCards`
  state read: none
  actions triggered: none
  children: `CardBack`

- `TableArea`
  props: `tableCards`, `mySeat`, `winnerSeat`, `briscolaSuit`
  state read: local `collecting`
  actions triggered: none
  children: `Card`

- `BriscolaSuitGif`
  props: `suit`, `replayToken`, `onPlaybackComplete`, `className`, `style`
  state read: local `fallbackToImg`
  actions triggered: `onPlaybackComplete`
  children: none

- `BriscolaModal`
  props: `onSelect`, `selectorName`
  state read: none
  actions triggered: `onSelect`
  children: none

- `Notification`
  props: `notification`, `onDismiss`
  state read: none
  actions triggered: `onDismiss`
  children: none

- `ConnectionStatus`
  props: none
  state read: `connected`, `pingMs`, `pingStatus`
  actions triggered: none
  children: none

- `Card`
  props: `card`, `size`, `briscolaSuit`, `onClick`, `className`, `style`
  state read: none
  actions triggered: `onClick`
  children: none

- `CardBack`
  props: `size`, `className`, `style`
  state read: none
  actions triggered: none
  children: none

### Game over flow

- `GameOverScreen`
  props: none
  state read: `gameOverData`, `mySeat`
  actions triggered: `reset`
  children: none

## 2.3 State Flow

### Central state flow

`connected`:
read by: [`ConnectionStatus`]
written by: [`gameConnection.onStateChange`]

`roomId`:
read by: [`LobbyScreen`, `gameConnection.getReconnectContext`]
written by: [`createRoom`, `joinRoom`, `restoreSession`]

`mySeat`:
read by: [`LobbyScreen`, `GameScreen`, `GameOverScreen`]
written by: [`_processMessage.joined`, `_processMessage.reconnected`, `_processMessage.seats_swapped`]

`playerName`:
read by: [`HomeScreen`, `login`, `createRoom`, `_connect`, `restoreSession`]
written by: [`setPlayerName`, `login`, `restoreSession`, `reset`, `_processMessage.kicked`]

`uuid`:
read by: [`login`, `_connect`, `restoreSession`]
written by: [`login`, `restoreSession`, `reset`, `_processMessage.kicked`]

`isOwner`:
read by: [`LobbyScreen`]
written by: [`_processMessage.joined`, `_processMessage.seats_swapped`, `_processMessage.player_left`, `_processMessage.owner_changed`]

`ownerSeat`:
read by: [`LobbyScreen`]
written by: [`_processMessage.joined`, `_processMessage.player_joined`, `_processMessage.seats_swapped`, `_processMessage.player_left`, `_processMessage.owner_changed`]

`screen`:
read by: [`App`, `gameConnection.getReconnectContext`]
written by: [`_processMessage.joined`, `_processMessage.reconnected`, `_processMessage.game_started`, `_processMessage.game_over`, `reset`, `_processMessage.kicked`]

`displayedScreen`:
read by: [`App`]
written by: [`completeScreenTransition`, `reset`, `_processMessage.kicked`]

`screenTransitionPhase`:
read by: [`App`]
written by: [`beginScreenTransition`, `completeScreenTransition`, `reset`, `_processMessage.kicked`]

`backendStatus`:
read by: [`App`, `reset`, `_processMessage.kicked`]
written by: [`useAppBootstrap -> setBackendStatus`]

`lobbyPlayers`:
read by: [`LobbyScreen`]
written by: [`_processMessage.joined`, `_processMessage.player_joined`, `_processMessage.game_started`, `_processMessage.seats_swapped`, `_processMessage.player_left`, `_processMessage.owner_changed`]

`phase`:
read by: [`GameScreen`, `useBriscolaIntro`]
written by: [`_processMessage.game_state`]

`briscola`:
read by: [`GameScreen`, `TableArea`, `Card`, `useBriscolaIntro`]
written by: [`_processMessage.game_state`, `_processMessage.briscola_set`]

`currentPlayerSeat`:
read by: [`GameScreen`]
written by: [`_processMessage.game_state`]

`tableCards`:
read by: [`GameScreen`, `TableArea`]
written by: [`_processMessage.game_state`, `_processMessage.card_played`]

`lastTrickCards`:
read by: [`GameScreen`]
written by: [`_processMessage.game_started`, `_processMessage.game_state`, `_processMessage.turn_result`]

`myHand`:
read by: [`GameScreen`]
written by: [`_processMessage.game_state`, `_processMessage.card_played`]

`players`:
read by: [`GameScreen`]
written by: [`_processMessage.game_state`, `_processMessage.player_disconnected`]

`totalScores`:
read by: [`GameScreen`]
written by: [`_processMessage.game_state`, `_processMessage.maraffa`]

`turnResultWinnerSeat`:
read by: [`GameScreen`, `TableArea`]
written by: [`_processMessage.game_state`, `_processMessage.turn_result`]

`briscolaAnnouncement`:
read by: [`GameScreen`, `useBriscolaIntro`]
written by: [`_processMessage.briscola_set`]

`currentDeclaration`:
read by: [`GameScreen`, `PlayerArea`]
written by: [`_processMessage.game_state`, `_processMessage.card_played`]

`notification`:
read by: [`GameScreen`, `Notification`]
written by: [`showNotification`, `dismissNotification`, `_processMessage.briscola_set`, `_processMessage.maraffa`, `_processMessage.turn_result`, `_processMessage.round_end`, `_processMessage.card_played`, `_processMessage.player_timeout`]

`gameOverData`:
read by: [`GameOverScreen`]
written by: [`_processMessage.game_over`]

`error`:
read by: [`HomeScreen`]
written by: [`login`, `createRoom`, `gameConnection.onStateChange`, `_processMessage.kicked`, `_processMessage.error`]

`pingMs`:
read by: [`ConnectionStatus`]
written by: [`gameConnection.onStateChange`, `_processMessage.pong`]

`pingStatus`:
read by: [`ConnectionStatus`]
written by: [`gameConnection.onStateChange`, `_processMessage.pong`]

`turnDeadline`:
read by: [`GameScreen`, `useTurnCountdown`]
written by: [`_processMessage.game_state`, `_processMessage.game_over`, `_processMessage.player_timeout`]

### Local state flow

`HomeScreen.selectedOption`:
read by: [`HomeScreen`]
written by: [`HomeScreen keyboard handler`, `HomeScreen onMouseEnter`]

`HomeScreen.showJoinPanel`:
read by: [`HomeScreen`]
written by: [`HomeScreen.handleActivateOption`, `HomeScreen.handleCloseJoinPanel`]

`HomeScreen.roomCode`:
read by: [`HomeScreen`, `HomeScreen.handleJoinRoom`]
written by: [`HomeScreen room-code input`, `HomeScreen.handleCloseJoinPanel`]

`LobbyScreen.swapPendingSeat`:
read by: [`LobbyScreen`]
written by: [`LobbyScreen.handleSeatClick`]

`LobbyScreen.copied`:
read by: [`LobbyScreen`]
written by: [`LobbyScreen.handleCopyRoomId`]

`useGameScreenController.showForfeitConfirm`:
read by: [`GameScreen`]
written by: [`useGameScreenController.handleOpenForfeitConfirm`, `useGameScreenController.handleCancelForfeit`, `useGameScreenController.handleConfirmForfeit`]

`useGameScreenController.pendingDeclaration`:
read by: [`GameScreen`]
written by: [`useGameScreenController.handleToggleDeclaration`, `useGameScreenController.handleCardClick`, `useGameScreenController.handlePointerUp`]

`useGameScreenController.drag`:
read by: [`GameScreen`]
written by: [`useGameScreenController.handleCardPointerDown`, `useGameScreenController.handlePointerMove`, `useGameScreenController.handlePointerUp`, `useGameScreenController.handlePointerCancel`]

`useBriscolaIntro.briscolaIntro`:
read by: [`GameScreen`]
written by: [`useBriscolaIntro effect on briscolaAnnouncement`, `useBriscolaIntro effect on briscola reset`, `useBriscolaIntro fallback effect`, `useBriscolaIntro.handleBriscolaGifPlaybackComplete`]

`useBriscolaIntro.briscolaGifMeta`:
read by: [`GameScreen`]
written by: [`useBriscolaIntro effect on briscolaAnnouncement`, `useBriscolaIntro effect on briscola reset`, `useBriscolaIntro fallback effect`]

`useTurnCountdown.now`:
read by: [`useTurnCountdown`]
written by: [`useTurnCountdown interval effect`]

`TableArea.collecting`:
read by: [`TableArea`]
written by: [`TableArea table clear effect`]

`BriscolaSuitGif.fallbackToImg`:
read by: [`BriscolaSuitGif`]
written by: [`BriscolaSuitGif asset decode effect`]

## 2.4 Layout Authority

Authority: `game/frontend/src/layout/layout.ts`

- `APP_LAYOUT` is the only source of truth for shell insets, playing-area bounds, card sizes, lobby metrics, modal widths, drag/drop sizes, and game-over widths.
- `layoutCssVariables` bridges layout values into `game/frontend/src/index.css` for the CSS rules that still need shared dimensions.
- `GAME_SEAT_STYLES`, `APP_SHELL_LAYOUT_STYLES`, `getCardSizeStyle`, `getGameTableSlotStyle`, `getLastTrickSlotStyle`, `getCollectVector`, `createTurnCountdownFillStyle`, `createBriscolaGifStyle`, `createGameDropZoneStyle`, and `createDragGhostStyle` are the only approved layout helpers for React components.

## 2.5 Invariants

- `connected === false` implies `pingStatus === 'offline'`. Connection state transitions must maintain this pair together.
- `displayedScreen` may lag `screen` only while `screenTransitionPhase === 'fading-out'`; once the phase returns to `visible`, `displayedScreen === screen` must hold.
- `GameScreen` may call `playCard` only when `isMyTurn === true`, and `isMyTurn` must be false for the entire briscola intro sequence.
- All table-card positioning, collection vectors, card sizes, and lobby shell dimensions originate from `APP_LAYOUT`; component files may consume layout helpers but must not define competing dimension constants.
