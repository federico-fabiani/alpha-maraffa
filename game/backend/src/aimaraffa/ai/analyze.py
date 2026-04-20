"""Produce a Markdown strategy report for a trained Marafone model."""

from __future__ import annotations

import logging
import textwrap
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from . import config

log = logging.getLogger(__name__)

TARGET = config.TARGET

_DROP = {
    "game_id",
    "seat",
    "team",
    "turn_winner_seat", "turn_winner_team", "turn_pts",
    "round_pts_t1", "round_pts_t2",
    "round_pts_player_team",
    "round_pts_diff",
    TARGET,
}
_SUITS       = ["bastoni", "coppe", "denara", "spade"]
_DECLS       = ["busso", "striscio", "volo"]
_SUIT_STATUS = ["busso", "has", "unknown", "void"]
_RANKS       = list(range(1, 11))

# Game rules
RANK_PTS  = {1: 3, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 2, 9: 3, 10: 4}
RANK_NAME = {1: "Asso", 2: "2", 3: "3", 4: "4", 5: "5",
             6: "6", 7: "7", 8: "Fante", 9: "Cavallo", 10: "Re"}


# ── Preprocessing (mirrors train.py) ───────────────────────────────────────────

def _encode(df: pd.DataFrame) -> pd.DataFrame:
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


def _load_raw(path: Path) -> pd.DataFrame:
    log.info("Loading %s …", path)
    df = pd.read_parquet(path)
    log.info("  %d rows × %d columns", len(df), len(df.columns))
    return df


def _load_for_model(df: pd.DataFrame):
    y = df[TARGET].astype(np.float32)
    X = _encode(df.drop(columns=[c for c in _DROP if c in df.columns]))
    return X, y


# ── Report helpers ─────────────────────────────────────────────────────────────

def _h(level: int, text: str) -> str:
    return "#" * level + " " + text + "\n"


def _table(df_in: pd.DataFrame, floatfmt: str = ".3f") -> str:
    df = df_in.copy().reset_index(drop=False)
    cols = list(df.columns)
    sep  = [":---" if df[c].dtype == object or str(df[c].dtype).startswith("cat")
            else "---:" for c in cols]
    rows = [" | ".join(cols), " | ".join(sep)]
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            cells.append(f"{v:{floatfmt}}" if isinstance(v, float) else str(v))
        rows.append(" | ".join(cells))
    return "\n".join(rows) + "\n"


def _bar(value: float, max_val: float, width: int = 20) -> str:
    filled = int(round(width * min(abs(value), max_val) / max_val))
    bar = "█" * filled + "░" * (width - filled)
    sign = "+" if value >= 0 else "-"
    return f"{sign} {bar}"


# ── Sections ───────────────────────────────────────────────────────────────────

def _section_overview(df: pd.DataFrame) -> str:
    n_games  = df["game_id"].nunique()
    n_rounds = df[["game_id", "round_num"]].drop_duplicates().shape[0]
    n_plays  = len(df)
    wins_t1  = (df.groupby(["game_id"])["round_pts_t1"]
                  .sum()
                  .gt(df.groupby(["game_id"])["round_pts_t2"].sum())
                  .mean())

    out  = _h(2, "Dataset Overview")
    out += "| Metric | Value |\n|:---|---:|\n"
    out += f"| Partite | {n_games:,} |\n"
    out += f"| Round | {n_rounds:,} |\n"
    out += f"| Giocate totali | {n_plays:,} |\n"
    out += f"| Win-rate team1 (seat 0/2) | {wins_t1:.1%} |\n\n"
    return out


def _section_model_metrics(model, X: pd.DataFrame, y: pd.Series) -> str:
    import xgboost as xgb
    dmat  = xgb.DMatrix(_encode(X), enable_categorical=True)
    preds = model.get_booster().predict(dmat)
    mae   = mean_absolute_error(y, preds)
    rmse  = mean_squared_error(y, preds) ** 0.5
    r2    = r2_score(y, preds)

    out  = _h(2, "Metriche del Modello (Test Set)")
    out += "| Metrica | Valore |\n|:---|---:|\n"
    out += f"| MAE | {mae:.3f} punti |\n"
    out += f"| RMSE | {rmse:.3f} punti |\n"
    out += f"| R² | {r2:.4f} |\n"
    out += "\n> `future_pts_diff` = punti_mia_squadra − punti_avversari dai turni rimanenti (giro corrente incluso)\n\n"
    return out


