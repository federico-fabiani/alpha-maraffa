import type { CSSProperties } from "react";
import { useRef } from "react";
import arrowImg from "../assets/arrow.png";

const LONG_PRESS_MS = 380;

type ArrowCtaButtonProps = {
  label: string;
  onClick: () => void;
  className: string;
  ariaLabel: string;
  disabled?: boolean;
  style?: CSSProperties;
  type?: "button" | "submit" | "reset";
  arrowStyle?: CSSProperties;
};

export default function ArrowCtaButton({
  label,
  onClick,
  className,
  ariaLabel,
  disabled = false,
  style,
  type = "button",
  arrowStyle,
}: ArrowCtaButtonProps) {
  const longPressTimerRef = useRef<number | null>(null);
  const suppressClickRef = useRef(false);

  const clearLongPressTimer = () => {
    if (longPressTimerRef.current !== null) {
      window.clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  };

  const handlePointerDown = (event: React.PointerEvent<HTMLButtonElement>) => {
    if (event.pointerType !== "touch" && event.pointerType !== "pen") {
      return;
    }

    suppressClickRef.current = false;
    clearLongPressTimer();
    longPressTimerRef.current = window.setTimeout(() => {
      suppressClickRef.current = true;
      longPressTimerRef.current = null;
    }, LONG_PRESS_MS);
  };

  const handlePointerUpOrCancel = () => {
    clearLongPressTimer();
  };

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    if (suppressClickRef.current) {
      event.preventDefault();
      event.stopPropagation();
      suppressClickRef.current = false;
      return;
    }

    onClick();
  };

  return (
    <button
      type={type}
      onClick={handleClick}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUpOrCancel}
      onPointerCancel={handlePointerUpOrCancel}
      onPointerLeave={handlePointerUpOrCancel}
      className={className}
      style={style}
      aria-label={ariaLabel}
      disabled={disabled}
    >
      <img
        src={arrowImg}
        alt=""
        aria-hidden="true"
        className="home-arrow home-arrow-left home-hover-arrow"
        style={{ alignSelf: "center", ...arrowStyle }}
      />
      <span
        className="home-menu-label"
        aria-hidden="true"
        data-label={label}
        style={{ alignSelf: "center" }}
      />
      <img
        src={arrowImg}
        alt=""
        aria-hidden="true"
        className="home-arrow home-arrow-right home-hover-arrow"
        style={{ alignSelf: "center", ...arrowStyle }}
      />
    </button>
  );
}
