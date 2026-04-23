import { useEffect, useRef, useState } from 'react'
import type { BriscolaAnnouncement, Phase, Suit } from '../types'
import { SUIT_META } from '../components/cardMeta'

const BRISCOLA_BANNER_MS = 2000

export type BriscolaIntroState =
  | { stage: 'idle' }
  | { stage: 'banner'; suit: Suit; text: string }
  | { stage: 'gif'; suit: Suit; token: number }

export function useBriscolaIntro({
  briscola,
  briscolaAnnouncement,
  phase,
}: {
  briscola: Suit | null
  briscolaAnnouncement: BriscolaAnnouncement | null
  phase: Phase
}) {
  const [briscolaIntro, setBriscolaIntro] = useState<BriscolaIntroState>({ stage: 'idle' })
  const [briscolaGifMeta, setBriscolaGifMeta] = useState<{ suit: Suit; token: number } | null>(null)
  const lastBriscolaEventRef = useRef<number | null>(null)
  const fallbackIntroKeyRef = useRef<string | null>(null)

  const handleBriscolaGifPlaybackComplete = () => {
    setBriscolaIntro(previousState => (
      previousState.stage === 'gif'
        ? { stage: 'idle' }
        : previousState
    ))
  }

  useEffect(() => {
    if (!briscolaAnnouncement) {
      return
    }

    if (lastBriscolaEventRef.current === briscolaAnnouncement.eventId) {
      return
    }

    lastBriscolaEventRef.current = briscolaAnnouncement.eventId
    const { suit } = briscolaAnnouncement

    setBriscolaIntro({
      stage: 'banner',
      suit,
      text: `Le briscole sono ${SUIT_META[suit].label}!`,
    })

    const timerId = window.setTimeout(() => {
      setBriscolaGifMeta({ suit, token: briscolaAnnouncement.eventId })
      setBriscolaIntro({ stage: 'gif', suit, token: briscolaAnnouncement.eventId })
    }, BRISCOLA_BANNER_MS)

    return () => {
      window.clearTimeout(timerId)
    }
  }, [briscolaAnnouncement])

  useEffect(() => {
    if (briscola) {
      return
    }

    setBriscolaIntro({ stage: 'idle' })
    setBriscolaGifMeta(null)
    lastBriscolaEventRef.current = null
    fallbackIntroKeyRef.current = null
  }, [briscola])

  useEffect(() => {
    if (!briscola || briscolaAnnouncement) {
      return
    }

    const fallbackKey = `${phase}-${briscola}`
    if (fallbackIntroKeyRef.current === fallbackKey) {
      return
    }

    fallbackIntroKeyRef.current = fallbackKey
    const token = Date.now()
    setBriscolaGifMeta({ suit: briscola, token })
    setBriscolaIntro({ stage: 'gif', suit: briscola, token })
  }, [briscola, briscolaAnnouncement, phase])

  return {
    briscolaIntro,
    briscolaGifMeta,
    briscolaIntroActive: briscolaIntro.stage !== 'idle',
    handleBriscolaGifPlaybackComplete,
  }
}