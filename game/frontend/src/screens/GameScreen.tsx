import {
  APP_LAYOUT,
  createBriscolaGifStyle,
  createDragGhostStyle,
  createGameDropZoneStyle,
  createTurnCountdownFillStyle,
  GAME_SEAT_STYLES,
  getLastTrickSlotStyle,
} from "../layout/layout";
import { Card as CardComponent } from "../components/Card";
import PlayerArea from "../components/PlayerArea";
import TableArea from "../components/TableArea";
import BriscolaSuitGif from "../components/BriscolaSuitGif";
import BriscolaModal from "../components/BriscolaModal";
import Notification from "../components/Notification";
import { useGameScreenController } from "../hooks/useGameScreenController";

type HandSlotStyle = React.CSSProperties &
  Record<"--hand-index" | "--hand-offset" | "--hand-offset-abs", string>;

export default function GameScreen() {
  const {
    briscola,
    briscolaChooserName,
    briscolaGifMeta,
    briscolaIntro,
    currentDeclaration,
    currentPlayerSeat,
    declarationOptions,
    dismissNotification,
    drag,
    gamePhase,
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
    lastTrickCards,
    leadSeat,
    leftSeat,
    needsBriscola,
    notification,
    pendingDeclaration,
    playerBySeat,
    rightSeat,
    seat,
    secsLeft,
    selectBriscola,
    showForfeitConfirm,
    sortedHand,
    stageRef,
    tableCards,
    topSeat,
    totalScores,
    turnResultWinnerSeat,
  } = useGameScreenController();

  const rootStyle = {
    position: "relative",
    width: "100%",
    height: "100%",
    overflow: "hidden",
  } as const;
  const hudStyle = {
    position: "absolute",
    top: APP_LAYOUT.game.hudInset,
    left: APP_LAYOUT.game.hudInset,
    zIndex: 10,
  } as const;
  const forfeitStyle = {
    position: "absolute",
    top: APP_LAYOUT.game.hudInset,
    right: APP_LAYOUT.game.hudInset,
    zIndex: 10,
  } as const;
  const turnBarStyle = {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    zIndex: 20,
    height: APP_LAYOUT.game.turnBarHeight,
  } as const;
  const tableStyle = {
    position: "absolute",
    pointerEvents: "none",
    left: "calc(var(--bg-render-left) + (var(--bg-render-width) * var(--layout-playing-area-left)))",
    top: "calc(var(--bg-render-top) + (var(--bg-render-height) * var(--layout-playing-area-top)))",
    width: "calc(var(--bg-render-width) * var(--layout-playing-area-width))",
    height: "calc(var(--bg-render-height) * var(--layout-playing-area-height))",
    "--table-card-height":
      "min(12rem, calc((var(--bg-render-height) * var(--layout-playing-area-height)) / 2))",
    "--table-card-width": "calc(var(--table-card-height) * 0.6667)",
    "--table-card-spread-x": `calc(var(--table-card-width) * ${APP_LAYOUT.game.table.spreadXMultiplier})`,
    "--table-card-spread-y": `calc(var(--table-card-height) * ${APP_LAYOUT.game.table.spreadYMultiplier})`,
  } as React.CSSProperties;
  const gifWrapStyle = {
    position: "absolute",
    left: "50%",
    top: "50%",
    zIndex: 0,
    transform: APP_LAYOUT.game.table.gifTransform,
    transformOrigin: "center center",
  } as const;
  const lastTrickWrapStyle = {
    position: "absolute",
    top: "50%",
    left: "50%",
    transform: `translate(${APP_LAYOUT.game.lastTrick.offsetX}, -50%)`,
    zIndex: 20,
    pointerEvents: "none",
  } as const;
  const lastTrickGridStyle = {
    position: "relative",
    width: APP_LAYOUT.game.lastTrick.size,
    height: APP_LAYOUT.game.lastTrick.size,
  } as const;
  const selfPanelStyle = {
    position: "absolute",
    bottom: APP_LAYOUT.game.selfPanel.bottom,
    left: "50%",
    transform: "translateX(-50%)",
    zIndex: 10,
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    gap: APP_LAYOUT.game.selfPanel.gap,
  } as const;
  const declarationStyle = {
    display: "flex",
    gap: APP_LAYOUT.game.declarationGap,
  } as const;
  const dropZoneLayerStyle = {
    position: "absolute",
    inset: 0,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    pointerEvents: "none",
    zIndex: 20,
  } as const;
  const handWrapStyle = {
    position: "absolute",
    left: "50%",
    transform: "translateX(-50%)",
    zIndex: 20,
    top: "calc(var(--bg-render-top) + (var(--bg-render-height) * (var(--layout-playing-area-top) + var(--layout-playing-area-height))) + var(--hand-playing-area-delta))",
  } as const;
  const announcementOverlayStyle = {
    position: "absolute",
    inset: 0,
    zIndex: 30,
    pointerEvents: "none",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    paddingInline: APP_LAYOUT.game.announcement.paddingX,
  } as const;
  const dialogOverlayStyle = {
    position: "absolute",
    inset: 0,
    zIndex: 50,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  } as const;
  const dialogStyle = {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    gap: APP_LAYOUT.game.dialog.gap,
    maxWidth: APP_LAYOUT.game.dialog.maxWidth,
    marginInline: APP_LAYOUT.game.dialog.marginX,
    padding: `${APP_LAYOUT.game.dialog.paddingY} ${APP_LAYOUT.game.dialog.paddingX}`,
  } as const;
  const dialogActionsStyle = {
    display: "flex",
    gap: APP_LAYOUT.game.dialog.actionGap,
    width: "100%",
  } as const;
  const createHandSlotStyle = (
    index: number,
    handOffset: number,
  ): HandSlotStyle => ({
    "--hand-index": `${index}`,
    "--hand-offset": `${handOffset}`,
    "--hand-offset-abs": `${Math.abs(handOffset)}`,
  });

  return (
    <div
      ref={stageRef}
      className="game-stage game-bg select-none touch-none"
      style={rootStyle}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerCancel}
      onPointerLeave={handlePointerCancel}
    >
      <div className="game-stage-ambient" />
      <div className="game-stage-vignette" />

      {APP_LAYOUT.game.debug.showTableclothOverlay && (
        <div className="tablecloth-debug-area" />
      )}

      <div style={hudStyle}>
        <div className="bg-felt-900/80 border border-felt-700/60 rounded-xl px-3 py-2 backdrop-blur-sm flex items-center gap-2.5">
          <span className="font-cinzel font-bold text-lg text-amber-400">
            {totalScores["1"] ?? 0}
          </span>
          <span className="text-felt-500">|</span>
          <span className="font-cinzel font-bold text-lg text-blue-400">
            {totalScores["2"] ?? 0}
          </span>
        </div>
      </div>

      <div style={forfeitStyle}>
        <button
          onClick={handleOpenForfeitConfirm}
          className="px-2.5 py-1 rounded-lg text-[10px] font-semibold uppercase tracking-wider border border-red-800/60 bg-stone-950/70 text-red-400/80 hover:bg-red-900/40 hover:text-red-300 hover:border-red-600/70 transition-all backdrop-blur-sm"
        >
          Abbandona
        </button>
      </div>

      {secsLeft !== null && (
        <div className="bg-stone-900/60" style={turnBarStyle}>
          <div
            className="h-full transition-[width] duration-200 ease-linear"
            style={createTurnCountdownFillStyle(secsLeft)}
          />
        </div>
      )}

      <div style={GAME_SEAT_STYLES.top}>
        <PlayerArea
          player={playerBySeat[topSeat]}
          isActive={currentPlayerSeat === topSeat}
          position="top"
          declaration={leadSeat === topSeat ? currentDeclaration : null}
          showCards={false}
        />
      </div>

      <div style={GAME_SEAT_STYLES.left}>
        <PlayerArea
          player={playerBySeat[leftSeat]}
          isActive={currentPlayerSeat === leftSeat}
          position="left"
          declaration={leadSeat === leftSeat ? currentDeclaration : null}
          showCards={false}
        />
      </div>

      <div style={GAME_SEAT_STYLES.right}>
        <PlayerArea
          player={playerBySeat[rightSeat]}
          isActive={currentPlayerSeat === rightSeat}
          position="right"
          declaration={leadSeat === rightSeat ? currentDeclaration : null}
          showCards={false}
        />
      </div>

      <div style={tableStyle}>
        {briscolaGifMeta && briscolaIntro.stage !== "banner" && (
          <div style={gifWrapStyle}>
            <BriscolaSuitGif
              suit={briscolaGifMeta.suit}
              replayToken={briscolaGifMeta.token}
              onPlaybackComplete={handleBriscolaGifPlaybackComplete}
              className="block w-auto select-none drop-shadow-[0_10px_18px_rgba(0,0,0,0.5)]"
              style={createBriscolaGifStyle()}
            />
          </div>
        )}
        <TableArea
          tableCards={tableCards}
          mySeat={seat}
          winnerSeat={turnResultWinnerSeat}
          briscolaSuit={briscola}
        />
      </div>

      {lastTrickCards.length > 0 && (
        <div style={lastTrickWrapStyle}>
          <p className="text-[10px] tracking-[0.12em] uppercase text-amber-900/70 mb-1.5 pl-1 font-semibold drop-shadow-sm">
            Ultima presa
          </p>
          <div style={lastTrickGridStyle}>
            {lastTrickCards.map(({ seat: cardSeat, card }, index) => {
              const relativeSeat = (cardSeat - seat + 4) % 4;
              return (
                <div
                  key={`last-trick-${index}-${cardSeat}-${card.suit}-${card.rank}`}
                  className="absolute"
                  style={{
                    ...getLastTrickSlotStyle(relativeSeat),
                    zIndex: index + 1,
                  }}
                >
                  <CardComponent
                    card={card}
                    size="sm"
                    className="opacity-95 recent-trick-card"
                    briscolaSuit={briscola}
                  />
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div style={selfPanelStyle}>
        {isLeadPlayer && (
          <div style={declarationStyle}>
            {declarationOptions.map((declaration) => (
              <button
                key={declaration}
                onClick={() => handleToggleDeclaration(declaration)}
                className={`
                  px-3 py-1 rounded-lg text-[11px] font-bold uppercase tracking-wider border transition-all
                  ${
                    pendingDeclaration === declaration
                      ? "bg-amber-700/80 border-amber-400/80 text-amber-100 shadow-[0_0_10px_rgba(217,119,6,0.3)]"
                      : "bg-stone-900/80 border-stone-600/60 text-stone-400 hover:text-amber-400 hover:border-amber-700/50"
                  }
                `}
              >
                {declaration}
              </button>
            ))}
          </div>
        )}

        {leadSeat === seat && currentDeclaration && (
          <div className="px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-widest uppercase bg-amber-900/60 border border-amber-500/50 text-amber-300">
            {currentDeclaration.toUpperCase()}
          </div>
        )}

        {playerBySeat[seat] && (
          <div
            className={`
            px-3.5 py-1.5 rounded-full text-xs font-semibold border shadow-lg backdrop-blur-sm
            ${
              playerBySeat[seat]?.team === 1
                ? "border-amber-400/70 text-amber-100 bg-stone-950/85"
                : "border-blue-400/70 text-blue-100 bg-stone-950/85"
            }
            ${isMyTurn ? "animate-pulse-ring" : ""}
          `}
          >
            {playerBySeat[seat]?.name}
            {isMyTurn && <span className="ml-1 text-amber-400">●</span>}
          </div>
        )}
      </div>

      {isActiveDrag && (
        <div style={dropZoneLayerStyle}>
          <div
            className={`
              rounded-full border-2 transition-all duration-200
              ${
                isDragOver
                  ? "border-amber-400/75 bg-amber-400/10 shadow-[0_0_32px_rgba(251,191,36,0.2)]"
                  : "border-white/15"
              }
            `}
            style={createGameDropZoneStyle(isDragOver)}
          />
        </div>
      )}

      <div
        className={isActiveDrag ? "pointer-events-none" : ""}
        style={handWrapStyle}
      >
        <div className="player-hand">
          {sortedHand.map(({ card }, index) => {
            const handOffset = index - (sortedHand.length - 1) / 2;
            const isBeingDragged =
              isActiveDrag &&
              drag?.card.suit === card.suit &&
              drag?.card.rank === card.rank;
            const isBriscolaIdle =
              gamePhase === "briscola_selection" && !card.playable;

            return (
              <div
                key={`${card.suit}-${card.rank}`}
                className="hand-card-slot"
                style={createHandSlotStyle(index, handOffset)}
                onPointerDown={(event) => handleCardPointerDown(event, card)}
              >
                <CardComponent
                  card={card}
                  size="md"
                  briscolaSuit={briscola}
                  onClick={() => handleCardClick(card)}
                  className={`${isBeingDragged ? "opacity-0" : ""} ${isBriscolaIdle ? "idle-floating" : ""}`.trim()}
                />
              </div>
            );
          })}
        </div>
      </div>

      {isActiveDrag && drag && (
        <div style={createDragGhostStyle(drag.x, drag.y, isDragOver)}>
          <CardComponent card={drag.card} size="md" briscolaSuit={briscola} />
        </div>
      )}

      {needsBriscola && (
        <BriscolaModal
          onSelect={selectBriscola}
          selectorName={playerBySeat[seat]?.name}
        />
      )}

      {(isWaitingBriscola || briscolaIntro.stage === "banner") && (
        <div style={announcementOverlayStyle}>
          <div className="bg-felt-900/92 border border-amber-800/50 rounded-2xl px-7 py-4 text-center shadow-2xl backdrop-blur-sm animate-fade-in">
            <p className="text-amber-200 font-semibold text-base md:text-lg">
              {briscolaIntro.stage === "banner"
                ? briscolaIntro.text
                : `${briscolaChooserName} sta scegliendo le briscole...`}
            </p>
          </div>
        </div>
      )}

      {showForfeitConfirm && (
        <div
          className="bg-stone-950/70 backdrop-blur-sm"
          style={dialogOverlayStyle}
        >
          <div
            className="bg-felt-900 border border-red-800/60 rounded-2xl shadow-2xl animate-fade-in"
            style={dialogStyle}
          >
            <p className="text-red-300 font-cinzel font-bold text-lg text-center tracking-wide">
              Abbandona la partita?
            </p>
            <p className="text-felt-400 text-sm text-center">
              Sei sicuro di voler abbandonare e concedere la partita?
            </p>
            <div style={dialogActionsStyle}>
              <button
                onClick={handleCancelForfeit}
                className="flex-1 py-2.5 rounded-lg border border-felt-600/60 bg-stone-900/80 text-felt-300 hover:text-white hover:border-felt-400 transition-colors font-semibold text-sm"
              >
                Annulla
              </button>
              <button
                onClick={handleConfirmForfeit}
                className="flex-1 py-2.5 rounded-lg bg-red-700/80 hover:bg-red-600/90 border border-red-600/60 text-white font-semibold text-sm transition-colors"
              >
                Abbandona
              </button>
            </div>
          </div>
        </div>
      )}

      {notification && (
        <Notification
          notification={notification}
          onDismiss={dismissNotification}
        />
      )}
    </div>
  );
}
