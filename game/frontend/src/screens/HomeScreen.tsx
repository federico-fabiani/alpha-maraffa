import { useEffect, useRef, useState } from "react";
import { APP_LAYOUT } from "../layout/layout";
import useGameStore from "../state/gameStore";
import arrowImg from "../assets/arrow.png";
import CustomKeyboard from "../components/CustomKeyboard";

type MenuOption = "nuova_partita" | "cerca_tavolo";

const HOME_MENU_OPTIONS: { key: MenuOption; label: string }[] = [
  { key: "nuova_partita", label: "Nuova partita" },
  { key: "cerca_tavolo", label: "Cerca un tavolo" },
];

type Rect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

type HomeLayoutMode = "hero" | "compact" | "compressed";

type HomeFocusGeometry = {
  contentRect: Rect;
  layoutMode: HomeLayoutMode;
};

const TABLE_CODE_LENGTH = 4;
const HOME_HIDDEN_WARNINGS = new Set([
  "Partita già iniziata",
  "Stanza non trovata",
  "Tavolo non trovato",
]);

function sanitizeTableCode(value: string) {
  return value
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, "")
    .slice(0, TABLE_CODE_LENGTH);
}

function clamp(value: number, min: number, max: number) {
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

function computeHomeFocusGeometry(
  stageWidth: number,
  stageHeight: number,
): HomeFocusGeometry {
  const isCompactLandscape =
    stageWidth > stageHeight &&
    stageHeight <= APP_LAYOUT.home.compactLandscapeMaxHeight;
  const backgroundAspectRatio = APP_LAYOUT.home.backgroundAspectRatio;
  const contentRect = APP_LAYOUT.home.contentRect;
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
  const projectedContentRect = intersectRect(
    {
      left: renderLeft + renderWidth * contentRect.x,
      top: renderTop + renderHeight * contentRect.y,
      width: renderWidth * contentRect.width,
      height: renderHeight * contentRect.height,
    },
    stageWidth,
    stageHeight,
  );
  const focusThresholds = APP_LAYOUT.home.focusLayoutThresholds;

  let layoutMode: HomeLayoutMode = "hero";
  if (
    projectedContentRect.height < focusThresholds.compressedHeightPx ||
    projectedContentRect.width < focusThresholds.compressedWidthPx
  ) {
    layoutMode = "compressed";
  } else if (projectedContentRect.height < focusThresholds.compactHeightPx) {
    layoutMode = "compact";
  }

  return {
    contentRect: projectedContentRect,
    layoutMode,
  };
}

export default function HomeScreen() {
  const playerName = useGameStore((state) => state.playerName);
  const error = useGameStore((state) => state.error);
  const setPlayerName = useGameStore((state) => state.setPlayerName);
  const setBackgroundGeometry = useGameStore(
    (state) => state.setBackgroundGeometry,
  );
  const createRoom = useGameStore((state) => state.createRoom);
  const joinRoom = useGameStore((state) => state.joinRoom);

  const [selectedOption, setSelectedOption] =
    useState<MenuOption>("nuova_partita");
  const [showJoinPanel, setShowJoinPanel] = useState(false);
  const [tableCode, setTableCode] = useState("");
  const [focusGeometry, setFocusGeometry] = useState<HomeFocusGeometry>(() =>
    computeHomeFocusGeometry(
      typeof window === "undefined" ? 1280 : window.innerWidth,
      typeof window === "undefined" ? 720 : window.innerHeight,
    ),
  );

  const rootRef = useRef<HTMLDivElement>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const tableCodeInputRef = useRef<HTMLInputElement>(null);
  const playerNameRef = useRef(playerName);
  playerNameRef.current = playerName;

  const [isTouchDevice] = useState(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia("(pointer: coarse)").matches,
  );
  const [showCustomKeyboard, setShowCustomKeyboard] = useState(false);

  const canProceed = playerName.trim().length > 0;
  const hasTableCode = tableCode.trim().length > 0;
  const visibleError = error && !HOME_HIDDEN_WARNINGS.has(error) ? error : null;

  const shakeNameInput = () => {
    const element = nameInputRef.current;
    if (!element) {
      return;
    }

    element.classList.remove("shake");
    void element.offsetWidth;
    element.classList.add("shake");
    element.focus();
  };

  const requestFullscreen = () => {
    const isStandalonePwa =
      window.matchMedia("(display-mode: standalone)").matches ||
      ("standalone" in navigator &&
        (navigator as Navigator & { standalone?: boolean }).standalone ===
          true);

    if (!isStandalonePwa) {
      return;
    }

    const rootElement = document.documentElement;
    if (rootElement.requestFullscreen) {
      void rootElement.requestFullscreen();
    }
  };

  const handleActivateOption = (option: MenuOption) => {
    if (!canProceed) {
      shakeNameInput();
      return;
    }

    requestFullscreen();

    if (option === "nuova_partita") {
      void createRoom();
      return;
    }

    setShowJoinPanel(true);
    window.setTimeout(() => {
      tableCodeInputRef.current?.focus();
    }, 40);
  };

  const handleCustomKey = (key: string) => {
    if (playerNameRef.current.length < 14)
      setPlayerName(playerNameRef.current + key);
  };

  const handleCustomBackspace = () => {
    setPlayerName(playerNameRef.current.slice(0, -1));
  };

  const handleCustomEnter = () => {
    setShowCustomKeyboard(false);
    if (canProceed) handleActivateOption(selectedOption);
    else shakeNameInput();
  };

  const handleCustomClose = () => {
    setShowCustomKeyboard(false);
  };

  const handleJoinRoom = () => {
    if (!hasTableCode) {
      return;
    }

    joinRoom(tableCode);
  };

  const handleCloseJoinPanel = () => {
    setShowJoinPanel(false);
    setTableCode("");
  };

  useEffect(() => {
    const stage = rootRef.current;
    if (!stage) {
      return;
    }

    const appShellRoot = document.querySelector<HTMLElement>(".app-shell-root");
    if (!appShellRoot) {
      return;
    }

    const updateFocusGeometry = () => {
      const stageWidth = stage.clientWidth;
      const stageHeight = stage.clientHeight;
      if (!stageWidth || !stageHeight) {
        return;
      }

      const nextGeometry = computeHomeFocusGeometry(stageWidth, stageHeight);
      const renderWidth =
        nextGeometry.contentRect.width / APP_LAYOUT.home.contentRect.width;
      const renderHeight =
        nextGeometry.contentRect.height / APP_LAYOUT.home.contentRect.height;
      const renderLeft =
        nextGeometry.contentRect.left -
        renderWidth * APP_LAYOUT.home.contentRect.x;
      const renderTop =
        nextGeometry.contentRect.top -
        renderHeight * APP_LAYOUT.home.contentRect.y;

      setBackgroundGeometry({
        size: `${renderWidth}px ${renderHeight}px`,
        position: `${renderLeft}px ${renderTop}px`,
      });

      setFocusGeometry(nextGeometry);
    };

    updateFocusGeometry();

    const resizeObserver = new ResizeObserver(updateFocusGeometry);
    resizeObserver.observe(stage);

    return () => {
      resizeObserver.disconnect();
      delete appShellRoot.dataset.homeFocusCentered;
      appShellRoot.style.setProperty(
        "--layout-shell-rustic-background-size",
        APP_LAYOUT.shell.rusticBackgroundSize,
      );
      appShellRoot.style.setProperty(
        "--layout-shell-rustic-background-position",
        APP_LAYOUT.shell.rusticBackgroundPosition,
      );
    };
  }, []);

  useEffect(() => {
    const handleKeyboardNavigation = (event: KeyboardEvent) => {
      if (showJoinPanel) {
        return;
      }

      if (event.key === "ArrowUp" || event.key === "ArrowDown") {
        event.preventDefault();
        setSelectedOption((previousOption) =>
          previousOption === "nuova_partita" ? "cerca_tavolo" : "nuova_partita",
        );
        return;
      }

      if (
        event.key === "Enter" &&
        document.activeElement !== nameInputRef.current
      ) {
        handleActivateOption(selectedOption);
      }
    };

    window.addEventListener("keydown", handleKeyboardNavigation);
    return () => {
      window.removeEventListener("keydown", handleKeyboardNavigation);
    };
  }, [handleActivateOption, selectedOption, showJoinPanel]);

  const useSideBySideCtas =
    focusGeometry.contentRect.height <
      APP_LAYOUT.home.focusLayoutThresholds.sideBySideHeightPx ||
    focusGeometry.contentRect.width <
      APP_LAYOUT.home.focusLayoutThresholds.sideBySideWidthPx;
  const panelPaddingTop = clamp(
    focusGeometry.contentRect.height * APP_LAYOUT.home.contentPadding.top.ratio,
    APP_LAYOUT.home.contentPadding.top.minPx,
    APP_LAYOUT.home.contentPadding.top.maxPx,
  );
  const panelPaddingRight = clamp(
    focusGeometry.contentRect.width *
      APP_LAYOUT.home.contentPadding.right.ratio,
    APP_LAYOUT.home.contentPadding.right.minPx,
    APP_LAYOUT.home.contentPadding.right.maxPx,
  );
  const panelPaddingBottom = clamp(
    focusGeometry.contentRect.height *
      APP_LAYOUT.home.contentPadding.bottom.ratio,
    APP_LAYOUT.home.contentPadding.bottom.minPx,
    APP_LAYOUT.home.contentPadding.bottom.maxPx,
  );
  const panelPaddingLeft = clamp(
    focusGeometry.contentRect.width * APP_LAYOUT.home.contentPadding.left.ratio,
    APP_LAYOUT.home.contentPadding.left.minPx,
    APP_LAYOUT.home.contentPadding.left.maxPx,
  );
  const contentInnerWidth = Math.max(
    1,
    focusGeometry.contentRect.width - panelPaddingLeft - panelPaddingRight,
  );
  const contentInnerHeight = Math.max(
    1,
    focusGeometry.contentRect.height - panelPaddingTop - panelPaddingBottom,
  );
  const titleFontSize = clamp(
    Math.min(contentInnerHeight * 0.34, contentInnerWidth * 0.17),
    52,
    152,
  );
  const inputFontSize = clamp(
    Math.min(contentInnerHeight * 0.11, contentInnerWidth * 0.062),
    16,
    28,
  );
  const menuItemFontSize = clamp(
    Math.min(
      contentInnerHeight * (useSideBySideCtas ? 0.085 : 0.1),
      contentInnerWidth * (useSideBySideCtas ? 0.052 : 0.08),
    ),
    useSideBySideCtas ? 13 : 15,
    24,
  );
  const arrowWidth = clamp(menuItemFontSize * 1.35, 20, 34);
  const inputWidth = Math.min(
    clamp(
      contentInnerWidth * (useSideBySideCtas ? 0.78 : 0.58),
      useSideBySideCtas ? 200 : 150,
      360,
    ),
    contentInnerWidth,
  );
  const joinHelperFontSize = clamp(
    contentInnerHeight * APP_LAYOUT.home.joinLayout.helperFontSize.ratio,
    APP_LAYOUT.home.joinLayout.helperFontSize.minPx,
    APP_LAYOUT.home.joinLayout.helperFontSize.maxPx,
  );
  const joinRowGap = clamp(
    contentInnerWidth * APP_LAYOUT.home.joinLayout.rowGap.ratio,
    APP_LAYOUT.home.joinLayout.rowGap.minPx,
    APP_LAYOUT.home.joinLayout.rowGap.maxPx,
  );
  const joinCodeInputWidth = Math.min(
    clamp(
      contentInnerWidth * APP_LAYOUT.home.joinLayout.codeInputWidth.ratio,
      APP_LAYOUT.home.joinLayout.codeInputWidth.minPx,
      APP_LAYOUT.home.joinLayout.codeInputWidth.maxPx,
    ),
    Math.max(112, contentInnerWidth - 152),
  );
  const joinBackFontSize = clamp(
    contentInnerWidth * APP_LAYOUT.home.joinLayout.backFontSize.ratio,
    APP_LAYOUT.home.joinLayout.backFontSize.minPx,
    APP_LAYOUT.home.joinLayout.backFontSize.maxPx,
  );
  const rootStyle = {
    position: "relative",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    height: "100%",
    "--layout-home-title-font-size": `${titleFontSize}px`,
    "--layout-home-input-font-size": `${inputFontSize}px`,
    "--layout-home-menu-item-font-size": `${menuItemFontSize}px`,
    "--layout-home-arrow-width": `${arrowWidth}px`,
    "--layout-home-panel-gap": `${clamp(
      contentInnerHeight *
        (showJoinPanel ? 0.04 : useSideBySideCtas ? 0.06 : 0.07),
      6,
      showJoinPanel ? 20 : 28,
    )}px`,
    "--layout-home-panel-padding-top": `${panelPaddingTop}px`,
    "--layout-home-panel-padding-right": `${panelPaddingRight}px`,
    "--layout-home-panel-padding-bottom": `${panelPaddingBottom}px`,
    "--layout-home-panel-padding-left": `${panelPaddingLeft}px`,
    "--layout-home-title-bottom-spacing": `${clamp(
      contentInnerHeight * APP_LAYOUT.home.titleBottomSpacing.ratio,
      APP_LAYOUT.home.titleBottomSpacing.minPx,
      APP_LAYOUT.home.titleBottomSpacing.maxPx,
    )}px`,
    "--layout-home-menu-gap": `${clamp(
      useSideBySideCtas ? contentInnerWidth * 0.02 : contentInnerHeight * 0.02,
      6,
      18,
    )}px`,
    "--layout-home-join-panel-gap": `${clamp(
      contentInnerHeight * (showJoinPanel ? 0.03 : 0.04),
      6,
      showJoinPanel ? 14 : 18,
    )}px`,
    "--layout-home-input-width": `${inputWidth}px`,
    "--layout-home-menu-item-padding": `${clamp(
      menuItemFontSize * 0.3,
      5,
      10,
    )}px ${clamp(menuItemFontSize * 0.75, 12, 26)}px`,
    "--layout-home-menu-item-gap": `${clamp(menuItemFontSize * 0.5, 8, 16)}px`,
    "--layout-home-join-helper-font-size": `${joinHelperFontSize}px`,
    "--layout-home-join-row-gap": `${joinRowGap}px`,
    "--layout-home-join-code-width": `${joinCodeInputWidth}px`,
    "--layout-home-join-back-font-size": `${joinBackFontSize}px`,
  } as const;
  const badgeStyle = {
    position: "absolute",
    top: APP_LAYOUT.home.demoBadgeInset.top,
    right: APP_LAYOUT.home.demoBadgeInset.right,
    animation: "var(--animate-demo-blink)",
  } as const;
  const panelStyle = {
    position: "absolute",
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    justifyContent: "flex-start",
    gap: "var(--layout-home-panel-gap)",
    left: `${focusGeometry.contentRect.left}px`,
    top: `${focusGeometry.contentRect.top}px`,
    width: `${focusGeometry.contentRect.width}px`,
    height: `${focusGeometry.contentRect.height}px`,
    maxWidth: `${focusGeometry.contentRect.width}px`,
    paddingTop: "var(--layout-home-panel-padding-top)",
    paddingRight: "var(--layout-home-panel-padding-right)",
    paddingBottom: "var(--layout-home-panel-padding-bottom)",
    paddingLeft: "var(--layout-home-panel-padding-left)",
    boxSizing: "border-box" as const,
    textAlign: "center" as const,
  } as const;
  const menuStyle = {
    display: "flex",
    flexDirection: useSideBySideCtas ? ("row" as const) : ("column" as const),
    alignItems: "center",
    justifyContent: "center",
    width: "100%",
    flexWrap: useSideBySideCtas ? ("nowrap" as const) : ("wrap" as const),
    gap: "var(--layout-home-menu-gap)",
  } as const;
  const joinPanelStyle = {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    gap: "var(--layout-home-join-panel-gap)",
  } as const;
  const hiddenSvgStyle = {
    position: "absolute",
    width: 0,
    height: 0,
    overflow: "hidden",
  } as const;

  return (
    <div ref={rootRef} className="home-screen" style={rootStyle}>
      {/* DEMO badge */}
      <span
        className="home-demo-badge font-cinzel font-bold text-xs tracking-widest
                   px-3 py-1 rounded-full bg-red-800/80 text-amber-100 border border-red-700/50"
        style={badgeStyle}
      >
        DEMO
      </span>

      <div className="home-panel notranslate" style={panelStyle} translate="no">
        {/* Title – individual animated letters */}
        {/* One SVG filter per letter: unique warp seed + unique grain seed → unique campitura */}
        <svg aria-hidden="true" style={hiddenSvgStyle}>
          <defs>
            {(
              [
                {
                  id: "ts0",
                  warpSeed: 3,
                  grainSeed: 19,
                  warpScale: 2.2,
                  grainThresh: -2.1,
                },
                {
                  id: "ts1",
                  warpSeed: 17,
                  grainSeed: 5,
                  warpScale: 3.1,
                  grainThresh: -2.4,
                },
                {
                  id: "ts2",
                  warpSeed: 31,
                  grainSeed: 42,
                  warpScale: 1.8,
                  grainThresh: -2.0,
                },
                {
                  id: "ts3",
                  warpSeed: 8,
                  grainSeed: 27,
                  warpScale: 2.7,
                  grainThresh: -2.3,
                },
                {
                  id: "ts4",
                  warpSeed: 53,
                  grainSeed: 11,
                  warpScale: 2.0,
                  grainThresh: -2.5,
                },
                {
                  id: "ts5",
                  warpSeed: 22,
                  grainSeed: 38,
                  warpScale: 3.4,
                  grainThresh: -2.2,
                },
                {
                  id: "ts6",
                  warpSeed: 44,
                  grainSeed: 7,
                  warpScale: 2.4,
                  grainThresh: -1.9,
                },
                {
                  id: "ts7",
                  warpSeed: 13,
                  grainSeed: 61,
                  warpScale: 2.9,
                  grainThresh: -2.6,
                },
              ] as const
            ).map(({ id, warpSeed, grainSeed, warpScale, grainThresh }) => (
              <filter
                key={id}
                id={id}
                x="-4%"
                y="-10%"
                width="108%"
                height="125%"
                colorInterpolationFilters="sRGB"
              >
                <feTurbulence
                  type="fractalNoise"
                  baseFrequency="0.04 0.07"
                  numOctaves="3"
                  seed={warpSeed}
                  result="warp"
                />
                <feDisplacementMap
                  in="SourceGraphic"
                  in2="warp"
                  scale={warpScale}
                  xChannelSelector="R"
                  yChannelSelector="G"
                  result="rough"
                />
                <feTurbulence
                  type="fractalNoise"
                  baseFrequency="0.75 0.55"
                  numOctaves="4"
                  seed={grainSeed}
                  result="grain"
                />
                <feColorMatrix
                  type="matrix"
                  values={`0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  4 0 0 0 ${grainThresh}`}
                  in="grain"
                  result="grainMask"
                />
                <feComposite
                  in="rough"
                  in2="grainMask"
                  operator="in"
                  result="textured"
                />
                <feBlend in="rough" in2="textured" mode="multiply" />
              </filter>
            ))}
          </defs>
        </svg>
        <div className="title-word home-title" aria-label="MARAFONE">
          {(
            [
              {
                l: "M",
                anim: "letter-drift-a",
                dur: "5.3s",
                delay: "0s",
                filterId: "ts0",
                color: "#6b1c0e",
              },
              {
                l: "A",
                anim: "letter-drift-c",
                dur: "4.8s",
                delay: "-0.65s",
                filterId: "ts1",
                color: "#7a2010",
              },
              {
                l: "R",
                anim: "letter-drift-b",
                dur: "5.6s",
                delay: "-1.4s",
                filterId: "ts2",
                color: "#5e1a0c",
              },
              {
                l: "A",
                anim: "letter-drift-d",
                dur: "5.0s",
                delay: "-0.4s",
                filterId: "ts3",
                color: "#72200f",
              },
              {
                l: "F",
                anim: "letter-drift-a",
                dur: "5.9s",
                delay: "-2.3s",
                filterId: "ts4",
                color: "#63190b",
              },
              {
                l: "O",
                anim: "letter-drift-c",
                dur: "4.7s",
                delay: "-1.0s",
                filterId: "ts5",
                color: "#791f0e",
              },
              {
                l: "N",
                anim: "letter-drift-d",
                dur: "5.5s",
                delay: "-1.8s",
                filterId: "ts6",
                color: "#5b180b",
              },
              {
                l: "E",
                anim: "letter-drift-b",
                dur: "5.2s",
                delay: "-0.8s",
                filterId: "ts7",
                color: "#6f1d0d",
              },
            ] as const
          ).map(({ l, anim, dur, delay, filterId, color }, i) => (
            <span
              key={i}
              className="title-letter"
              style={{
                animation: `${anim} ${dur} ease-in-out infinite`,
                animationDelay: delay,
                color,
                filter: `url(#${filterId}) drop-shadow(3px 4px 0 rgba(20, 4, 2, 0.3))`,
              }}
            >
              {l}
            </span>
          ))}
        </div>

        <div
          className={`home-action-cluster${showJoinPanel ? " home-action-cluster-join" : ""}`}
        >
          {!showJoinPanel ? (
            <>
              <input
                ref={nameInputRef}
                type="text"
                placeholder="Il tuo nome…"
                value={playerName}
                onChange={(e) => setPlayerName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !showJoinPanel)
                    handleActivateOption(selectedOption);
                }}
                onClick={() => {
                  if (isTouchDevice) setShowCustomKeyboard(true);
                }}
                className="home-name-input"
                style={{ width: "var(--layout-home-input-width)" }}
                maxLength={14}
                autoFocus={!isTouchDevice}
                readOnly={isTouchDevice}
                inputMode={isTouchDevice ? "none" : undefined}
              />

              <div
                className={`home-menu${useSideBySideCtas ? " home-menu-side-by-side" : ""}`}
                style={menuStyle}
              >
                {HOME_MENU_OPTIONS.map((opt) => (
                  <div
                    key={opt.key}
                    className={`home-menu-item${!canProceed ? " disabled" : ""}`}
                    onClick={() => handleActivateOption(opt.key)}
                    onMouseEnter={() => setSelectedOption(opt.key)}
                    aria-label={opt.label}
                    role="button"
                  >
                    <img
                      src={arrowImg}
                      alt=""
                      className="home-arrow home-arrow-left"
                      style={{
                        opacity: selectedOption === opt.key ? 1 : 0,
                        width: "var(--layout-home-arrow-width)",
                      }}
                    />
                    <span
                      className="home-menu-label"
                      aria-hidden="true"
                      data-label={opt.label}
                    />
                    <img
                      src={arrowImg}
                      alt=""
                      className="home-arrow home-arrow-right"
                      style={{
                        opacity: selectedOption === opt.key ? 1 : 0,
                        width: "var(--layout-home-arrow-width)",
                      }}
                    />
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div
              className="home-join-panel animate-fade-in"
              style={joinPanelStyle}
            >
              <p className="home-join-helper">
                Ciao, <strong>{playerName}</strong>, inserisci il codice del
                tavolo
              </p>
              <div className="home-join-row">
                <input
                  ref={tableCodeInputRef}
                  type="text"
                  placeholder="M7Q4"
                  aria-label="Codice tavolo"
                  value={tableCode}
                  onChange={(e) =>
                    setTableCode(sanitizeTableCode(e.target.value))
                  }
                  onKeyDown={(e) => e.key === "Enter" && handleJoinRoom()}
                  className="home-name-input home-table-code-input"
                  style={{ width: "var(--layout-home-join-code-width)" }}
                  inputMode="text"
                  autoCapitalize="characters"
                  autoCorrect="off"
                  spellCheck={false}
                  maxLength={TABLE_CODE_LENGTH}
                />
                <button
                  type="button"
                  className="home-menu-item home-join-submit"
                  onClick={handleJoinRoom}
                  aria-label="Unisciti"
                >
                  <img
                    src={arrowImg}
                    alt=""
                    className="home-arrow home-arrow-left home-hover-arrow"
                    style={{ width: "var(--layout-home-arrow-width)" }}
                  />
                  <span
                    className="home-menu-label"
                    aria-hidden="true"
                    data-label="Unisciti"
                  />
                  <img
                    src={arrowImg}
                    alt=""
                    className="home-arrow home-arrow-right home-hover-arrow"
                    style={{ width: "var(--layout-home-arrow-width)" }}
                  />
                </button>
              </div>
              <button
                className="home-back-btn home-back-link"
                onClick={handleCloseJoinPanel}
                aria-label="Torna indietro"
                type="button"
              >
                <span aria-hidden="true" className="home-back-arrow" />
              </button>
            </div>
          )}
        </div>

        {visibleError && (
          <p
            className="home-error-message animate-fade-in"
            style={{
              fontFamily: "'IM Fell English', serif",
              color: "#8b1a06",
              fontSize: "0.95rem",
            }}
          >
            {visibleError}
          </p>
        )}
      </div>

      {showCustomKeyboard && (
        <CustomKeyboard
          onKey={handleCustomKey}
          onBackspace={handleCustomBackspace}
          onEnter={handleCustomEnter}
          onClose={handleCustomClose}
        />
      )}
    </div>
  );
}
