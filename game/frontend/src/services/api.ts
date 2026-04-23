const JSON_HEADERS = {
  'Content-Type': 'application/json',
} as const

export async function pingBackend(): Promise<boolean> {
  try {
    const response = await fetch('/api/ping', { cache: 'no-store' })
    return response.ok
  } catch {
    return false
  }
}

export async function loginPlayer(playerName: string): Promise<{ uuid: string; playerName: string }> {
  const response = await fetch('/api/login', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ player_name: playerName }),
  })

  if (!response.ok) {
    throw new Error('Impossibile raggiungere il server')
  }

  const payload = (await response.json()) as { uuid: string; player_name: string }
  return {
    uuid: payload.uuid,
    playerName: payload.player_name,
  }
}

export async function createRoomRequest(playerName: string): Promise<{ roomId: string }> {
  const response = await fetch('/api/rooms', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ player_name: playerName }),
  })

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail ?? 'Impossibile creare la stanza')
  }

  const payload = (await response.json()) as { room_id: string }
  return {
    roomId: payload.room_id,
  }
}