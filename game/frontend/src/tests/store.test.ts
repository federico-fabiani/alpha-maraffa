/** Unit tests for the Zustand store's message-processing logic. */

import { beforeEach, describe, expect, it } from 'vitest'
import useGameStore, { initialState } from '../store'

beforeEach(() => {
  useGameStore.setState(initialState)
})

describe('initial state', () => {
  it('starts on the home screen', () => {
    expect(useGameStore.getState().screen).toBe('home')
  })

  it('has no seat assigned', () => {
    expect(useGameStore.getState().mySeat).toBeNull()
  })
})

describe('setPlayerName', () => {
  it('updates playerName', () => {
    useGameStore.getState().setPlayerName('Alice')
    expect(useGameStore.getState().playerName).toBe('Alice')
  })
})

describe('_processMessage: joined', () => {
  it('sets mySeat, lobbyPlayers and navigates to lobby', () => {
    useGameStore.getState()._processMessage({
      type: 'joined',
      data: {
        seat: 2,
        room_id: 'TEST-ROOM-1',
        players: [{ seat: 2, name: 'Alice', is_bot: false, team: 1 }],
      },
    })
    const { mySeat, screen, lobbyPlayers } = useGameStore.getState()
    expect(mySeat).toBe(2)
    expect(screen).toBe('lobby')
    expect(lobbyPlayers).toHaveLength(1)
    expect(lobbyPlayers[0].name).toBe('Alice')
  })
})

describe('_processMessage: player_joined', () => {
  it('updates lobbyPlayers list', () => {
    useGameStore.getState()._processMessage({
      type: 'player_joined',
      data: {
        seat: 1,
        name: 'Bob',
        players: [
          { seat: 0, name: 'Alice', is_bot: false, team: 1 },
          { seat: 1, name: 'Bob',   is_bot: false, team: 2 },
        ],
      },
    })
    expect(useGameStore.getState().lobbyPlayers).toHaveLength(2)
  })
})

describe('_processMessage: game_started', () => {
  it('navigates to game screen', () => {
    useGameStore.getState()._processMessage({
      type: 'game_started',
      data: { players: [] },
    })
    expect(useGameStore.getState().screen).toBe('game')
  })
})

describe('_processMessage: game_state', () => {
  it('updates all game fields', () => {
    useGameStore.getState()._processMessage({
      type: 'game_state',
      data: {
        phase: 'playing',
        round: 2,
        turn: 5,
        briscola: 'bastoni',
        briscola_selector_seat: 1,
        current_player_seat: 0,
        table_cards: [{ seat: 1, card: { suit: 'bastoni', rank: 3 } }],
        my_hand: [{ suit: 'coppe', rank: 7, playable: true }],
        players: [],
        total_scores: { '1': 12, '2': 8 },
        round_scores: { '1': 3, '2': 2 },
        last_turn_winner: 1,
      },
    })
    const s = useGameStore.getState()
    expect(s.phase).toBe('playing')
    expect(s.round).toBe(2)
    expect(s.turn).toBe(5)
    expect(s.briscola).toBe('bastoni')
    expect(s.currentPlayerSeat).toBe(0)
    expect(s.myHand).toHaveLength(1)
    expect(s.myHand[0].playable).toBe(true)
    expect(s.totalScores['1']).toBe(12)
  })
})

describe('_processMessage: briscola_set', () => {
  it('sets briscola and shows a notification', () => {
    useGameStore.getState()._processMessage({
      type: 'briscola_set',
      data: { suit: 'denara', by_seat: 0, by_name: 'Alice' },
    })
    const s = useGameStore.getState()
    expect(s.briscola).toBe('denara')
    expect(s.notification).not.toBeNull()
    expect(s.notification?.text).toContain('DENARA')
  })
})

describe('_processMessage: turn_result', () => {
  it('shows a notification with winner info', () => {
    useGameStore.getState()._processMessage({
      type: 'turn_result',
      data: { winner_name: 'Bob', winner_team: 2, points: 1.34 },
    })
    const { notification } = useGameStore.getState()
    expect(notification).not.toBeNull()
    expect(notification?.text).toContain('Bob')
  })
})

describe('_processMessage: game_over', () => {
  it('sets gameOverData and navigates to gameover screen', () => {
    useGameStore.getState()._processMessage({
      type: 'game_over',
      data: { winner_team: 1, scores: { '1': 44, '2': 28 } },
    })
    const { screen, gameOverData } = useGameStore.getState()
    expect(screen).toBe('gameover')
    expect(gameOverData?.winner_team).toBe(1)
    expect(gameOverData?.scores['1']).toBe(44)
  })
})

describe('dismissNotification', () => {
  it('clears the notification', () => {
    useGameStore.setState({ notification: { text: 'Test', duration: 1000 } })
    useGameStore.getState().dismissNotification()
    expect(useGameStore.getState().notification).toBeNull()
  })
})
