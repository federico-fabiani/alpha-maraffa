import { APP_LAYOUT } from "./layout";

export type Rect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

export function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function intersectRect(rect: Rect, maxWidth: number, maxHeight: number): Rect {
  const left = clamp(rect.left, 0, maxWidth);
  const top = clamp(rect.top, 0, maxHeight);
  const right = clamp(rect.left + rect.width, 0, maxWidth);
  const bottom = clamp(rect.top + rect.height, 0, maxHeight);

  return {
    left,
    top,
    width: Math.max(0, right - left),
    height: Math.max(0, bottom - top),
  };
}

export function computeRusticBackgroundLayout(
  stageWidth: number,
  stageHeight: number,
) {
  const isCompactLandscape =
    stageWidth > stageHeight &&
    stageHeight <= APP_LAYOUT.home.compactLandscapeMaxHeight;
  const backgroundAspectRatio = APP_LAYOUT.home.backgroundAspectRatio;
  const contentRect = APP_LAYOUT.rusticBackground.contentRect;
  const contentCenterX = contentRect.x + contentRect.width / 2;
  const contentCenterY = contentRect.y + contentRect.height / 2;
  const stageAspectRatio = stageWidth / stageHeight;

  const coverWidth =
    stageAspectRatio > backgroundAspectRatio
      ? stageWidth
      : stageHeight * backgroundAspectRatio;
  const coverHeight =
    stageAspectRatio > backgroundAspectRatio
      ? stageWidth / backgroundAspectRatio
      : stageHeight;
  const focusScale = isCompactLandscape
    ? APP_LAYOUT.home.compactLandscapeBackgroundScale
    : 1;
  const renderWidth = coverWidth * focusScale;
  const renderHeight = coverHeight * focusScale;
  const unclampedLeft = stageWidth / 2 - renderWidth * contentCenterX;
  const unclampedTop = stageHeight / 2 - renderHeight * contentCenterY;
  const renderLeft = clamp(unclampedLeft, stageWidth - renderWidth, 0);
  const renderTop = clamp(unclampedTop, stageHeight - renderHeight, 0);

  return {
    renderLeft,
    renderTop,
    renderWidth,
    renderHeight,
    contentRect: intersectRect(
      {
        left: renderLeft + renderWidth * contentRect.x,
        top: renderTop + renderHeight * contentRect.y,
        width: renderWidth * contentRect.width,
        height: renderHeight * contentRect.height,
      },
      stageWidth,
      stageHeight,
    ),
  };
}