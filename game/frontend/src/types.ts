/** Shared TypeScript types for the Marafone frontend. */

export type Suit = 'bastoni' | 'denara' | 'spade' | 'coppe'

export type PingStatus = 'good' | 'ok' | 'bad' | 'offline'

export type Phase =
  | 'waiting'
  | 'briscola_selection'
  | 'playing'
  | 'turn_result'
  | 'round_end'
  | 'game_over'

export type Screen = 'home' | 'lobby' | 'game' | 'gameover'

export interface Card {
  suit: Suit
  rank: number
  playable?: boolean
}

export interface TableCard {
  seat: number
  card: Card
}

export interface Player {
  seat: number
  name: string
  team: 1 | 2
  cards_count: number
  is_you: boolean
  is_bot: boolean
  is_connected: boolean
}

export interface LobbyPlayer {
  seat: number
  name: string
  is_bot: boolean
  team: 1 | 2
}

export interface Notification {
  text: string
  subtitle?: string
  duration?: number
}

export interface BriscolaAnnouncement {
  byName: string
  suit: Suit
  eventId: number
}

export interface GameOverData {
  winner_team: 1 | 2
  scores: Record<string, number>
}
