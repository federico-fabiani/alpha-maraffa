import { useEffect, useRef } from 'react'
import { APP_LAYOUT } from '../layout/layout'

export function useGameStageLayout() {
  const stageRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const stage = stageRef.current
    if (!stage) {
      return
    }

    const updateBackgroundFrame = () => {
      const stageWidth = stage.clientWidth
      const stageHeight = stage.clientHeight
      if (!stageWidth || !stageHeight) {
        return
      }

      const stageAspectRatio = stageWidth / stageHeight
      const renderWidth = stageAspectRatio > APP_LAYOUT.game.backgroundAspectRatio
        ? stageWidth
        : stageHeight * APP_LAYOUT.game.backgroundAspectRatio
      const renderHeight = stageAspectRatio > APP_LAYOUT.game.backgroundAspectRatio
        ? stageWidth / APP_LAYOUT.game.backgroundAspectRatio
        : stageHeight
      const renderLeft = (stageWidth - renderWidth) / 2
      const renderTop = (stageHeight - renderHeight) / 2

      stage.style.setProperty('--bg-render-left', `${renderLeft}px`)
      stage.style.setProperty('--bg-render-top', `${renderTop}px`)
      stage.style.setProperty('--bg-render-width', `${renderWidth}px`)
      stage.style.setProperty('--bg-render-height', `${renderHeight}px`)
    }

    updateBackgroundFrame()

    const resizeObserver = new ResizeObserver(updateBackgroundFrame)
    resizeObserver.observe(stage)

    return () => {
      resizeObserver.disconnect()
    }
  }, [])

  return stageRef
}