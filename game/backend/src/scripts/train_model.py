"""Train XGBoost to predict round_pts_player_team from per-play features."""

import argparse
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

try:
    import cudf
    import cudf.pandas  # noqa: F401
    _CUDF_AVAILABLE = True
except ImportError:
    _CUDF_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TARGET = "round_pts_diff"   # points_my_team - points_opponent_team in this round

# Columns excluded from features: identifiers, same-turn outcomes (leak), target components
_DROP = {
    "game_id",
    "seat",                                               # absolute identifier — redundant with is_my_team encoding
    "team",                                               # absolute identifier — causes team-identity bias
    "turn_winner_seat", "turn_winner_team", "turn_pts",   # outcome of the same turn
    "round_pts_t1", "round_pts_t2",                       # target components
    "round_pts_player_team",                              # target component
    TARGET,
}

# Fixed category lists — unordered, no arithmetic meaning
_SUITS        = ["bastoni", "coppe", "denara", "spade"]
_DECLS        = ["busso", "striscio", "volo"]   # NaN = no declaration / not lead
_SUIT_STATUS  = ["busso", "has", "unknown", "void"]  # derived suit-status features


# ── Preprocessing ──────────────────────────────────────────────────────────────

def _encode(df: pd.DataFrame) -> pd.DataFrame:
    """Convert all columns to types XGBoost can use, with correct categorical semantics."""
    df = df.copy()

    # Unordered suits — only reference-frame cols remain (card/table suits are now role-encoded)
    for col in ["briscola_suit", "lead_suit"]:
        if col in df.columns:
            df[col] = pd.Categorical(df[col], categories=_SUITS)

    # Unordered declarations — NaN where no declaration / not lead card
    decl_cols = ["declaration"] + [c for c in df.columns if c.endswith("_decl")]
    for col in decl_cols:
        if col in df.columns:
            df[col] = pd.Categorical(df[col], categories=_DECLS)

    # Suit-status features decoded from partner/opponent declarations
    for col in ["partner_suit_status", "opp_left_suit_status", "opp_right_suit_status"]:
        if col in df.columns:
            df[col] = pd.Categorical(df[col], categories=_SUIT_STATUS)

    # table_*_rank may be NaN (no card on table yet) — leave as float, NaN handled natively
    for col in [c for c in df.columns if c.startswith("table_") and c.endswith("_rank")]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def load(path: Path, use_gpu: bool = False) -> tuple[pd.DataFrame, pd.Series]:
    if path.suffix == ".parquet":
        logger.info("Loading %s (Parquet) …", path)
        df = pd.read_parquet(path)
    elif use_gpu and _CUDF_AVAILABLE:
        logger.info("Loading %s with cuDF (GPU) …", path)
        df = cudf.read_csv(path).to_pandas()
    else:
        if use_gpu and not _CUDF_AVAILABLE:
            logger.warning("cuDF not available — falling back to pandas for CSV loading")
        logger.info("Loading %s …", path)
        df = pd.read_csv(path, low_memory=False)
    logger.info("  %d rows × %d columns", len(df), len(df.columns))

    y = df[TARGET].astype(np.float32)
    game_ids = df["game_id"]

    df = _encode(df.drop(columns=[c for c in _DROP if c in df.columns]))
    return df, y, game_ids




# ── Training ───────────────────────────────────────────────────────────────────

def train(data: Path, model_out: Path, importance_out: Path,
          test_size: float, n_estimators: int, learning_rate: float,
          max_depth: int, subsample: float, device: str = "cpu") -> None:

    use_gpu = device == "cuda"
    if use_gpu:
        logger.info("GPU mode: device=cuda%s", " + cuDF" if _CUDF_AVAILABLE else " (cuDF not available)")
    X, y, game_ids = load(data, use_gpu=use_gpu)

    # Split by game_id so rows from the same game stay in the same fold
    unique_games = game_ids.unique()
    min_games_for_split = max(2, int(1 / test_size) + 1)
    if len(unique_games) >= min_games_for_split:
        train_games, test_games = train_test_split(
            unique_games, test_size=test_size, random_state=42
        )
        train_mask = game_ids.isin(train_games)
        X_train, X_test = X[train_mask], X[~train_mask]
        y_train, y_test = y[train_mask], y[~train_mask]
        logger.info("Train: %d rows (%d games) | Test: %d rows (%d games)",
                    len(X_train), len(train_games), len(X_test), len(test_games))
    else:
        logger.warning("Too few games (%d) for game-level split — falling back to row-level split",
                       len(unique_games))
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )
        logger.info("Train: %d rows | Test: %d rows", len(X_train), len(X_test))

    model = XGBRegressor(
        n_estimators=n_estimators,      # upper bound — early stopping finds optimum
        learning_rate=learning_rate,
        max_depth=max_depth,
        subsample=subsample,
        colsample_bytree=0.8,
        tree_method="hist",
        enable_categorical=True,
        early_stopping_rounds=50,       # XGBoost 2+ takes this in the constructor
        device=device,
        n_jobs=-1 if device == "cpu" else 1,   # n_jobs ignored on GPU, avoid warning
        random_state=42,
        eval_metric="rmse",
    )

    logger.info("Training (early stopping patience=50) …")
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=100,
    )

    # ── Metrics ────────────────────────────────────────────────────────────────
    for split, Xs, ys in [("train", X_train, y_train), ("test", X_test, y_test)]:
        preds = model.predict(Xs)
        mae  = mean_absolute_error(ys, preds)
        rmse = mean_squared_error(ys, preds) ** 0.5
        r2   = r2_score(ys, preds)
        logger.info("[%s]  MAE=%.3f  RMSE=%.3f  R²=%.4f", split, mae, rmse, r2)

    # ── Save model ─────────────────────────────────────────────────────────────
    joblib.dump(model, model_out)
    logger.info("Model saved → %s", model_out)

    # ── Feature importances ────────────────────────────────────────────────────
    imp = (
        pd.Series(model.feature_importances_, index=X.columns)
        .sort_values(ascending=False)
    )
    imp.to_csv(importance_out, header=["importance"])
    logger.info("Feature importances saved → %s", importance_out)
    logger.info("Top 20 features:\n%s", imp.head(20).to_string())


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Train XGBoost on Marafone play data")
    _a = Path("src/scripts/artifacts")
    parser.add_argument("--data",           type=Path, default=_a / "marafone_dataset.parquet")
    parser.add_argument("--model-out",      type=Path, default=_a / "marafone_model.joblib")
    parser.add_argument("--importance-out", type=Path, default=_a / "marafone_importance.csv")
    parser.add_argument("--test-size",   type=float, default=0.2)
    parser.add_argument("--n-estimators",type=int,   default=2000)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--max-depth",   type=int,   default=6)
    parser.add_argument("--subsample",   type=float, default=0.8)
    parser.add_argument("--device",      type=str,   default="cuda",
                        choices=["cpu", "cuda"],
                        help="XGBoost device: 'cuda' for GPU (default), 'cpu' for CPU")
    args = parser.parse_args()

    train(
        data=args.data,
        model_out=args.model_out,
        importance_out=args.importance_out,
        test_size=args.test_size,
        n_estimators=args.n_estimators,
        learning_rate=args.learning_rate,
        max_depth=args.max_depth,
        subsample=args.subsample,
        device=args.device,
    )


if __name__ == "__main__":
    main()
