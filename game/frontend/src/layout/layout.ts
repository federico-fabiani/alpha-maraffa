import type { CSSProperties } from "react";

type SeatPosition = "top" | "right" | "bottom" | "left";

export const APP_LAYOUT = {
  rusticBackground: {
    contentRect: {
      x: 0.245,
      y: 0.2,
      width: 0.509,
      height: 0.58,
    },
  },
  shell: {
    inactiveBlurRadius: "7px",
    screenFadeDurationMs: 380,
    backgroundFadeDurationMs: 550,
    rusticBackgroundSize: "auto 100%",
    rusticBackgroundPosition: "center center",
    rusticBackgroundCompactLandscapeSize: "132% auto",
    rusticBackgroundCompactLandscapePosition: "50% 38%",
    startupRetryMs: 1200,
    connectionInset: {
      bottom: "0.5rem",
      right: "0.75rem",
    },
    startupCard: {
      gap: "1rem",
      paddingX: "1.75rem",
      paddingY: "1.5rem",
    },
    startupSpinnerSize: "54px",
  },
  home: {
    backgroundAspectRatio: 21 / 9,
    compactLandscapeMaxHeight: 500,
    compactLandscapeBackgroundScale: 1.24,
    compactLandscapeBackgroundAnchorY: 0.38,
    contentPadding: {
      top: {
        ratio: 0.05,
        minPx: 1,
        maxPx: 34,
      },
      right: {
        ratio: 0.08,
        minPx: 10,
        maxPx: 42,
      },
      bottom: {
        ratio: 0.08,
        minPx: 10,
        maxPx: 42,
      },
      left: {
        ratio: 0.08,
        minPx: 10,
        maxPx: 42,
      },
    },
    titleBottomSpacing: {
      ratio: 0.06,
      minPx: 8,
      maxPx: 30,
    },
    joinLayout: {
      helperFontSize: {
        ratio: 0.045,
        minPx: 13,
        maxPx: 18,
      },
      rowGap: {
        ratio: 0.025,
        minPx: 8,
        maxPx: 18,
      },
      codeInputWidth: {
        ratio: 0.28,
        minPx: 112,
        maxPx: 172,
      },
      backFontSize: {
        ratio: 0.034,
        minPx: 14,
        maxPx: 18,
      },
    },
    focusLayoutThresholds: {
      compactHeightPx: 290,
      compressedHeightPx: 225,
      compressedWidthPx: 360,
      sideBySideHeightPx: 390,
      sideBySideWidthPx: 620,
    },
    stageOffsetTop: "-14vh",
    stageOffsetTopCompactLandscape: "-18vh",
    demoBadgeInset: {
      top: "1rem",
      right: "1rem",
    },
    panelGap: "2.5rem",
    panelGapCompactLandscape: "0.65rem",
    menuGap: "0.25rem",
    menuGapCompactLandscape: "0.02rem",
    joinPanelGap: "1rem",
    joinPanelGapCompactLandscape: "0.35rem",
    inputWidth: "min(82vw, 25rem)",
    inputWidthCompactLandscape: "min(68vw, 17rem)",
    arrowWidth: "clamp(2.4rem, 4.5vw, 3.8rem)",
    arrowWidthCompactLandscape: "1.55rem",
    titleFontSize: "clamp(4.6rem, 14.95vw, 9.2rem)",
    titleFontSizeCompactLandscape: "clamp(2.5rem, 7.2vw, 4rem)",
    titleGap: "0.46em",
    titleGapCompactLandscape: "0.16em",
    inputFontSize: "1.65rem",
    inputFontSizeCompactLandscape: "1rem",
    menuItemFontSize: "clamp(1.8rem, 4vw, 2.8rem)",
    menuItemFontSizeCompactLandscape: "clamp(1rem, 2.7vw, 1.35rem)",
    menuItemGap: "1.1rem",
    menuItemGapCompactLandscape: "0.35rem",
    menuItemPadding: "0.28rem 0.4rem",
    menuItemPaddingCompactLandscape: "0.04rem 0.16rem",
  },
  lobby: {
    backgroundAspectRatio: 21 / 9,
    frameRect: {
      x: 0.2,
      y: 0.16,
      width: 0.6,
      height: 0.7,
    },
    safeInsetX: 18,
    safeInsetY: 16,
    basePanelWidth: 760,
    basePanelHeight: 410,
    panelMaxWidth: "30rem",
    panelGap: "0.9rem",
    headerReservedHeight: {
      ratio: 0.1,
      minPx: 20,
      maxPx: 90,
    },
    headerGap: {
      ratio: 0.028,
      minPx: 10,
      maxPx: 18,
    },
    contentPaddingX: {
      ratio: 0.03,
      minPx: 12,
      maxPx: 24,
    },
    contentPaddingY: {
      ratio: 0.024,
      minPx: 10,
      maxPx: 20,
    },
    sectionGap: {
      ratio: 0.035,
      minPx: 14,
      maxPx: 28,
    },
    tableArea: {
      widthRatio: 0.72,
      minWidthPx: 320,
      maxWidthPx: 520,
    },
    ctaArea: {
      minWidthPx: 150,
      maxWidthPx: 220,
    },
    responsive: {
      widthRangePx: {
        relaxed: 920,
        compressed: 520,
      },
      heightRangePx: {
        relaxed: 520,
        compressed: 280,
      },
      blendWeights: {
        width: 0.7,
        height: 0.3,
      },
      tableArea: {
        widthRatio: {
          relaxed: 0.72,
          compressed: 0.66,
        },
        minWidthPx: {
          relaxed: 320,
          compressed: 248,
        },
      },
      ctaArea: {
        minWidthPx: {
          relaxed: 150,
          compressed: 128,
        },
        arrowsVisibleWidthPx: {
          hidden: 160,
          fullyVisible: 216,
        },
      },
      tableOffsetXPx: {
        relaxed: 0,
        compressed: -28,
      },
      tableOffsetYPx: {
        relaxed: 0,
        compressed: -14,
      },
      nameSeatGapPx: {
        relaxed: 8,
        compressed: 3,
      },
    },
    table: {
      aspectRatio: 400 / 280,
      displayAspectRatio: 1.72,
      minWidthPx: 176,
      maxWidthPx: 460,
      hintMaxWidthRatio: 0.88,
    },
    seat: {
      badgeSizeRatio: 0.2,
      badgeSizeMinPx: 42,
      badgeSizeMaxPx: 68,
      /** Fixed gap in px from badge edge to nearest edge of the name label — same for all 4 seats. */
      nameSeatGapPx: 2,
      maxNameLength: 12,
      nameFontSize: {
        ratio: 0.032,
        minPx: 13,
        maxPx: 18,
      },
    },
    tableGap: "0.15rem",
    tableMiddleRowHeight: "1.85rem",
    avatarSize: "46px",
    seatCardGap: "0.35rem",
    seatCardPaddingY: "0.35rem",
    seatCardPaddingX: "0.3rem",
    seatActionGap: "0.15rem",
    ctaFontSize: {
      ratio: 0.08,
      minPx: 18,
      maxPx: 28,
    },
  },
  game: {
    backgroundAspectRatio: 6336 / 2688,
    debug: {
      showTableclothOverlay: true,
    },
    playingArea: {
      left: 0.2794,
      top: 0.2,
      width: 0.437,
      height: 0.51,
    },
    handPlayingAreaDelta: "max(0px, calc(4vh - 1.5rem))",
    hudInset: "0.75rem",
    opponentInset: {
      top: "1.5rem",
      side: "1rem",
    },
    selfPanel: {
      bottom: "12.5rem",
      gap: "0.375rem",
    },
    declarationControls: {
      gap: "0.5rem",
      offsetAboveHand: "0.5rem",
    },
    declarationGap: "0.375rem",
    turnBarHeight: "0.25rem",
    lastTrick: {
      offsetX: "clamp(11.5rem, 32vw, 12.5rem)",
      size: "7rem",
      labelMarginBottom: "0.375rem",
    },
    dropZone: {
      idleSize: "7rem",
      activeSize: "9rem",
    },
    announcement: {
      paddingX: "1.5rem",
      maxWidth: "16rem",
      paddingXCard: "1rem",
      paddingYCard: "0.85rem",
      handClearance: "0.6rem",
      estimatedCardHeight: "5.25rem",
    },
    dialog: {
      maxWidth: "20rem",
      marginX: "1rem",
      gap: "1.25rem",
      actionGap: "0.75rem",
      paddingX: "2rem",
      paddingY: "1.75rem",
    },
    table: {
      spreadXMultiplier: 1.2,
      spreadYMultiplier: 0.6,
      gifHeightRatio: 0.78,
      gifMaxWidthRatio: 0.9,
      gifTransform:
        "translate(-50%, -58%) perspective(500px) rotateX(30deg) rotate(-2deg)",
      slotStyles: {
        0: {
          left: "50%",
          top: "calc(50% + var(--table-card-spread-y))",
          transform: "translate(-50%, -50%) rotate(-4deg)",
        },
        1: {
          left: "calc(50% + var(--table-card-spread-x))",
          top: "50%",
          transform: "translate(-50%, -50%) rotate(6deg)",
        },
        2: {
          left: "50%",
          top: "calc(50% - var(--table-card-spread-y))",
          transform: "translate(-50%, -50%) rotate(3deg)",
        },
        3: {
          left: "calc(50% - var(--table-card-spread-x))",
          top: "50%",
          transform: "translate(-50%, -50%) rotate(-6deg)",
        },
      } satisfies Record<number, CSSProperties>,
      lastTrickSlotStyles: {
        0: { bottom: "0px", left: "50%", transform: "translateX(-50%)" },
        1: { right: "0px", top: "50%", transform: "translateY(-50%)" },
        2: { top: "0px", left: "50%", transform: "translateX(-50%)" },
        3: { left: "0px", top: "50%", transform: "translateY(-50%)" },
      } satisfies Record<number, CSSProperties>,
      collectVectors: {
        0: {
          0: { x: 0, y: 350 },
          1: { x: -200, y: 480 },
          2: { x: 0, y: 600 },
          3: { x: 200, y: 480 },
        },
        1: {
          0: { x: 520, y: -140 },
          1: { x: 320, y: 0 },
          2: { x: 520, y: 140 },
          3: { x: 700, y: 0 },
        },
        2: {
          0: { x: 0, y: -600 },
          1: { x: -200, y: -480 },
          2: { x: 0, y: -350 },
          3: { x: 200, y: -480 },
        },
        3: {
          0: { x: -520, y: -140 },
          1: { x: -700, y: 0 },
          2: { x: -520, y: 140 },
          3: { x: -320, y: 0 },
        },
      } satisfies Record<number, Record<number, { x: number; y: number }>>,
    },
  },
  cards: {
    sizes: {
      sm: { width: "2.5rem", height: "3.5rem" },
      md: { width: "min(6.875rem, 9vw)", height: "min(10.3rem, 13.5vw)" },
      lg: { width: "5rem", height: "7rem" },
      table: { width: "8rem", height: "12rem" },
    },
    hand: {
      overlap: "-0.5625rem",
      translateBase: "4px",
      translateOffsetFactor: "2.35px",
      rotateFactor: "3.25deg",
      hoverTranslate: "-14px",
      hoverRotateFactor: "1.4deg",
      hoverScale: 1.04,
    },
    opponentStackOverlap: "-1.25rem",
    dragGhost: {
      offsetX: 44,
      offsetY: 66,
      idleScale: 1.04,
      activeScale: 1.1,
    },
  },
  playerArea: {
    gap: "0.5rem",
  },
  connectionStatus: {
    gap: "0.375rem",
    dotSize: "0.5rem",
  },
  notification: {
    bottom: "11rem",
    paddingX: "1.5rem",
    paddingY: "0.75rem",
  },
  briscolaModal: {
    width: "clamp(12.75rem, 42vw, 22rem)",
    gridGap: "clamp(0.43rem, 1.4vw, 0.9rem)",
    cardPaddingX: "clamp(0.8rem, 2.5vw, 1.6rem)",
    cardPaddingY: "clamp(0.68rem, 2vw, 1.25rem)",
    titleFontSize: "clamp(0.77rem, 2.2vw, 1.15rem)",
    buttonPaddingX: "clamp(0.51rem, 1.8vw, 1rem)",
    buttonPaddingY: "clamp(0.38rem, 1.2vw, 0.75rem)",
    buttonIconSize: "clamp(1.02rem, 3vw, 1.75rem)",
    buttonLabelSize: "clamp(0.64rem, 1.6vw, 0.95rem)",
    handClearance: "0.65rem",
    estimatedHeight: "clamp(6.8rem, 22vw, 11.5rem)",
  },
  gameOver: {
    panelGap: "2rem",
    scoreWidth: "18rem",
    actionWidth: "16rem",
  },
} as const;

