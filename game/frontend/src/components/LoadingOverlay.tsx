import { APP_SHELL_LAYOUT_STYLES } from "../layout/layout";

interface LoadingOverlayProps {
  message: string;
}

export default function LoadingOverlay({ message }: LoadingOverlayProps) {
  return (
    <div
      className="loading-overlay"
      style={APP_SHELL_LAYOUT_STYLES.startupOverlay}
    >
      <div
        className="loading-card"
        style={APP_SHELL_LAYOUT_STYLES.startupCard}
      >
        <div className="loading-spinner" aria-hidden="true" />
        <p className="loading-title">{message}</p>
      </div>
    </div>
  );
}