def _section_feature_importance(model, X: pd.DataFrame, top_n: int) -> str:
    imp = (pd.Series(model.feature_importances_, index=X.columns)
             .sort_values(ascending=False)
             .head(top_n)
             .reset_index())
    imp.columns = ["Feature", "Importance"]
    imp["Bar"] = imp["Importance"].apply(lambda v: _bar(v, imp["Importance"].max()))

    out  = _h(2, f"Feature Importance (Top {top_n})")
    out += _table(imp[["Feature", "Importance", "Bar"]]) + "\n"
    return out


def _section_card_value(df: pd.DataFrame) -> str:
    df2 = df.copy()
    df2["card_role"] = np.where(
        df2["card_is_briscola"] == 1, "briscola",
        np.where(df2["card_is_lead"] == 1, "lead", "altro")
    )
    df2["rank_name"] = df2["card_rank"].map(RANK_NAME)
    df2["rank_pts"]  = df2["card_rank"].map(RANK_PTS)

    pivot = (df2.groupby(["card_role", "card_rank", "rank_name", "rank_pts"])[TARGET]
                .agg(media="mean", std="std", n="count")
                .round(3)
                .reset_index()
                .sort_values(["card_role", "media"], ascending=[True, False]))

    out  = _h(2, "Valore delle Carte per Ruolo")
    out += textwrap.dedent("""\
        - **briscola**: carta del seme briscola
        - **lead**: carta del seme d'apertura (≠ briscola)
        - **altro**: carta di seme neutro

        """)
    for role in ["briscola", "lead", "altro"]:
        sub = pivot[pivot["card_role"] == role][
            ["rank_name", "rank_pts", "media", "std", "n"]
        ].rename(columns={"rank_name": "Carta", "rank_pts": "Val.Pt",
                          "media": "Δpunti medio", "std": "σ", "n": "Freq."})
        out += _h(3, f"Carte {role.capitalize()}")
        out += _table(sub) + "\n"
    return out


def _section_winning_cards(df: pd.DataFrame) -> str:
    df2 = df.copy()
    df2["won_turn"]  = (df2["seat"] == df2["turn_winner_seat"]).astype(int)
    df2["card_role"] = np.where(
        df2["card_is_briscola"] == 1, "briscola",
        np.where(df2["card_is_lead"] == 1, "lead", "altro")
    )
    df2["rank_name"] = df2["card_rank"].map(RANK_NAME)

    stats = (df2.groupby(["card_role", "rank_name", "card_rank"])
                .agg(win_rate=("won_turn", "mean"),
                     avg_pts_won=("turn_pts",
                                  lambda s: s[df2.loc[s.index, "won_turn"] == 1].mean()),
                     n=("won_turn", "count"))
                .round(3)
                .reset_index()
                .sort_values(["card_role", "win_rate"], ascending=[True, False]))

    out  = _h(2, "Carte che Vincono i Turni")
    out += "Win-rate = frequenza con cui quella carta vince il turno corrente.\n\n"
    for role in ["briscola", "lead", "altro"]:
        sub = stats[stats["card_role"] == role][
            ["rank_name", "win_rate", "avg_pts_won", "n"]
        ].rename(columns={"rank_name": "Carta",
                          "win_rate": "Win-rate",
                          "avg_pts_won": "Pt medi vinti",
                          "n": "Freq."})
        out += _h(3, f"Ruolo: {role.capitalize()}")
        out += _table(sub) + "\n"
    return out