export type CardSize = keyof typeof APP_LAYOUT.cards.sizes;

export const APP_SHELL_LAYOUT_STYLES = {
  root: {
    position: "relative",
    width: "100%",
    height: "100%",
    overflow: "hidden",
  } satisfies CSSProperties,
  frame: {
    position: "relative",
    width: "100%",
    height: "100%",
    transition: `filter ${APP_LAYOUT.shell.screenFadeDurationMs}ms ease`,
  } satisfies CSSProperties,
  background: {
    position: "absolute",
    inset: 0,
    zIndex: 0,
    backgroundRepeat: "no-repeat",
    transition: `opacity ${APP_LAYOUT.shell.backgroundFadeDurationMs}ms ease`,
  } satisfies CSSProperties,
  content: {
    position: "relative",
    width: "100%",
    height: "100%",
    zIndex: 10,
  } satisfies CSSProperties,
  connection: {
    position: "absolute",
    bottom: APP_LAYOUT.shell.connectionInset.bottom,
    right: APP_LAYOUT.shell.connectionInset.right,
    zIndex: 50,
  } satisfies CSSProperties,
  startupOverlay: {
    position: "absolute",
    inset: 0,
    zIndex: 70,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  } satisfies CSSProperties,
  startupCard: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: APP_LAYOUT.shell.startupCard.gap,
    padding: `${APP_LAYOUT.shell.startupCard.paddingY} ${APP_LAYOUT.shell.startupCard.paddingX}`,
  } satisfies CSSProperties,
} as const;

