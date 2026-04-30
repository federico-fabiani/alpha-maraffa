import { useEffect, useRef, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import useGameStore from "../state/gameStore";
import type { Card, Declaration, Notification, Suit } from "../types";
import { useBriscolaIntro } from "./useBriscolaIntro";
import { useGameStageLayout } from "./useGameStageLayout";
import { useTurnCountdown } from "./useTurnCountdown";

const SUIT_ORDER: Record<Suit, number> = {
  bastoni: 0,
  denara: 1,
  spade: 2,
  coppe: 3,
};

const CARD_ORDER: Record<number, number> = {
  3: 9,
  2: 8,
  1: 7,
  10: 6,
  9: 5,
  8: 4,
  7: 3,
  6: 2,
  5: 1,
  4: 0,
};

const DECLARATION_OPTIONS: Exclude<Declaration, null>[] = [
  "busso",
  "striscio",
  "volo",
];
const MIN_BUFFERED_PLAY_DELAY_MS = 1500;
const DEFAULT_NOTIFICATION_DURATION_MS = 2500;

interface DragState {
  card: Card;
  x: number;
  y: number;
  startX: number;
  startY: number;
  source: "mouse" | "touch";
}

interface TouchArmedCard {
  suit: Card["suit"];
  rank: Card["rank"];
}

function getCardKey(card: Pick<Card, "suit" | "rank">) {
  return `${card.suit}-${card.rank}`;
}

export function useGameScreenController() {
  const gameState = useGameStore(
    useShallow((state) => ({
      mySeat: state.mySeat,
      players: state.players,
      myHand: state.myHand,
      phase: state.phase,
      briscola: state.briscola,
      briscolaAnnouncement: state.briscolaAnnouncement,
      currentPlayerSeat: state.currentPlayerSeat,
      tableCards: state.tableCards,
      turnResultWinnerSeat: state.turnResultWinnerSeat,
      lastTrickCards: state.lastTrickCards,
      totalScores: state.totalScores,
      notification: state.notification,
      currentDeclaration: state.currentDeclaration,
      turnDeadline: state.turnDeadline,
    })),
  );

  const playCard = useGameStore((state) => state.playCard);
  const selectBriscola = useGameStore((state) => state.selectBriscola);
  const showNotification = useGameStore((state) => state.showNotification);
  const dismissNotification = useGameStore(
    (state) => state.dismissNotification,
  );
  const forfeit = useGameStore((state) => state.forfeit);

  const [showForfeitConfirm, setShowForfeitConfirm] = useState(false);
  const [pendingDeclaration, setPendingDeclaration] =
    useState<Declaration>(null);
  const [drag, setDrag] = useState<DragState | null>(null);
  const [touchArmedCard, setTouchArmedCard] = useState<TouchArmedCard | null>(
    null,
  );
  const [queuedNotifications, setQueuedNotifications] = useState<
    Notification[]
  >([]);
  const [activeNotification, setActiveNotification] =
    useState<Notification | null>(null);
  const [isTurnActivationPending, setIsTurnActivationPending] = useState(false);
  const lastTouchInteractionAtRef = useRef(0);
  const notificationTimerRef = useRef<number | null>(null);
  const turnActivationTimerRef = useRef<number | null>(null);
  // Initialize isMyTurn=true so first mount never spuriously triggers delay
  const prevTurnStateRef = useRef({ isMyTurn: true });

  const stageRef = useGameStageLayout();
  const secsLeft = useTurnCountdown(gameState.turnDeadline);
  const {
    briscolaIntro,
    briscolaGifMeta,
    briscolaIntroActive,
    handleBriscolaGifPlaybackComplete,
  } = useBriscolaIntro({
    briscola: gameState.briscola,
    briscolaAnnouncement: gameState.briscolaAnnouncement,
    phase: gameState.phase,
  });

  const seat = gameState.mySeat ?? 0;
  const topSeat = (seat + 2) % 4;
  const rightSeat = (seat + 1) % 4;
  const leftSeat = (seat + 3) % 4;

  const playerBySeat = Object.fromEntries(
    gameState.players.map((player) => [player.seat, player]),
  );

  const needsBriscola =
    gameState.phase === "briscola_selection" &&
    gameState.currentPlayerSeat === seat;
  const isWaitingBriscola =
    gameState.phase === "briscola_selection" &&
    !needsBriscola &&
    !briscolaIntroActive;
  const isMyTurn =
    gameState.currentPlayerSeat === seat &&
    gameState.phase === "playing" &&
    !briscolaIntroActive &&
    !isTurnActivationPending;
  const leadSeat =
    gameState.tableCards.length > 0
      ? gameState.tableCards[0].seat
      : gameState.currentPlayerSeat;
  const isLeadPlayer = isMyTurn && gameState.tableCards.length === 0;

  const briscolaChooserName =
    gameState.currentPlayerSeat != null
      ? (playerBySeat[gameState.currentPlayerSeat]?.name ?? "Un giocatore")
      : "Un giocatore";

  const sortedHand = gameState.myHand
    .map((card, index) => ({ card, index }))
    .sort((left, right) => {
      const suitDiff = SUIT_ORDER[left.card.suit] - SUIT_ORDER[right.card.suit];
      if (suitDiff !== 0) {
        return suitDiff;
      }

      const pointsDiff =
        CARD_ORDER[right.card.rank] - CARD_ORDER[left.card.rank];
      if (pointsDiff !== 0) {
        return pointsDiff;
      }

      const rankDiff = right.card.rank - left.card.rank;
      if (rankDiff !== 0) {
        return rankDiff;
      }

      return left.index - right.index;
    });

  useEffect(() => {
    const incomingNotification = gameState.notification;
    if (!incomingNotification) {
      return;
    }

    setQueuedNotifications((currentQueue) => [
      ...currentQueue,
      incomingNotification,
    ]);
    dismissNotification();
  }, [dismissNotification, gameState.notification]);

  useEffect(() => {
    const hasFlowPopup =
      showForfeitConfirm ||
      needsBriscola ||
      isWaitingBriscola ||
      briscolaIntroActive;

    if (
      activeNotification ||
      hasFlowPopup ||
      queuedNotifications.length === 0
    ) {
      return;
    }

    setActiveNotification(queuedNotifications[0]);
    setQueuedNotifications((currentQueue) => currentQueue.slice(1));
  }, [
    activeNotification,
    briscolaIntroActive,
    isWaitingBriscola,
    needsBriscola,
    queuedNotifications,
    showForfeitConfirm,
  ]);

  useEffect(() => {
    if (!activeNotification) {
      if (notificationTimerRef.current !== null) {
        window.clearTimeout(notificationTimerRef.current);
        notificationTimerRef.current = null;
      }
      return;
    }

    const duration =
      activeNotification.duration ?? DEFAULT_NOTIFICATION_DURATION_MS;
    notificationTimerRef.current = window.setTimeout(() => {
      notificationTimerRef.current = null;
      setActiveNotification(null);
    }, duration);

    return () => {
      if (notificationTimerRef.current !== null) {
        window.clearTimeout(notificationTimerRef.current);
        notificationTimerRef.current = null;
      }
    };
  }, [activeNotification]);

  useEffect(() => {
    return () => {
      if (turnActivationTimerRef.current !== null) {
        window.clearTimeout(turnActivationTimerRef.current);
      }
      if (notificationTimerRef.current !== null) {
        window.clearTimeout(notificationTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const isNowMyTurn =
      gameState.currentPlayerSeat === seat &&
      gameState.phase === "playing" &&
      !briscolaIntroActive;

    if (isNowMyTurn && !prevTurnStateRef.current.isMyTurn) {
      if (turnActivationTimerRef.current !== null) {
        window.clearTimeout(turnActivationTimerRef.current);
      }
      setIsTurnActivationPending(true);
      turnActivationTimerRef.current = window.setTimeout(() => {
        turnActivationTimerRef.current = null;
        setIsTurnActivationPending(false);
      }, MIN_BUFFERED_PLAY_DELAY_MS);
    } else if (!isNowMyTurn) {
      if (turnActivationTimerRef.current !== null) {
        window.clearTimeout(turnActivationTimerRef.current);
        turnActivationTimerRef.current = null;
      }
      setIsTurnActivationPending(false);
    }

    prevTurnStateRef.current = { isMyTurn: isNowMyTurn };
  }, [briscolaIntroActive, gameState.currentPlayerSeat, gameState.phase, seat]);

  const dragDistance = drag
    ? Math.hypot(drag.x - drag.startX, drag.y - drag.startY)
    : 0;
  const isActiveDrag = dragDistance > 8;
  const isDragOver = drag !== null && drag.startY - drag.y > 90;

  useEffect(() => {
    if (!touchArmedCard) {
      return;
    }

    const armedCardStillInHand = gameState.myHand.some(
      (card) => getCardKey(card) === getCardKey(touchArmedCard),
    );

    if (!isMyTurn || !armedCardStillInHand) {
      setTouchArmedCard(null);
    }
  }, [gameState.myHand, isMyTurn, touchArmedCard]);

  const playSelectedCard = (card: Card) => {
    playCard(card, isLeadPlayer ? pendingDeclaration : null);
    setPendingDeclaration(null);
    setTouchArmedCard(null);
  };

  const isTouchArmed = (card: Pick<Card, "suit" | "rank">) =>
    touchArmedCard !== null && getCardKey(touchArmedCard) === getCardKey(card);

  const handleCardClick = (card: Card) => {
    if (Date.now() - lastTouchInteractionAtRef.current < 550) {
      return;
    }

    if (!card.playable) {
      showNotification({
        text: "Mossa non valida",
        subtitle: "Questa carta non e giocabile in questo turno.",
        duration: 1400,
      });
      return;
    }

    if (!isMyTurn) {
      return;
    }

    playSelectedCard(card);
  };

  const handleCardPointerDown = (event: React.PointerEvent, card: Card) => {
    if (!isMyTurn || !card.playable) {
      return;
    }

    if (event.pointerType === "touch") {
      lastTouchInteractionAtRef.current = Date.now();

      if (isTouchArmed(card)) {
        setDrag({
          card,
          x: event.clientX,
          y: event.clientY,
          startX: event.clientX,
          startY: event.clientY,
          source: "touch",
        });
        return;
      }

      setTouchArmedCard({ suit: card.suit, rank: card.rank });
      return;
    }

    setTouchArmedCard(null);

    setDrag({
      card,
      x: event.clientX,
      y: event.clientY,
      startX: event.clientX,
      startY: event.clientY,
      source: "mouse",
    });
  };

  const handlePointerMove = (event: React.PointerEvent) => {
    if (!drag) {
      return;
    }

    setDrag((previousDrag) =>
      previousDrag
        ? {
            ...previousDrag,
            x: event.clientX,
            y: event.clientY,
          }
        : null,
    );
  };

  const handlePointerUp = (event: React.PointerEvent) => {
    if (!drag) {
      return;
    }

    const shouldPlayByDrop =
      drag.startY - event.clientY > 90 && drag.card.playable && isMyTurn;
    const shouldPlayByTouchConfirm =
      drag.source === "touch" &&
      !isActiveDrag &&
      drag.card.playable &&
      isMyTurn;

    if (shouldPlayByDrop || shouldPlayByTouchConfirm) {
      playSelectedCard(drag.card);
    }

    setDrag(null);
  };

  const handlePointerCancel = () => {
    setDrag(null);
  };

  const handleDismissActiveNotification = () => {
    if (notificationTimerRef.current !== null) {
      window.clearTimeout(notificationTimerRef.current);
      notificationTimerRef.current = null;
    }
    setActiveNotification(null);
  };

  const handleToggleDeclaration = (declaration: Exclude<Declaration, null>) => {
    setPendingDeclaration((currentDeclaration) =>
      currentDeclaration === declaration ? null : declaration,
    );
  };

  const handleOpenForfeitConfirm = () => {
    setShowForfeitConfirm(true);
  };

  const handleCancelForfeit = () => {
    setShowForfeitConfirm(false);
  };

  const handleConfirmForfeit = () => {
    setShowForfeitConfirm(false);
    forfeit();
  };

  return {
    briscola: gameState.briscola,
    briscolaChooserName,
    briscolaGifMeta,
    briscolaIntro,
    briscolaIntroActive,
    currentDeclaration: gameState.currentDeclaration,
    currentPlayerSeat: gameState.currentPlayerSeat,
    declarationOptions: DECLARATION_OPTIONS,
    dismissNotification: handleDismissActiveNotification,
    drag,
    gamePhase: gameState.phase,
    handleBriscolaGifPlaybackComplete,
    handleCancelForfeit,
    handleCardClick,
    handleCardPointerDown,
    handleConfirmForfeit,
    handleOpenForfeitConfirm,
    handlePointerCancel,
    handlePointerMove,
    handlePointerUp,
    handleToggleDeclaration,
    isActiveDrag,
    isDragOver,
    isLeadPlayer,
    isMyTurn,
    isWaitingBriscola,
    lastTrickCards: gameState.lastTrickCards,
    leadSeat,
    leftSeat,
    needsBriscola,
    notification: activeNotification,
    pendingDeclaration,
    playerBySeat,
    rightSeat,
    seat,
    secsLeft,
    selectBriscola,
    showForfeitConfirm,
    sortedHand,
    stageRef,
    tableCards: briscolaIntroActive ? [] : gameState.tableCards,
    touchArmedCard,
    topSeat,
    totalScores: gameState.totalScores,
    turnResultWinnerSeat: gameState.turnResultWinnerSeat,
  };
}
