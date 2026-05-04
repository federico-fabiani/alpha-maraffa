import { create } from "zustand";
import { APP_LAYOUT } from "../layout/layout";
import { createRoomRequest, loginPlayer } from "../services/api";
import { createGameConnectionController } from "../services/gameConnection";
import { sessionStorageService } from "../services/sessionStorage";
import type {
  Card,
  Declaration,
  LobbyPlayer,
  Phase,
  PingStatus,
  Player,
  Suit,
  TableCard,
} from "../types";
import type { GameMessage, GameStore, GameStoreState } from "./storeTypes";

let connectionController: ReturnType<typeof createGameConnectionController>;
const INVALID_SESSION_MESSAGE = "Sessione non valida, ricarica la pagina";
const MAX_PLAYER_NAME_LENGTH = APP_LAYOUT.lobby.seat.maxNameLength;
const NEW_ROUND_DELAY_MS = 1500;

export const initialState: GameStoreState = {
  connected: false,
  roomId: "",
  mySeat: null,
  playerName: "",
  uuid: "",
  isOwner: false,
  ownerSeat: null,
  screen: "home",
  displayedScreen: "home",
  screenTransitionPhase: "visible",
  backendStatus: "checking",
  lobbyPlayers: [],
  phase: "waiting",
  briscola: null,
  currentPlayerSeat: null,
  tableCards: [],
  lastTrickCards: [],
  myHand: [],
  players: [],
  totalScores: { "1": 0, "2": 0 },
  turnResultWinnerSeat: null,
  briscolaAnnouncement: null,
  currentDeclaration: null,
  notification: null,
  gameOverData: null,
  error: null,
  pingMs: null,
  pingStatus: "offline",
  turnDeadline: null,
  backgroundGeometry: null,
};

