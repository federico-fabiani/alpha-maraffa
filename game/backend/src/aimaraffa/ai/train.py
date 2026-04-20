"""Train an XGBoost regressor on per-play Marafone features."""

from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

from . import config

logger = logging.getLogger(__name__)

# Identifiers + same-turn / round-final / target leaks. Kept verbatim from the
# previous train_model.py — the schema must match the predictor at inference time.
_BASE_DROP = {
    "game_id",
    "seat",
    "team",
    "turn_winner_seat", "turn_winner_team", "turn_pts",
    "round_pts_t1", "round_pts_t2",
    "round_pts_player_team",
    "round_pts_diff",
    "future_pts_diff",
}

_SUITS       = ["bastoni", "coppe", "denara", "spade"]
_DECLS       = ["busso", "striscio", "volo"]
_SUIT_STATUS = ["busso", "has", "unknown", "void"]


def _encode(df: pd.DataFrame) -> pd.DataFrame:
    """Cast columns to types XGBoost can ingest with correct categorical semantics."""
    df = df.copy()
    for col in ["briscola_suit", "lead_suit"]:
        if col in df.columns:
            df[col] = pd.Categorical(df[col], categories=_SUITS)

    decl_cols = ["declaration"] + [c for c in df.columns if c.endswith("_decl")]
    for col in decl_cols:
        if col in df.columns:
            df[col] = pd.Categorical(df[col], categories=_DECLS)

    for col in ["partner_suit_status", "opp_left_suit_status", "opp_right_suit_status"]:
        if col in df.columns:
            df[col] = pd.Categorical(df[col], categories=_SUIT_STATUS)

    for col in [c for c in df.columns if c.startswith("table_") and c.endswith("_rank")]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def _load(path: Path) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    logger.info("Loading %s …", path)
    df = pd.read_parquet(path)
    logger.info("  %d rows × %d columns", len(df), len(df.columns))

    y = df[config.TARGET].astype(np.float32)
    game_ids = df["game_id"]
    X = _encode(df.drop(columns=[c for c in _BASE_DROP if c in df.columns]))
    return X, y, game_ids


def train(data_path: Path, model_out: Path, importance_out: Path) -> None:
    """Train, evaluate, and persist a model + feature-importance CSV."""
    X, y, game_ids = _load(data_path)

    # Split by game_id so rows from the same game stay in one fold.
    unique_games = np.asarray(game_ids.unique())
    min_games = max(2, int(1 / config.TEST_SIZE) + 1)
    if len(unique_games) >= min_games:
        train_games, _ = train_test_split(
            unique_games, test_size=config.TEST_SIZE, random_state=42
        )
        train_mask = game_ids.isin(train_games)
        X_train, X_test = X[train_mask], X[~train_mask]
        y_train, y_test = y[train_mask], y[~train_mask]
        logger.info("Train: %d rows  Test: %d rows", len(X_train), len(X_test))
    else:
        logger.warning("Few games (%d) — falling back to row-level split.", len(unique_games))
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=config.TEST_SIZE, random_state=42
        )

    model = XGBRegressor(
        n_estimators=config.N_ESTIMATORS,
        learning_rate=config.LEARNING_RATE,
        max_depth=config.MAX_DEPTH,
        subsample=config.SUBSAMPLE,
        colsample_bytree=0.8,
        tree_method="hist",
        enable_categorical=True,
        early_stopping_rounds=50,
        device=config.DEVICE,
        n_jobs=-1 if config.DEVICE == "cpu" else 1,
        random_state=42,
        eval_metric="rmse",
    )

    logger.info("Training (device=%s, early stopping=50) …", config.DEVICE)
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=100)

    for split, Xs, ys in [("train", X_train, y_train), ("test", X_test, y_test)]:
        preds = model.predict(Xs)
        mae  = mean_absolute_error(ys, preds)
        rmse = mean_squared_error(ys, preds) ** 0.5
        r2   = r2_score(ys, preds)
        logger.info("[%s]  MAE=%.3f  RMSE=%.3f  R²=%.4f", split, mae, rmse, r2)

    model_out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_out)
    logger.info("Model → %s", model_out)

    imp = (pd.Series(model.feature_importances_, index=X.columns)
             .sort_values(ascending=False))
    imp.to_csv(importance_out, header=["importance"])
    logger.info("Importances → %s", importance_out)
    logger.info("Top 20:\n%s", imp.head(20).to_string())