def _section_briscola_selection(df: pd.DataFrame) -> str:
    sel = df[(df["turn_num"] == 1) & (df["play_order"] == 0)].copy()

    by_suit = (sel.groupby("briscola_suit")[TARGET]
                  .agg(media="mean", n="count")
                  .round(3)
                  .reset_index()
                  .sort_values("media", ascending=False))
    by_suit.columns = ["Seme Briscola", "Δpunti medio", "N"]

    briscola_rank_cols = [f"hand_briscola_{r}" for r in _RANKS]
    available = [c for c in briscola_rank_cols if c in sel.columns]
    if available:
        corr = sel[available + [TARGET]].corr()[TARGET].drop(TARGET)
        corr.index = [RANK_NAME[int(c.split("_")[-1])] for c in corr.index]
        corr = corr.sort_values(ascending=False).reset_index()
        corr.columns = ["Carta in mano", "Corr. con Δpunti"]
    else:
        corr = pd.DataFrame()

    out  = _h(2, "Strategia Briscola")
    out += _h(3, "Δpunti medio per seme scelto")
    out += _table(by_suit) + "\n"
    out += textwrap.dedent("""\
        > I semi con Δpunti positivo sono quelli dove il selettore ha in genere
        > carte forti. La differenza assoluta è piccola perché il seme è neutralizzato
        > nell'encoding — conta soprattutto **quali ranghi** possiedi in quel seme.

        """)

    if not corr.empty:
        out += _h(3, "Correlazione tra carte in mano (briscola) e risultato")
        out += _table(corr) + "\n"
        top_pos = corr[corr["Corr. con Δpunti"] > 0]["Carta in mano"].tolist()
        out += f"**Carte da preferire come briscola:** {', '.join(top_pos) if top_pos else '—'}\n\n"

    return out


def _section_declarations(df: pd.DataFrame) -> str:
    leads = df[df["is_lead"] == 1].copy()
    leads["decl_label"] = leads["declaration"].astype(str).replace({"": "nessuna", "nan": "nessuna"})

    stats = (leads.groupby("decl_label")[TARGET]
                  .agg(media="mean", std="std", n="count")
                  .round(3)
                  .reset_index()
                  .sort_values("media", ascending=False))
    stats.columns = ["Dichiarazione", "Δpunti medio", "σ", "Freq."]
    stats["Freq. %"] = (stats["Freq."] / stats["Freq."].sum() * 100).round(1)

    decl_cards = (leads[leads["decl_label"] != "nessuna"]
                  .groupby(["decl_label", "card_rank"])
                  .size()
                  .reset_index(name="n")
                  .assign(rank_name=lambda d: d["card_rank"].map(RANK_NAME))
                  .sort_values(["decl_label", "n"], ascending=[True, False]))

    out  = _h(2, "Dichiarazioni (busso / striscio / volo)")
    out += _table(stats) + "\n"
    out += _h(3, "Carte usate per dichiarare")
    for decl in ["busso", "striscio", "volo"]:
        sub = decl_cards[decl_cards["decl_label"] == decl][["rank_name", "n"]]
        sub.columns = ["Carta", "N"]
        if not sub.empty:
            out += f"**{decl.capitalize()}:**\n"
            out += _table(sub) + "\n"
    return out


def _section_play_order(df: pd.DataFrame) -> str:
    stats = (df.groupby("play_order")[TARGET]
               .agg(media="mean", std="std", n="count")
               .round(3)
               .reset_index())
    stats.columns = ["Posizione (0=apre)", "Δpunti medio", "σ", "N"]

    out  = _h(2, "Effetto della Posizione nel Turno")
    out += _table(stats) + "\n"

    medians = df.groupby("play_order")[TARGET].mean()
    best  = int(medians.idxmax())
    worst = int(medians.idxmin())
    pos_names = {0: "aprire (lead)", 1: "secondo", 2: "terzo", 3: "chiudere (last)"}
    out += (f"> Posizione più vantaggiosa: **{pos_names[best]}** (Δ={medians[best]:.3f})\n"
            f"> Posizione meno vantaggiosa: **{pos_names[worst]}** (Δ={medians[worst]:.3f})\n\n")
    return out


def _section_turn_winner_patterns(df: pd.DataFrame) -> str:
    df2 = df.copy()
    winners = df2[df2["seat"] == df2["turn_winner_seat"]].copy()
    winners["card_role"] = np.where(
        winners["card_is_briscola"] == 1, "briscola",
        np.where(winners["card_is_lead"] == 1, "lead", "altro")
    )

    role_dist = (winners["card_role"]
                 .value_counts(normalize=True)
                 .mul(100).round(1)
                 .reset_index())
    role_dist.columns = ["Tipo carta vincente", "% vittorie"]

    high_val_wins = winners[winners["turn_pts"] >= 6].copy()
    high_role = (high_val_wins["card_role"]
                 .value_counts(normalize=True)
                 .mul(100).round(1)
                 .reset_index())
    high_role.columns = ["Tipo carta vincente", "% vittorie (turni ≥6pt)"]

    out  = _h(2, "Pattern di Vittoria dei Turni")
    out += _h(3, "Tipo di carta vincente")
    out += _table(role_dist) + "\n"
    out += _h(3, "Nei turni ad alto valore (≥ 6 punti)")
    out += _table(high_role) + "\n"

    hv_rank = (high_val_wins.groupby(["card_role", "card_rank"])
                             .size()
                             .reset_index(name="n")
                             .assign(rank_name=lambda d: d["card_rank"].map(RANK_NAME))
                             .sort_values(["card_role", "n"], ascending=[True, False]))
    out += _h(3, "Ranghi vincenti nei turni ad alto valore")
    for role in ["briscola", "lead"]:
        sub = hv_rank[hv_rank["card_role"] == role][["rank_name", "n"]]
        sub.columns = ["Carta", "N"]
        if not sub.empty:
            out += f"**{role.capitalize()}:**\n"
            out += _table(sub) + "\n"
    return out


