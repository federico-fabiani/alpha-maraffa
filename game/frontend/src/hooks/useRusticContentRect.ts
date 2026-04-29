import { useEffect, useRef, useState } from "react";
import {
  computeRusticBackgroundLayout,
  type Rect,
} from "../layout/rusticBackground";
import useGameStore from "../state/gameStore";

const DEFAULT_STAGE_WIDTH = 1280;
const DEFAULT_STAGE_HEIGHT = 720;

export function useRusticContentRect() {
  const setBackgroundGeometry = useGameStore(
    (state) => state.setBackgroundGeometry,
  );
  const stageRef = useRef<HTMLDivElement | null>(null);
  const [contentRect, setContentRect] = useState<Rect>(() => {
    const stageWidth =
      typeof window === "undefined" ? DEFAULT_STAGE_WIDTH : window.innerWidth;
    const stageHeight =
      typeof window === "undefined"
        ? DEFAULT_STAGE_HEIGHT
        : window.innerHeight;

    return computeRusticBackgroundLayout(stageWidth, stageHeight).contentRect;
  });

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) {
      return;
    }

    const updateLayout = () => {
      const stageWidth = stage.clientWidth;
      const stageHeight = stage.clientHeight;
      if (!stageWidth || !stageHeight) {
        return;
      }

      const nextLayout = computeRusticBackgroundLayout(stageWidth, stageHeight);

      setBackgroundGeometry({
        size: `${nextLayout.renderWidth}px ${nextLayout.renderHeight}px`,
        position: `${nextLayout.renderLeft}px ${nextLayout.renderTop}px`,
      });
      setContentRect(nextLayout.contentRect);
    };

    updateLayout();

    const resizeObserver = new ResizeObserver(updateLayout);
    resizeObserver.observe(stage);

    return () => {
      resizeObserver.disconnect();
    };
  }, [setBackgroundGeometry]);

  return {
    stageRef,
    contentRect,
  };
}