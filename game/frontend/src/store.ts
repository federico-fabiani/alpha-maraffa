/** Zustand store: all app state and WebSocket communication. */

import { create } from 'zustand'
import type {
  Card,
  GameOverData,
  LobbyPlayer,
  Notification,
  Phase,
  Player,
  Screen,
  Suit,
  TableCard,
} from './types'

// ── Types ───────────────────────────────────────────────────────────────────��──

interface State {
  // Connection
  ws: WebSocket | null
  connected: boolean
  roomId: string
  mySeat: number | null
  playerName: string
  // Navigation
  screen: Screen
  // Lobby
  lobbyPlayers: LobbyPlayer[]
  // Game
  phase: Phase
  round: number
  turn: number
  briscola: Suit | null
  briscolaSelectorSeat: number | null
  currentPlayerSeat: number | null
  tableCards: TableCard[]
  myHand: Card[]
  players: Player[]
  totalScores: Record<string, number>
  roundScores: Record<string, number>
  lastTurnWinner: number | null
  // UI
  notification: Notification | null
  gameOverData: GameOverData | null
  error: string | null
}

interface Actions {
  setPlayerName: (name: string) => void
  createRoom: () => Promise<void>
  joinRoom: (roomId: string) => void
  startGame: () => void
  selectBriscola: (suit: Suit) => void
  playCard: (card: Card) => void
  dismissNotification: () => void
  reset: () => void
  // Exported for unit testing
  _connect: (roomId: string) => void
  _processMessage: (msg: { type: string; data?: unknown }) => void
}

// ── Initial state (exported so tests can reset cleanly) ────────────────────────

export const initialState: State = {
  ws: null,
  connected: false,
  roomId: '',
  mySeat: null,
  playerName: '',
  screen: 'home',
  lobbyPlayers: [],
  phase: 'waiting',
  round: 0,
  turn: 0,
  briscola: null,
  briscolaSelectorSeat: null,
  currentPlayerSeat: null,
  tableCards: [],
  myHand: [],
  players: [],
  totalScores: { '1': 0, '2': 0 },
  roundScores: { '1': 0, '2': 0 },
  lastTurnWinner: null,
  notification: null,
  gameOverData: null,
  error: null,
}

// ── Store ──────────────────────────────────────────────────────────────────────

const useGameStore = create<State & Actions>((set, get) => ({
  ...initialState,

  setPlayerName: (name) => set({ playerName: name }),

  createRoom: async () => {
    const { playerName } = get()
    try {
      const res = await fetch('/api/rooms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ player_name: playerName }),
      })
      const { room_id } = (await res.json()) as { room_id: string }
      set({ roomId: room_id })
      get()._connect(room_id)
    } catch {
      set({ error: 'Impossibile creare la stanza' })
    }
  },

  joinRoom: (roomId) => {
    set({ roomId })
    get()._connect(roomId)
  },

  _connect: (roomId) => {
    const { playerName } = get()
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${proto}//${window.location.host}/ws/${roomId}?player_name=${encodeURIComponent(playerName)}`
    const ws = new WebSocket(url)

    ws.onopen = () => set({ connected: true })
    ws.onmessage = (e) => get()._processMessage(JSON.parse(e.data as string) as { type: string; data?: unknown })
    ws.onclose = () => set({ connected: false })
    ws.onerror = () => set({ error: 'Errore di connessione' })

    set({ ws })
  },

  startGame: () => {
    get().ws?.send(JSON.stringify({ type: 'start_game' }))
  },

  selectBriscola: (suit) => {
    get().ws?.send(JSON.stringify({ type: 'select_briscola', data: { suit } }))
  },

  playCard: (card) => {
    get().ws?.send(JSON.stringify({ type: 'play_card', data: { card } }))
  },

  dismissNotification: () => set({ notification: null }),

  reset: () => {
    get().ws?.close()
    set(initialState)
  },

  _processMessage: (msg) => {
    const { type } = msg
    const data = (msg.data ?? {}) as Record<string, unknown>

    switch (type) {
      case 'joined':
        set({
          mySeat: data.seat as number,
          lobbyPlayers: data.players as LobbyPlayer[],
          screen: 'lobby',
        })
        break

      case 'reconnected':
        set({ mySeat: data.seat as number, screen: 'game' })
        break

      case 'player_joined':
        set({ lobbyPlayers: data.players as LobbyPlayer[] })
        break

      case 'game_started':
        set({ screen: 'game', lobbyPlayers: data.players as LobbyPlayer[] })
        break

      case 'game_state': {
        const d = data as {
          phase: Phase
          round: number
          turn: number
          briscola: Suit | null
          briscola_selector_seat: number | null
          current_player_seat: number | null
          table_cards: TableCard[]
          my_hand: Card[]
          players: Player[]
          total_scores: Record<string, number>
          round_scores: Record<string, number>
          last_turn_winner: number | null
        }
        set({
          phase: d.phase,
          round: d.round,
          turn: d.turn,
          briscola: d.briscola,
          briscolaSelectorSeat: d.briscola_selector_seat,
          currentPlayerSeat: d.current_player_seat,
          tableCards: d.table_cards,
          myHand: d.my_hand,
          players: d.players,
          totalScores: d.total_scores,
          roundScores: d.round_scores,
          lastTurnWinner: d.last_turn_winner,
        })
        break
      }

      case 'briscola_set':
        set({
          briscola: data.suit as Suit,
          notification: {
            text: `Briscola: ${(data.suit as string).toUpperCase()}`,
            subtitle: `Scelta da ${data.by_name as string}`,
            duration: 3000,
          },
        })
        break

      case 'turn_result':
        set({
          notification: {
            text: `Prende ${data.winner_name as string}`,
            subtitle: `Team ${data.winner_team as number} +${data.points as number} pt`,
            duration: 2000,
          },
        })
        break

      case 'round_end': {
        const rs = data.round_scores as Record<string, number>
        set({
          notification: {
            text: `Fine round ${data.round as number}`,
            subtitle: `Team 1: ${rs['1']} — Team 2: ${rs['2']}`,
            duration: 3500,
          },
        })
        break
      }

      case 'game_over':
        set({
          gameOverData: {
            winner_team: data.winner_team as 1 | 2,
            scores: data.scores as Record<string, number>,
          },
          screen: 'gameover',
        })
        break

      case 'error':
        set({ error: data.message as string })
        break
    }
  },
}))

export default useGameStore
