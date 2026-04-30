import type { CSSProperties } from "react";
import arrowImg from "../assets/arrow.png";

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
  return (
    <button
      type={type}
      onClick={onClick}
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
      <span className="home-menu-label" aria-hidden="true" data-label={label} style={{ alignSelf: "center" }} />
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
