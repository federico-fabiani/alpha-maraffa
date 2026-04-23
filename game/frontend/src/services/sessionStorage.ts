export interface StoredSession {
  uuid: string
  playerName: string
  roomId: string
}

const STORAGE_KEYS = {
  uuid: 'mrf_uuid',
  playerName: 'mrf_name',
  roomId: 'mrf_room',
} as const

export const sessionStorageService = {
  save(uuid: string, playerName: string, roomId?: string) {
    try {
      localStorage.setItem(STORAGE_KEYS.uuid, uuid)
      localStorage.setItem(STORAGE_KEYS.playerName, playerName)
      if (roomId) {
        localStorage.setItem(STORAGE_KEYS.roomId, roomId)
      } else {
        localStorage.removeItem(STORAGE_KEYS.roomId)
      }
    } catch {
      // Ignore quota/storage access errors.
    }
  },

  loadPlayerName() {
    try {
      return localStorage.getItem(STORAGE_KEYS.playerName) ?? ''
    } catch {
      return ''
    }
  },

  clearSession() {
    try {
      localStorage.removeItem(STORAGE_KEYS.uuid)
      localStorage.removeItem(STORAGE_KEYS.roomId)
    } catch {
      // Ignore storage access errors.
    }
  },

  clearRoom() {
    try {
      localStorage.removeItem(STORAGE_KEYS.roomId)
    } catch {
      // Ignore storage access errors.
    }
  },

  load(): StoredSession | null {
    try {
      const uuid = localStorage.getItem(STORAGE_KEYS.uuid) ?? ''
      const playerName = localStorage.getItem(STORAGE_KEYS.playerName) ?? ''
      const roomId = localStorage.getItem(STORAGE_KEYS.roomId) ?? ''

      return uuid && roomId
        ? { uuid, playerName, roomId }
        : null
    } catch {
      return null
    }
  },
}