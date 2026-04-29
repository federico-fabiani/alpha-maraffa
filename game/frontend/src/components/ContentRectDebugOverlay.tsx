import type { Rect } from "../layout/rusticBackground";

type ContentRectDebugOverlayProps = {
  rect: Rect;
  enabled: boolean;
};

export default function ContentRectDebugOverlay({
  rect,
  enabled,
}: ContentRectDebugOverlayProps) {
  if (!enabled) {
    return null;
  }

  return (
    <div
      style={{
        position: "absolute",
        left: `${rect.left}px`,
        top: `${rect.top}px`,
        width: `${rect.width}px`,
        height: `${rect.height}px`,
        border: "2px solid red",
        pointerEvents: "none",
        boxSizing: "border-box",
        background: "rgba(255, 0, 0, 0.05)",
        zIndex: 9999,
      }}
      aria-hidden="true"
    />
  );
}