def _section_hand_strength(df: pd.DataFrame) -> str:
    first_play = (df.sort_values("turn_num")
                    .groupby(["game_id", "round_num", "seat"])
                    .first()
                    .reset_index())

    briscola_cols = [f"hand_briscola_{r}" for r in _RANKS]
    lead_cols     = [f"hand_lead_{r}"     for r in _RANKS]
    other_cols    = [f"hand_other_{r}_count" for r in _RANKS]
    available     = [c for c in briscola_cols + lead_cols + other_cols
                     if c in first_play.columns]
    if not available:
        return ""

    corr = (first_play[available + [TARGET]]
            .corr()[TARGET]
            .drop(TARGET)
            .sort_values(ascending=False))

    top = corr.head(10).reset_index()
    top.columns = ["Feature", "Corr. Δpunti"]
    bot = corr.tail(10).reset_index()
    bot.columns = ["Feature", "Corr. Δpunti"]

    def _friendly(feat: str) -> str:
        parts = feat.split("_")
        rank  = RANK_NAME.get(int(parts[-1]) if parts[-1].isdigit() else 0, parts[-1])
        role  = parts[1] if len(parts) > 1 else ""
        return f"{rank} ({role})"

    top["Feature"] = top["Feature"].apply(_friendly)
    bot["Feature"] = bot["Feature"].apply(_friendly)

    out  = _h(2, "Forza della Mano")
    out += "Correlazione tra le carte in mano all'inizio del round e il Δpunti finale.\n\n"
    out += _h(3, "Carte che aumentano il Δpunti (positive)")
    out += _table(top) + "\n"
    out += _h(3, "Carte che abbassano il Δpunti (negative)")
    out += _table(bot) + "\n"
    return out


def _section_shap(model, X: pd.DataFrame, max_rows: int = 5000) -> str:
    try:
        import shap
    except ImportError:
        return (
            _h(2, "Analisi SHAP (non disponibile)")
            + "> Installa `shap` per l'analisi dei contributi per-feature: "
              "`uv add shap`\n\n"
        )

    sample = X.sample(min(max_rows, len(X)), random_state=42)
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(sample)

    mean_abs = pd.Series(np.abs(shap_values).mean(axis=0), index=sample.columns)
    top = mean_abs.sort_values(ascending=False).head(20).reset_index()
    top.columns = ["Feature", "|SHAP| medio"]

    out  = _h(2, "Analisi SHAP — Contributo per Feature")
    out += f"Calcolato su {len(sample):,} campioni.\n\n"
    out += _table(top.round(4)) + "\n"
    return out


# ── Entry point ────────────────────────────────────────────────────────────────

def analyze(data_path: Path, model_path: Path, out_path: Path) -> None:
    df = _load_raw(data_path)
    model = joblib.load(model_path)
    log.info("Model loaded from %s", model_path)

    X, y = _load_for_model(df)

    sections = [
        _h(1, "Report Strategie — Marafone ML"),
        f"> Generato da `{data_path.name}` · modello `{model_path.name}`\n\n",
        _section_overview(df),
        _section_model_metrics(model, X, y),
        _section_feature_importance(model, X, config.ANALYSIS_TOP_FEATURES),
        _section_card_value(df),
        _section_winning_cards(df),
        _section_briscola_selection(df),
        _section_declarations(df),
        _section_play_order(df),
        _section_turn_winner_patterns(df),
        _section_hand_strength(df),
    ]
    if config.ANALYSIS_SHAP:
        sections.append(_section_shap(model, X))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(sections), encoding="utf-8")
    log.info("Report → %s", out_path)
