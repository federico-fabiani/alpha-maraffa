import { useRef } from "react";
import { createPortal } from "react-dom";

const ROWS: readonly (readonly string[])[] = [
  ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
  ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
  ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
  ["Z", "X", "C", "V", "B", "N", "M"],
];

interface CustomKeyboardProps {
  onKey: (key: string) => void;
  onBackspace: () => void;
  onEnter: () => void;
  onClose: () => void;
}

export default function CustomKeyboard({
  onKey,
  onBackspace,
  onEnter,
  onClose,
}: CustomKeyboardProps) {
  const repeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const repeatTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const startRepeat = (action: () => void) => {
    action();
    repeatTimeoutRef.current = setTimeout(() => {
      repeatTimerRef.current = setInterval(action, 80);
    }, 400);
  };

  const stopRepeat = () => {
    if (repeatTimerRef.current) clearInterval(repeatTimerRef.current);
    if (repeatTimeoutRef.current) clearTimeout(repeatTimeoutRef.current);
    repeatTimerRef.current = null;
    repeatTimeoutRef.current = null;
  };

  const press = (e: React.PointerEvent, action: () => void, repeat = false) => {
    e.preventDefault();
    e.stopPropagation();
    if (repeat) {
      startRepeat(action);
    } else {
      action();
    }
  };

  const keyboard = (
    <div
      className="custom-keyboard animate-slide-up"
      onPointerDown={(e) => e.stopPropagation()}
    >
      <div className="custom-keyboard-inner">
        <div className="custom-keyboard-main">
          {ROWS.map((row, ri) => (
            <div key={ri} className="custom-keyboard-row">
              {row.map((key) => (
                <button
                  key={key}
                  className="custom-key"
                  onPointerDown={(e) => press(e, () => onKey(key))}
                  type="button"
                  tabIndex={-1}
                >
                  {key}
                </button>
              ))}
            </div>
          ))}
        </div>
        <div className="custom-keyboard-actions">
          <button
            className="custom-key custom-key-backspace"
            onPointerDown={(e) => press(e, onBackspace, true)}
            onPointerUp={stopRepeat}
            onPointerLeave={stopRepeat}
            onPointerCancel={stopRepeat}
            type="button"
            tabIndex={-1}
          >
            CANC
          </button>
          <button
            className="custom-key custom-key-enter"
            onPointerDown={(e) => press(e, onEnter)}
            type="button"
            tabIndex={-1}
          >
            ENTER
          </button>
          <button
            className="custom-key custom-key-dismiss"
            onPointerDown={(e) => press(e, onClose)}
            type="button"
            tabIndex={-1}
          >
            BACK
          </button>
        </div>
      </div>
    </div>
  );

  if (typeof document === "undefined") {
    return keyboard;
  }

  return createPortal(keyboard, document.body);
}