const useGameStore = create<GameStore>((set, get) => ({
  ...initialState,

  setPlayerName: (name) =>
    set({ playerName: name.trimStart().slice(0, MAX_PLAYER_NAME_LENGTH) }),

  setBackendStatus: (backendStatus) => set({ backendStatus }),

  setBackgroundGeometry: (backgroundGeometry) => set({ backgroundGeometry }),

  beginScreenTransition: () => set({ screenTransitionPhase: "fading-out" }),

  completeScreenTransition: () => {
    set((state) => ({
      displayedScreen: state.screen,
      screenTransitionPhase: "visible",
    }));
  },

  login: async () => {
    try {
      const { uuid, playerName } = await loginPlayer(get().playerName);
      set({ uuid, playerName });
      sessionStorageService.save(uuid, playerName);
    } catch {
      set({ error: "Impossibile raggiungere il server" });
    }
  },

  createRoom: async () => {
    try {
      const { roomId } = await createRoomRequest(get().playerName);
      set({ roomId });
      sessionStorageService.save(get().uuid, get().playerName, roomId);
      get()._connect(roomId);
    } catch (error) {
      set({
        error:
          error instanceof Error
            ? error.message
            : "Impossibile creare la stanza",
      });
    }
  },

  joinRoom: (roomId) => {
    const normalizedRoomId = roomId.trim();
    set({ roomId: normalizedRoomId });
    sessionStorageService.save(get().uuid, get().playerName, normalizedRoomId);
    get()._connect(normalizedRoomId);
  },

  startGame: () => {
    if (!get().isOwner) {
      return;
    }

    connectionController.send({ type: "start_game" });
  },

  swapSeats: (seatA, seatB) => {
    connectionController.send({
      type: "swap_seats",
      data: { seat_a: seatA, seat_b: seatB },
    });
  },

  kickPlayer: (seat) => {
    connectionController.send({ type: "kick", data: { seat } });
  },

  promotePlayer: (seat) => {
    connectionController.send({ type: "promote", data: { seat } });
  },

  selectBriscola: (suit) => {
    connectionController.send({ type: "select_briscola", data: { suit } });
  },

  playCard: (card, declaration = null) => {
    connectionController.send({
      type: "play_card",
      data: { card, declaration },
    });
  },

  forfeit: () => {
    connectionController.send({ type: "forfeit" });
  },

  restoreSession: () => {
    const savedSession = sessionStorageService.load();
    if (!savedSession) {
      const storedPlayerName = sessionStorageService.loadPlayerName();
      if (storedPlayerName) {
        set({ playerName: storedPlayerName });
      }
      void get().login();
      return;
    }

    set({
      uuid: savedSession.uuid,
      playerName: savedSession.playerName,
      roomId: savedSession.roomId,
    });
    get()._connect(savedSession.roomId);
  },

  showNotification: (notification) => set({ notification }),

  dismissNotification: () => set({ notification: null }),

  reset: () => {
    const { uuid, playerName, backendStatus, backgroundGeometry } = get();
    connectionController.disconnect({ intentional: true });
    sessionStorageService.clearRoom();
    set({
      ...initialState,
      uuid,
      playerName,
      backendStatus,
      backgroundGeometry,
      displayedScreen: "home",
      screenTransitionPhase: "visible",
    });
  },

  _connect: (roomId) => {
    connectionController.connect({
      roomId,
      playerName: get().playerName,
      uuid: get().uuid,
    });
  },

  _processMessage: (msg: GameMessage) => {
    const { type } = msg;
    const data = (msg.data ?? {}) as Record<string, unknown>;

    switch (type) {
      case "joined": {
        const { uuid, playerName, roomId } = get();
        sessionStorageService.save(uuid, playerName, roomId);
        set({
          mySeat: data.seat as number,
          lobbyPlayers: data.players as LobbyPlayer[],
          screen: "lobby",
          ownerSeat: data.owner_seat as number,
          isOwner: (data.seat as number) === (data.owner_seat as number),
        });
        break;
      }

      case "reconnected":
        set({ mySeat: data.seat as number, screen: "game" });
        break;

      case "player_joined": {
        const payload = data as { players: LobbyPlayer[]; owner_seat: number };
        set({ lobbyPlayers: payload.players, ownerSeat: payload.owner_seat });
        break;
      }

      case "game_started":
        set({
          screen: "game",
          lastTrickCards: [],
        });
        break;

      case "game_state": {
        const payload = data as {
          phase: Phase;
          briscola: Suit | null;
          current_player_seat: number | null;
          table_cards: TableCard[];
          my_hand: Card[];
          players: Player[];
          total_scores: Record<string, number>;
          current_declaration: Declaration;
          turn_deadline: number | null;
        };

        const applyGameState = () => {
          set((state) => ({
            phase: payload.phase,
            briscola: payload.briscola,
            currentPlayerSeat: payload.current_player_seat,
            tableCards: payload.table_cards,
            lastTrickCards:
              payload.phase === "briscola_selection"
                ? []
                : state.lastTrickCards,
            turnResultWinnerSeat: null,
            myHand: payload.my_hand,
            players: payload.players,
            totalScores: payload.total_scores,
            currentDeclaration: payload.current_declaration ?? null,
            turnDeadline: payload.turn_deadline ?? null,
          }));
        };

        const isNewRound =
          payload.phase === "briscola_selection" && get().phase === "playing";

        if (isNewRound) {
          window.setTimeout(applyGameState, NEW_ROUND_DELAY_MS);
        } else {
          applyGameState();
        }
        break;
      }

      case "briscola_set": {
        const selectedSuit = data.suit as Suit;
        set({
          briscola: selectedSuit,
          briscolaAnnouncement: {
            byName: data.by_name as string,
            suit: selectedSuit,
            eventId: connectionController.nextAnnouncementEventId(),
          },
          notification: null,
        });
        break;
      }

      case "maraffa": {
        const payload = data as {
          name: string;
          team: number;
          bonus: number;
          total_scores: Record<string, number>;
        };
        set({
          totalScores: payload.total_scores,
          notification: {
            text: `Maraffa! ${payload.name} ha 1, 2 e 3 di briscola`,
            subtitle: `Team ${payload.team} +${payload.bonus} punti bonus`,
            duration: 4000,
          },
        });
        break;
      }

      case "turn_result": {
        const trickCards = (
          (data.table as TableCard[] | undefined) ?? []
        ).slice(-4);
        set({
          turnResultWinnerSeat: data.winner_seat as number,
          lastTrickCards: trickCards,
          notification: {
            text: `Prende ${data.winner_name as string}`,
            duration: 2000,
          },
        });
        break;
      }

      case "round_end": {
        const roundScores = data.round_scores as Record<string, number>;
        const totalScores = data.total_scores as Record<string, number>;
        const players = get().players;
        const team1Players = players.filter((p) => p.team === 1);
        const team2Players = players.filter((p) => p.team === 2);
        const nameOrFallback = (
          p: (typeof players)[0] | undefined,
          fallback: string,
        ) => p?.name ?? fallback;
        set({
          tableCards: [],
          lastTrickCards: [],
          turnResultWinnerSeat: null,
          notification: {
            text: `Fine round ${data.round as number}`,
            duration: 3500,
            roundSummary: {
              team1: {
                names: [
                  nameOrFallback(team1Players[0], "—"),
                  nameOrFallback(team1Players[1], "—"),
                ],
                roundScore: roundScores["1"] ?? 0,
                totalScore: totalScores["1"] ?? 0,
              },
              team2: {
                names: [
                  nameOrFallback(team2Players[0], "—"),
                  nameOrFallback(team2Players[1], "—"),
                ],
                roundScore: roundScores["2"] ?? 0,
                totalScore: totalScores["2"] ?? 0,
              },
            },
          },
        });
        break;
      }

      case "game_over":
        set({
          gameOverData: {
            winner_team: data.winner_team as 1 | 2,
            scores: data.scores as Record<string, number>,
            ...(data.forfeit_by
              ? { forfeit_by: data.forfeit_by as string }
              : {}),
          },
          screen: "gameover",
          turnDeadline: null,
        });
        sessionStorageService.clearRoom();
        break;

      case "kicked": {
        const { uuid, playerName, backendStatus, backgroundGeometry } = get();
        connectionController.disconnect({ intentional: true });
        sessionStorageService.clearRoom();
        set({
          ...initialState,
          uuid,
          playerName,
          backendStatus,
          backgroundGeometry,
          displayedScreen: "home",
          screenTransitionPhase: "visible",
          error: (data.message as string) ?? "Sei stato espulso dalla stanza",
        });
        break;
      }

      case "seats_swapped": {
        const { seat_a, seat_b, owner_seat } = data as {
          seat_a: number;
          seat_b: number;
          players: LobbyPlayer[];
          owner_seat: number;
        };

        set((state) => {
          const nextMySeat =
            state.mySeat === seat_a
              ? seat_b
              : state.mySeat === seat_b
                ? seat_a
                : state.mySeat;

          return {
            lobbyPlayers: (data as { players: LobbyPlayer[] }).players,
            mySeat: nextMySeat,
            ownerSeat: owner_seat,
            isOwner: nextMySeat === owner_seat,
          };
        });
        break;
      }

      case "player_left": {
        const payload = data as { players: LobbyPlayer[]; owner_seat: number };
        set((state) => ({
          lobbyPlayers: payload.players,
          ownerSeat: payload.owner_seat,
          isOwner: state.mySeat === payload.owner_seat,
        }));
        break;
      }

      case "owner_changed": {
        const payload = data as { owner_seat: number; players: LobbyPlayer[] };
        set((state) => ({
          lobbyPlayers: payload.players,
          ownerSeat: payload.owner_seat,
          isOwner: state.mySeat === payload.owner_seat,
        }));
        break;
      }

      case "pong": {
        const latency = connectionController.getLatency();
        const pingStatus: PingStatus =
          latency < 150 ? "good" : latency < 500 ? "ok" : "bad";
        set({ pingMs: latency, pingStatus });
        break;
      }

      case "card_played": {
        const playedSeat = data.seat as number;
        const playedCard = data.card as Card;
        const declaration = (data.declaration ?? null) as Declaration;
        const declarationText: Record<string, string> = {
          busso: "bussa!",
          striscio: "striscia.",
          volo: "vola!",
        };

        set((state) => ({
          tableCards: data.table as TableCard[],
          myHand:
            state.mySeat === playedSeat
              ? state.myHand.filter(
                  (card) =>
                    !(
                      card.suit === playedCard.suit &&
                      card.rank === playedCard.rank
                    ),
                )
              : state.myHand,
          ...(declaration
            ? {
                currentDeclaration: declaration,
                notification: {
                  text: `${data.name as string} ${declarationText[declaration] ?? declaration}`,
                  duration: 2000,
                },
              }
            : {}),
        }));
        break;
      }

      case "player_disconnected": {
        const disconnectedSeat = data.seat as number;
        set((state) => ({
          players: state.players.map((player) =>
            player.seat === disconnectedSeat
              ? { ...player, is_connected: false }
              : player,
          ),
        }));
        break;
      }

      case "player_timeout": {
        const payload = data as {
          name: string;
          consecutive: number;
          total: number;
        };
        const remaining = 3 - payload.consecutive;
        set({
          turnDeadline: null,
          notification: {
            text: `${payload.name} non ha giocato in tempo`,
            subtitle:
              remaining > 0
                ? `Ancora ${remaining} pausa${remaining > 1 ? "" : ""} prima dell'espulsione`
                : undefined,
            duration: 3000,
          },
        });
        break;
      }

      case "error": {
        const message = data.message as string;

        if (message === INVALID_SESSION_MESSAGE) {
          const { playerName, backendStatus, backgroundGeometry } = get();
          connectionController.disconnect({ intentional: true });
          sessionStorageService.clearSession();
          set({
            ...initialState,
            playerName,
            backendStatus,
            backgroundGeometry,
            displayedScreen: "home",
            screenTransitionPhase: "visible",
          });
          void get().login();
          break;
        }

        set({
          error:
            message === "Stanza non trovata" ? "Tavolo non trovato" : message,
        });
        break;
      }
    }
  },
}));

connectionController = createGameConnectionController({
  onStateChange: (patch) => {
    useGameStore.setState(patch);
  },
  onMessage: (message) => {
    useGameStore.getState()._processMessage(message);
  },
  getReconnectContext: () => {
    const state = useGameStore.getState();
    return {
      screen: state.screen,
      roomId: state.roomId,
    };
  },
});

export default useGameStore;