export const layoutCssVariables = {
  "--layout-screen-transition-duration": `${APP_LAYOUT.shell.screenFadeDurationMs}ms`,
  "--layout-shell-rustic-background-size":
    APP_LAYOUT.shell.rusticBackgroundSize,
  "--layout-shell-rustic-background-position":
    APP_LAYOUT.shell.rusticBackgroundPosition,
  "--layout-shell-rustic-background-size-compact":
    APP_LAYOUT.shell.rusticBackgroundCompactLandscapeSize,
  "--layout-shell-rustic-background-position-compact":
    APP_LAYOUT.shell.rusticBackgroundCompactLandscapePosition,
  "--layout-hand-playing-area-delta": APP_LAYOUT.game.handPlayingAreaDelta,
  "--layout-playing-area-left": `${APP_LAYOUT.game.playingArea.left}`,
  "--layout-playing-area-top": `${APP_LAYOUT.game.playingArea.top}`,
  "--layout-playing-area-width": `${APP_LAYOUT.game.playingArea.width}`,
  "--layout-playing-area-height": `${APP_LAYOUT.game.playingArea.height}`,
  "--layout-home-stage-offset-top": APP_LAYOUT.home.stageOffsetTop,
  "--layout-home-stage-offset-top-compact":
    APP_LAYOUT.home.stageOffsetTopCompactLandscape,
  "--layout-home-panel-gap": APP_LAYOUT.home.panelGap,
  "--layout-home-panel-gap-compact": APP_LAYOUT.home.panelGapCompactLandscape,
  "--layout-home-menu-gap": APP_LAYOUT.home.menuGap,
  "--layout-home-menu-gap-compact": APP_LAYOUT.home.menuGapCompactLandscape,
  "--layout-home-join-panel-gap": APP_LAYOUT.home.joinPanelGap,
  "--layout-home-join-panel-gap-compact":
    APP_LAYOUT.home.joinPanelGapCompactLandscape,
  "--layout-home-title-font-size": APP_LAYOUT.home.titleFontSize,
  "--layout-home-title-font-size-compact":
    APP_LAYOUT.home.titleFontSizeCompactLandscape,
  "--layout-home-title-gap": APP_LAYOUT.home.titleGap,
  "--layout-home-title-gap-compact": APP_LAYOUT.home.titleGapCompactLandscape,
  "--layout-home-input-width": APP_LAYOUT.home.inputWidth,
  "--layout-home-input-width-compact":
    APP_LAYOUT.home.inputWidthCompactLandscape,
  "--layout-home-arrow-width": APP_LAYOUT.home.arrowWidth,
  "--layout-home-arrow-width-compact":
    APP_LAYOUT.home.arrowWidthCompactLandscape,
  "--layout-home-input-font-size": APP_LAYOUT.home.inputFontSize,
  "--layout-home-input-font-size-compact":
    APP_LAYOUT.home.inputFontSizeCompactLandscape,
  "--layout-home-menu-item-font-size": APP_LAYOUT.home.menuItemFontSize,
  "--layout-home-menu-item-font-size-compact":
    APP_LAYOUT.home.menuItemFontSizeCompactLandscape,
  "--layout-home-menu-item-gap": APP_LAYOUT.home.menuItemGap,
  "--layout-home-menu-item-gap-compact":
    APP_LAYOUT.home.menuItemGapCompactLandscape,
  "--layout-home-menu-item-padding": APP_LAYOUT.home.menuItemPadding,
  "--layout-home-menu-item-padding-compact":
    APP_LAYOUT.home.menuItemPaddingCompactLandscape,
  "--layout-lobby-panel-max-width": APP_LAYOUT.lobby.panelMaxWidth,
  "--layout-lobby-panel-gap": APP_LAYOUT.lobby.panelGap,
  "--layout-lobby-table-gap": APP_LAYOUT.lobby.tableGap,
  "--layout-lobby-table-middle-row-height":
    APP_LAYOUT.lobby.tableMiddleRowHeight,
  "--layout-lobby-avatar-size": APP_LAYOUT.lobby.avatarSize,
  "--layout-lobby-seat-card-gap": APP_LAYOUT.lobby.seatCardGap,
  "--layout-lobby-seat-card-padding-y": APP_LAYOUT.lobby.seatCardPaddingY,
  "--layout-lobby-seat-card-padding-x": APP_LAYOUT.lobby.seatCardPaddingX,
  "--layout-lobby-seat-action-gap": APP_LAYOUT.lobby.seatActionGap,
  "--layout-player-hand-overlap": APP_LAYOUT.cards.hand.overlap,
  "--layout-player-hand-translate-base": APP_LAYOUT.cards.hand.translateBase,
  "--layout-player-hand-translate-offset-factor":
    APP_LAYOUT.cards.hand.translateOffsetFactor,
  "--layout-player-hand-rotate-factor": APP_LAYOUT.cards.hand.rotateFactor,
  "--layout-player-hand-hover-translate": APP_LAYOUT.cards.hand.hoverTranslate,
  "--layout-player-hand-hover-rotate-factor":
    APP_LAYOUT.cards.hand.hoverRotateFactor,
  "--layout-player-hand-hover-scale": `${APP_LAYOUT.cards.hand.hoverScale}`,
  "--layout-opponent-stack-overlap": APP_LAYOUT.cards.opponentStackOverlap,
} as CSSProperties;

