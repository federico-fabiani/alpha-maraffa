import type {
  BriscolaAnnouncement,
  Card,
  Declaration,
  GameOverData,
  LobbyPlayer,
  Notification,
  Phase,
  PingStatus,
  Player,
  Screen,
  Suit,
  TableCard,
} from "../types";

export type BackendStatus = "checking" | "ready";

export type ScreenTransitionPhase = "visible" | "fading-out";

export interface GameMessage {
  type: string;
  data?: unknown;
}

export interface GameStoreState {
  connected: boolean;
  roomId: string;
  mySeat: number | null;
  playerName: string;
  uuid: string;
  isOwner: boolean;
  ownerSeat: number | null;
  screen: Screen;
  displayedScreen: Screen;
  screenTransitionPhase: ScreenTransitionPhase;
  backendStatus: BackendStatus;
  lobbyPlayers: LobbyPlayer[];
  phase: Phase;
  briscola: Suit | null;
  currentPlayerSeat: number | null;
  tableCards: TableCard[];
  lastTrickCards: TableCard[];
  myHand: Card[];
  players: Player[];
  totalScores: Record<string, number>;
  turnResultWinnerSeat: number | null;
  briscolaAnnouncement: BriscolaAnnouncement | null;
  currentDeclaration: Declaration;
  notification: Notification | null;
  gameOverData: GameOverData | null;
  error: string | null;
  pingMs: number | null;
  pingStatus: PingStatus;
  turnDeadline: number | null;
}

export interface GameStoreActions {
  setPlayerName: (name: string) => void;
  setBackendStatus: (status: BackendStatus) => void;
  beginScreenTransition: () => void;
  completeScreenTransition: () => void;
  login: () => Promise<void>;
  createRoom: () => Promise<void>;
  joinRoom: (roomId: string) => void;
  startGame: () => void;
  swapSeats: (seatA: number, seatB: number) => void;
  kickPlayer: (seat: number) => void;
  promotePlayer: (seat: number) => void;
  selectBriscola: (suit: Suit) => void;
  playCard: (card: Card, declaration?: Declaration) => void;
  forfeit: () => void;
  restoreSession: () => void;
  showNotification: (notification: Notification) => void;
  dismissNotification: () => void;
  reset: () => void;
  _connect: (roomId: string) => void;
  _processMessage: (msg: GameMessage) => void;
}

export type GameStore = GameStoreState & GameStoreActions;
