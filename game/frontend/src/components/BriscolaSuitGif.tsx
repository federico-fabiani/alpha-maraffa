import { useEffect, useMemo, useRef, useState } from 'react'
import { decompressFrames, parseGIF } from 'gifuct-js'
import type { ParsedFrame, ParsedGif } from 'gifuct-js'
import type { Suit } from '../types'

import bastoniGif from '../assets/gifs/bastoni.gif'
import coppeGif from '../assets/gifs/coppe.gif'
import denaraGif from '../assets/gifs/denara.gif'
import spadeGif from '../assets/gifs/spade.gif'

interface BriscolaSuitGifProps {
  suit: Suit
  replayToken?: string | number
  onPlaybackComplete?: () => void
  className?: string
  style?: React.CSSProperties
}

type GifFrame = ParsedFrame

const GIF_SRC_BY_SUIT: Record<Suit, string> = {
  bastoni: bastoniGif,
  denara: denaraGif,
  spade: spadeGif,
  coppe: coppeGif,
}

const BRISCOLA_GIF_FPS = 14
const BRISCOLA_FRAME_MS = 1000 / BRISCOLA_GIF_FPS

export default function BriscolaSuitGif({ suit, replayToken, onPlaybackComplete, className, style }: BriscolaSuitGifProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const onPlaybackCompleteRef = useRef(onPlaybackComplete)
  const [fallbackToImg, setFallbackToImg] = useState(false)

  const src = useMemo(() => GIF_SRC_BY_SUIT[suit], [suit])

  useEffect(() => {
    onPlaybackCompleteRef.current = onPlaybackComplete
  }, [onPlaybackComplete])

  useEffect(() => {
    setFallbackToImg(false)

    let cancelled = false
    let timerId: number | null = null
    let playbackCompleteNotified = false

    const notifyPlaybackComplete = () => {
      if (playbackCompleteNotified) return
      playbackCompleteNotified = true
      onPlaybackCompleteRef.current?.()
    }

    const run = async () => {
      const canvas = canvasRef.current
      if (!canvas) return

      try {
        const response = await fetch(src)
        if (!response.ok) {
          throw new Error('Failed to load briscola GIF')
        }

        const buffer = await response.arrayBuffer()
        if (cancelled) return

        const gif = parseGIF(buffer) as ParsedGif
        const frames = decompressFrames(gif, true) as GifFrame[]
        if (!frames.length) {
          setFallbackToImg(true)
          notifyPlaybackComplete()
          return
        }

        const logicalWidth = gif.lsd?.width ?? Math.max(...frames.map(frame => frame.dims.left + frame.dims.width))
        const logicalHeight = gif.lsd?.height ?? Math.max(...frames.map(frame => frame.dims.top + frame.dims.height))

        canvas.width = logicalWidth
        canvas.height = logicalHeight

        const ctx = canvas.getContext('2d', { willReadFrequently: true })
        if (!ctx) {
          setFallbackToImg(true)
          notifyPlaybackComplete()
          return
        }

        ctx.clearRect(0, 0, logicalWidth, logicalHeight)

        let previousFrame: GifFrame | null = null
        let restoreBeforeFrame: ImageData | null = null

        const drawFrame = (index: number) => {
          if (cancelled) return

          const frame = frames[index]

          if (previousFrame) {
            if (previousFrame.disposalType === 2) {
              ctx.clearRect(
                previousFrame.dims.left,
                previousFrame.dims.top,
                previousFrame.dims.width,
                previousFrame.dims.height,
              )
            } else if (previousFrame.disposalType === 3 && restoreBeforeFrame) {
              ctx.putImageData(restoreBeforeFrame, 0, 0)
            }
          }

          restoreBeforeFrame = frame.disposalType === 3
            ? ctx.getImageData(0, 0, logicalWidth, logicalHeight)
            : null

          const patchData = ctx.createImageData(frame.dims.width, frame.dims.height)
          patchData.data.set(frame.patch)
          ctx.putImageData(patchData, frame.dims.left, frame.dims.top)

          previousFrame = frame

          if (index >= frames.length - 1) {
            notifyPlaybackComplete()
            return
          }

          const delayMs = BRISCOLA_FRAME_MS
          timerId = window.setTimeout(() => drawFrame(index + 1), delayMs)
        }

        drawFrame(0)
      } catch {
        if (!cancelled) {
          setFallbackToImg(true)
          notifyPlaybackComplete()
        }
      }
    }

    run()

    return () => {
      cancelled = true
      if (timerId !== null) {
        window.clearTimeout(timerId)
      }
    }
  }, [src, replayToken])

  if (fallbackToImg) {
    return <img src={src} alt="" className={className} style={style} draggable={false} />
  }

  return <canvas ref={canvasRef} className={className} style={style} />
}