export const GAME_SEAT_STYLES: Record<
  Exclude<SeatPosition, "bottom">,
  CSSProperties
> = {
  top: {
    position: "absolute",
    top: APP_LAYOUT.game.opponentInset.top,
    left: "50%",
    transform: "translateX(-50%)",
  },
  left: {
    position: "absolute",
    left: APP_LAYOUT.game.opponentInset.side,
    top: "50%",
    transform: "translateY(-50%)",
  },
  right: {
    position: "absolute",
    right: APP_LAYOUT.game.opponentInset.side,
    top: "50%",
    transform: "translateY(-50%)",
  },
};

export function getCardSizeStyle(size: CardSize): CSSProperties {
  return APP_LAYOUT.cards.sizes[size];
}

export function getGameTableSlotStyle(relativeSeat: number): CSSProperties {
  return (
    APP_LAYOUT.game.table.slotStyles[
      relativeSeat as keyof typeof APP_LAYOUT.game.table.slotStyles
    ] ?? {}
  );
}

export function getLastTrickSlotStyle(relativeSeat: number): CSSProperties {
  return (
    APP_LAYOUT.game.table.lastTrickSlotStyles[
      relativeSeat as keyof typeof APP_LAYOUT.game.table.lastTrickSlotStyles
    ] ?? {}
  );
}

