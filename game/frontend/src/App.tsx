import { useEffect, useRef } from "react";
import useGameStore from "./state/gameStore";
import {
  APP_LAYOUT,
  APP_SHELL_LAYOUT_STYLES,
  layoutCssVariables,
} from "./layout/layout";
import { useAppBootstrap } from "./hooks/useAppBootstrap";
import { computeRusticBackgroundLayout } from "./layout/rusticBackground";
import HomeScreen from "./screens/HomeScreen";
import LobbyScreen from "./screens/LobbyScreen";
import GameScreen from "./screens/GameScreen";
import GameOverScreen from "./screens/GameOverScreen";
import ConnectionStatus from "./components/ConnectionStatus";
import backgroundImg from "./assets/homepage/background.jpg";
import { CRT_FLICKER_EVENT } from "./services/visualEffects";

const screens = {
  home: HomeScreen,
  lobby: LobbyScreen,
  game: GameScreen,
  gameover: GameOverScreen,
} as const;

export default function App() {
  const screen = useGameStore((state) => state.screen);
  const displayedScreen = useGameStore((state) => state.displayedScreen);
  const backgroundGeometry = useGameStore((state) => state.backgroundGeometry);
  const screenTransitionPhase = useGameStore(
    (state) => state.screenTransitionPhase,
  );
  const setBackgroundGeometry = useGameStore(
    (state) => state.setBackgroundGeometry,
  );
  const beginScreenTransition = useGameStore(
    (state) => state.beginScreenTransition,
  );
  const completeScreenTransition = useGameStore(
    (state) => state.completeScreenTransition,
  );
  const backendStatus = useAppBootstrap();
  const shellRootRef = useRef<HTMLDivElement | null>(null);
  const crtOverlayRef = useRef<HTMLDivElement | null>(null);
  const crtPulseTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    const root = shellRootRef.current;
    if (!root) {
      return;
    }

    const updateGeometry = () => {
      const width = root.clientWidth;
      const height = root.clientHeight;

      if (!width || !height) {
        return;
      }

      const nextLayout = computeRusticBackgroundLayout(width, height);
      setBackgroundGeometry({
        size: `${nextLayout.renderWidth}px ${nextLayout.renderHeight}px`,
        position: `${nextLayout.renderLeft}px ${nextLayout.renderTop}px`,
      });
    };

    updateGeometry();

    const observer = new ResizeObserver(updateGeometry);
    observer.observe(root);

    return () => {
      observer.disconnect();
    };
  }, [setBackgroundGeometry]);

  useEffect(() => {
    if (screen === displayedScreen) {
      return;
    }

    beginScreenTransition();
    const timerId = window.setTimeout(() => {
      completeScreenTransition();
    }, APP_LAYOUT.shell.screenFadeDurationMs);

    return () => {
      window.clearTimeout(timerId);
    };
  }, [
    beginScreenTransition,
    completeScreenTransition,
    displayedScreen,
    screen,
  ]);

  useEffect(() => {
    const handleCrtFlicker = () => {
      const overlay = crtOverlayRef.current;
      if (!overlay) {
        return;
      }

      overlay.classList.remove("crt-overlay-pulse");
      void overlay.offsetWidth;
      overlay.classList.add("crt-overlay-pulse");

      if (crtPulseTimeoutRef.current !== null) {
        window.clearTimeout(crtPulseTimeoutRef.current);
      }

      crtPulseTimeoutRef.current = window.setTimeout(() => {
        overlay.classList.remove("crt-overlay-pulse");
        crtPulseTimeoutRef.current = null;
      }, 210);
    };

    window.addEventListener(CRT_FLICKER_EVENT, handleCrtFlicker);

    return () => {
      window.removeEventListener(CRT_FLICKER_EVENT, handleCrtFlicker);
      if (crtPulseTimeoutRef.current !== null) {
        window.clearTimeout(crtPulseTimeoutRef.current);
      }
    };
  }, []);

  const showRusticBg =
    displayedScreen === "home" || displayedScreen === "lobby";
  const Screen = screens[displayedScreen];
  const backendReady = backendStatus === "ready";
  const contentVisible = screenTransitionPhase === "visible";

  return (
    <div
      ref={shellRootRef}
      className="app-shell-root"
      style={{ ...APP_SHELL_LAYOUT_STYLES.root, ...layoutCssVariables }}
    >
      <div
        className={backendReady ? "" : "pointer-events-none select-none"}
        style={{
          ...APP_SHELL_LAYOUT_STYLES.frame,
          filter: backendReady
            ? "none"
            : `blur(${APP_LAYOUT.shell.inactiveBlurRadius})`,
        }}
      >
        {/* Persistent rustic background — visible for home and lobby */}
        <div
          className="app-rustic-background"
          style={{
            ...APP_SHELL_LAYOUT_STYLES.background,
            backgroundImage: `url(${backgroundImg})`,
            backgroundSize: backgroundGeometry?.size || undefined,
            backgroundPosition: backgroundGeometry?.position || undefined,
            opacity: showRusticBg ? 1 : 0,
          }}
        />

        {/* CRT overlay */}
        <div ref={crtOverlayRef} className="crt-overlay" />

        {/* Screen content */}
        <div
          className="screen-content"
          style={{
            ...APP_SHELL_LAYOUT_STYLES.content,
            opacity: contentVisible ? 1 : 0,
          }}
        >
          <Screen />
        </div>

        {displayedScreen !== "home" && (
          <div style={APP_SHELL_LAYOUT_STYLES.connection}>
            <ConnectionStatus />
          </div>
        )}
      </div>

      {!backendReady && (
        <div
          className="startup-loading-overlay"
          style={APP_SHELL_LAYOUT_STYLES.startupOverlay}
        >
          <div
            className="startup-loading-card"
            style={APP_SHELL_LAYOUT_STYLES.startupCard}
          >
            <div className="startup-spinner" aria-hidden="true" />
            <p className="startup-loading-title">Connessione al tavolo</p>
            <p className="startup-loading-subtitle">
              Attendo risposta del backend...
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
