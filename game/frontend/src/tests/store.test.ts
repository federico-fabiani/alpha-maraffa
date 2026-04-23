/** Unit tests for the Zustand store's message-processing logic. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../services/api";
import useGameStore, { initialState } from "../state/gameStore";

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  useGameStore.setState(initialState);
});

describe("initial state", () => {
  it("starts on the home screen", () => {
    expect(useGameStore.getState().screen).toBe("home");
  });

  it("has no seat assigned", () => {
    expect(useGameStore.getState().mySeat).toBeNull();
  });
});

describe("setPlayerName", () => {
  it("updates playerName", () => {
    useGameStore.getState().setPlayerName("Alice");
    expect(useGameStore.getState().playerName).toBe("Alice");
  });
});

describe("_processMessage: joined", () => {
  it("sets mySeat, lobbyPlayers and navigates to lobby", () => {
    useGameStore.getState()._processMessage({
      type: "joined",
      data: {
        seat: 2,
        room_id: "TEST-ROOM-1",
        players: [{ seat: 2, name: "Alice", is_bot: false, team: 1 }],
      },
    });
    const { mySeat, screen, lobbyPlayers } = useGameStore.getState();
    expect(mySeat).toBe(2);
    expect(screen).toBe("lobby");
    expect(lobbyPlayers).toHaveLength(1);
    expect(lobbyPlayers[0].name).toBe("Alice");
  });
});

describe("_processMessage: player_joined", () => {
  it("updates lobbyPlayers list", () => {
    useGameStore.getState()._processMessage({
      type: "player_joined",
      data: {
        seat: 1,
        name: "Bob",
        players: [
          { seat: 0, name: "Alice", is_bot: false, team: 1 },
          { seat: 1, name: "Bob", is_bot: false, team: 2 },
        ],
      },
    });
    expect(useGameStore.getState().lobbyPlayers).toHaveLength(2);
  });
});

describe("_processMessage: game_started", () => {
  it("navigates to game screen", () => {
    useGameStore.getState()._processMessage({
      type: "game_started",
      data: { players: [] },
    });
    expect(useGameStore.getState().screen).toBe("game");
  });
});

describe("_processMessage: game_state", () => {
  it("updates all game fields", () => {
    useGameStore.getState()._processMessage({
      type: "game_state",
      data: {
        phase: "playing",
        round: 2,
        turn: 5,
        briscola: "bastoni",
        briscola_selector_seat: 1,
        current_player_seat: 0,
        table_cards: [{ seat: 1, card: { suit: "bastoni", rank: 3 } }],
        my_hand: [{ suit: "coppe", rank: 7, playable: true }],
        players: [],
        total_scores: { "1": 12, "2": 8 },
        round_scores: { "1": 3, "2": 2 },
        last_turn_winner: 1,
      },
    });
    const s = useGameStore.getState();
    expect(s.phase).toBe("playing");
    expect(s.briscola).toBe("bastoni");
    expect(s.currentPlayerSeat).toBe(0);
    expect(s.myHand).toHaveLength(1);
    expect(s.myHand[0].playable).toBe(true);
    expect(s.totalScores["1"]).toBe(12);
  });
});

describe("_processMessage: briscola_set", () => {
  it("sets briscola and announcement payload without redundant notification", () => {
    useGameStore.getState()._processMessage({
      type: "briscola_set",
      data: { suit: "denara", by_seat: 0, by_name: "Alice" },
    });
    const s = useGameStore.getState();
    expect(s.briscola).toBe("denara");
    expect(s.briscolaAnnouncement?.byName).toBe("Alice");
    expect(s.briscolaAnnouncement?.suit).toBe("denara");
    expect(s.briscolaAnnouncement?.eventId).toBeGreaterThan(0);
    expect(s.notification).toBeNull();
  });

  it("keeps briscolaAnnouncement after the next game_state update", () => {
    useGameStore.getState()._processMessage({
      type: "briscola_set",
      data: { suit: "spade", by_seat: 1, by_name: "Bob" },
    });

    const eventId = useGameStore.getState().briscolaAnnouncement?.eventId;

    useGameStore.getState()._processMessage({
      type: "game_state",
      data: {
        phase: "playing",
        round: 1,
        turn: 1,
        briscola: "spade",
        briscola_selector_seat: 1,
        current_player_seat: 1,
        table_cards: [],
        my_hand: [],
        players: [],
        total_scores: { "1": 0, "2": 0 },
        round_scores: { "1": 0, "2": 0 },
        last_turn_winner: null,
      },
    });

    const s = useGameStore.getState();
    expect(s.briscolaAnnouncement?.byName).toBe("Bob");
    expect(s.briscolaAnnouncement?.suit).toBe("spade");
    expect(s.briscolaAnnouncement?.eventId).toBe(eventId);
  });
});

describe("_processMessage: turn_result", () => {
  it("shows a notification with winner info and stores last trick cards", () => {
    useGameStore.getState()._processMessage({
      type: "turn_result",
      data: {
        winner_name: "Bob",
        winner_team: 2,
        points: 1.34,
        table: [
          { seat: 1, card: { suit: "denara", rank: 2 } },
          { seat: 2, card: { suit: "spade", rank: 3 } },
          { seat: 3, card: { suit: "coppe", rank: 4 } },
          { seat: 0, card: { suit: "bastoni", rank: 5 } },
        ],
      },
    });
    const { notification, lastTrickCards } = useGameStore.getState();
    expect(notification).not.toBeNull();
    expect(notification?.text).toContain("Bob");
    expect(lastTrickCards).toEqual([
      { seat: 1, card: { suit: "denara", rank: 2 } },
      { seat: 2, card: { suit: "spade", rank: 3 } },
      { seat: 3, card: { suit: "coppe", rank: 4 } },
      { seat: 0, card: { suit: "bastoni", rank: 5 } },
    ]);
  });
});

describe("_processMessage: card_played", () => {
  it("removes the played card from myHand when I am the one who played", () => {
    useGameStore.setState({
      mySeat: 2,
      myHand: [
        { suit: "coppe", rank: 7, playable: true },
        { suit: "spade", rank: 1, playable: true },
      ],
    });

    useGameStore.getState()._processMessage({
      type: "card_played",
      data: {
        seat: 2,
        card: { suit: "coppe", rank: 7 },
        table: [{ seat: 2, card: { suit: "coppe", rank: 7 } }],
      },
    });

    const s = useGameStore.getState();
    expect(s.myHand).toEqual([{ suit: "spade", rank: 1, playable: true }]);
    expect(s.tableCards).toHaveLength(1);
    expect(s.lastTrickCards).toEqual([]);
  });

  it("does not change myHand when another seat plays", () => {
    useGameStore.setState({
      mySeat: 2,
      myHand: [{ suit: "coppe", rank: 7, playable: true }],
    });

    useGameStore.getState()._processMessage({
      type: "card_played",
      data: {
        seat: 1,
        card: { suit: "denara", rank: 3 },
        table: [{ seat: 1, card: { suit: "denara", rank: 3 } }],
      },
    });

    const s = useGameStore.getState();
    expect(s.myHand).toEqual([{ suit: "coppe", rank: 7, playable: true }]);
    expect(s.tableCards).toHaveLength(1);
    expect(s.lastTrickCards).toEqual([]);
  });
});

describe("_processMessage: game_over", () => {
  it("sets gameOverData and navigates to gameover screen", () => {
    useGameStore.getState()._processMessage({
      type: "game_over",
      data: { winner_team: 1, scores: { "1": 44, "2": 28 } },
    });
    const { screen, gameOverData } = useGameStore.getState();
    expect(screen).toBe("gameover");
    expect(gameOverData?.winner_team).toBe(1);
    expect(gameOverData?.scores["1"]).toBe(44);
  });
});

describe("_processMessage: invalid session error", () => {
  it("clears the stale room, refreshes identity, and keeps the user unblocked", async () => {
    vi.spyOn(api, "loginPlayer").mockResolvedValue({
      uuid: "fresh-uuid",
      playerName: "Alice",
    });
    localStorage.setItem("mrf_uuid", "stale-uuid");
    localStorage.setItem("mrf_name", "Alice");
    localStorage.setItem("mrf_room", "ROOM-1");
    useGameStore.setState({
      ...initialState,
      uuid: "stale-uuid",
      playerName: "Alice",
      roomId: "ROOM-1",
      backendStatus: "ready",
    });

    useGameStore.getState()._processMessage({
      type: "error",
      data: { message: "Sessione non valida, ricarica la pagina" },
    });

    await Promise.resolve();
    await Promise.resolve();

    const state = useGameStore.getState();
    expect(api.loginPlayer).toHaveBeenCalledWith("Alice");
    expect(state.screen).toBe("home");
    expect(state.uuid).toBe("fresh-uuid");
    expect(state.roomId).toBe("");
    expect(state.playerName).toBe("Alice");
    expect(state.error).toBeNull();
    expect(localStorage.getItem("mrf_uuid")).toBe("fresh-uuid");
    expect(localStorage.getItem("mrf_room")).toBeNull();
    expect(localStorage.getItem("mrf_name")).toBe("Alice");
  });
});

describe("dismissNotification", () => {
  it("clears the notification", () => {
    useGameStore.setState({ notification: { text: "Test", duration: 1000 } });
    useGameStore.getState().dismissNotification();
    expect(useGameStore.getState().notification).toBeNull();
  });
});

describe("showNotification", () => {
  it("sets the notification", () => {
    useGameStore
      .getState()
      .showNotification({ text: "Mossa non valida", duration: 1200 });
    expect(useGameStore.getState().notification?.text).toBe("Mossa non valida");
  });
});