export function getCollectVector(
  winnerRelativeSeat: number,
  cardRelativeSeat: number,
): { x: number; y: number } {
  return (
    APP_LAYOUT.game.table.collectVectors[
      winnerRelativeSeat as keyof typeof APP_LAYOUT.game.table.collectVectors
    ]?.[
      cardRelativeSeat as keyof (typeof APP_LAYOUT.game.table.collectVectors)[0]
    ] ?? { x: 0, y: 0 }
  );
}

export function createTurnCountdownFillStyle(secsLeft: number): CSSProperties {
  return {
    width: `${Math.max(0, (secsLeft / 30) * 100)}%`,
    backgroundColor:
      secsLeft > 15 ? "#4ade80" : secsLeft > 7 ? "#facc15" : "#f87171",
  };
}

export function createBriscolaGifStyle(): CSSProperties {
  return {
    height: `calc((var(--bg-render-height) * var(--layout-playing-area-height)) * ${APP_LAYOUT.game.table.gifHeightRatio})`,
    maxWidth: `calc(var(--bg-render-width) * var(--layout-playing-area-width) * ${APP_LAYOUT.game.table.gifMaxWidthRatio})`,
  };
}

export function createGameDropZoneStyle(isDragOver: boolean): CSSProperties {
  const size = isDragOver
    ? APP_LAYOUT.game.dropZone.activeSize
    : APP_LAYOUT.game.dropZone.idleSize;
  return {
    width: size,
    height: size,
  };
}

export function createDragGhostStyle(
  x: number,
  y: number,
  isDragOver: boolean,
): CSSProperties {
  return {
    position: "fixed",
    pointerEvents: "none",
    zIndex: 50,
    left: x - APP_LAYOUT.cards.dragGhost.offsetX,
    top: y - APP_LAYOUT.cards.dragGhost.offsetY,
    transform: `rotate(-4deg) scale(${isDragOver ? APP_LAYOUT.cards.dragGhost.activeScale : APP_LAYOUT.cards.dragGhost.idleScale})`,
    transition: "transform 0.12s ease, filter 0.12s ease",
    filter: "drop-shadow(0 10px 24px rgba(0,0,0,0.55))",
  };
}
