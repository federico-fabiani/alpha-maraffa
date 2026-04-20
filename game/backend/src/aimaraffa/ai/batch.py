"""Batch pipeline runner — N sequential iterations with resume and overnight report.

Run it before bed, read ``batch_report.md`` in the morning.

Usage (from repo root)::

    train_batch.bat               # 5 iterations (default)
    train_batch.bat --n 10        # 10 iterations
    train_batch.bat --reset       # clear saved state and restart
    train_batch.bat --reset --n 8 # restart with 8 iterations
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
import traceback as tb_mod
from datetime import datetime
from pathlib import Path

from . import config
from .config import MODEL_FILENAME, TRAINING_ARTIFACTS_DIR
from .pipeline import run as run_one
from .versions import latest_version, production_version

logger = logging.getLogger(__name__)

_STATE_FILE = TRAINING_ARTIFACTS_DIR / "batch_state.json"
_REPORT_FILE = TRAINING_ARTIFACTS_DIR / "batch_report.md"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    return f"{m}m{s:02d}s"


# ── State persistence (atomic write) ──────────────────────────────────────────

def _load_state() -> dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, KeyError):
            logger.warning("Corrupt batch state file — starting fresh.")
    return {}


def _save_state(state: dict) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    tmp.replace(_STATE_FILE)


# ── Tournament result parsing ──────────────────────────────────────────────────

def _parse_tournament(version_dir: Path) -> dict | None:
    """Extract key metrics from the tournament text file written by pipeline."""
    files = list(version_dir.glob("tournament_*.txt"))
    if not files:
        return None
    text = files[0].read_text(encoding="utf-8")
    info: dict = {}
    for line in text.splitlines():
        s = line.strip()
        if "B =" in s:
            info["opponent"] = s.split("=", 1)[1].strip()
        elif "A win-rate" in s:
            m = re.search(r"([\d.]+)%\s*\[.*?([\d.]+)%\s*[-–]\s*([\d.]+)%", s)
            if m:
                info["win_rate"] = float(m.group(1))
                info["ci_lo"] = float(m.group(2))
                info["ci_hi"] = float(m.group(3))
        elif "Games total" in s:
            m = re.search(r":\s*(\d+)", s)
            if m:
                info["games"] = int(m.group(1))
        elif "Avg margin" in s:
            m = re.search(r"([+-]?[\d.]+)\s*points", s)
            if m:
                info["avg_margin"] = float(m.group(1))
        elif "Verdict" in s:
            info["verdict"] = s.split(":", 1)[1].strip()
    return info if info else None


# ── Report generation ──────────────────────────────────────────────────────────

def _generate_report(state: dict) -> str:
    iters = state.get("iterations", [])
    n_ok = sum(1 for it in iters if it["status"] == "ok")
    n_err = sum(1 for it in iters if it["status"] == "error")
    n_req = state.get("n_requested", "?")
    total_secs = sum(it.get("duration_sec", 0) for it in iters)

    if n_err:
        badge = f"✗ STOPPED — {n_ok}/{n_req} completed, 1 error"
    elif isinstance(n_req, int) and n_ok >= n_req:
        badge = f"✓ COMPLETED ({n_ok}/{n_req})"
    else:
        badge = f"… IN PROGRESS ({n_ok}/{n_req})"

    lines = [
        "# Batch Training Report",
        "",
        f"**{badge}**",
        "",
        "| | |",
        "|---|---|",
        f"| Started | {state.get('started', '—')} |",
        f"| Finished | {state.get('finished', '—')} |",
        f"| Total duration | {_fmt_duration(total_secs)} |",
        f"| Iterations | {n_ok} ok"
        + (f", {n_err} error" if n_err else "")
        + f" / {n_req} requested |",
        "",
        "## Results",
        "",
        "| # | Version | Source | Status | Win Rate | 95% CI | Margin | Promoted | Duration |",
        "|--:|---------|--------|:------:|----------|--------|-------:|:--------:|---------:|",
    ]

    for i, it in enumerate(iters, 1):
        ver = it.get("version", "?")
        src = it.get("source", "?")
        status = {"ok": "✓", "error": "✗"}.get(it.get("status", ""), "?")
        dur = _fmt_duration(it["duration_sec"]) if it.get("duration_sec") else "—"
        promoted = "✓" if it.get("promoted") else ""

        tour = it.get("tournament")
        if tour and tour.get("win_rate") is not None:
            wr = f"{tour['win_rate']:.1f}%"
            ci = f"{tour['ci_lo']:.1f}% – {tour['ci_hi']:.1f}%"
            margin = (
                f"{tour['avg_margin']:+.1f}"
                if tour.get("avg_margin") is not None
                else "—"
            )
        elif it.get("status") == "ok" and src == "random":
            wr, ci, margin = "—", "bootstrap", "—"
        else:
            wr, ci, margin = "—", "—", "—"

        lines.append(
            f"| {i} | {ver} | {src} | {status} | {wr} | {ci} | {margin} | {promoted} | {dur} |"
        )

    lines.append("")

    # Production
    prod = production_version() or "(none)"
    promoted_list = [it["version"] for it in iters if it.get("promoted")]
    lines.append("## Production")
    lines.append("")
    lines.append(f"Current production model: **{prod}**")
    if promoted_list:
        lines.append("")
        lines.append(f"Promoted during batch: {' → '.join(promoted_list)}")
    lines.append("")

    # Errors
    errors = [it for it in iters if it.get("status") == "error"]
    if errors:
        lines.append("## Errors")
        lines.append("")
        for it in errors:
            lines.append(f"### {it.get('version', '?')}")
            lines.append("")
            lines.append("```")
            lines.append(it.get("error", "unknown"))
            lines.append("```")
            lines.append("")

    # Config snapshot
    lines.extend([
        "## Config",
        "",
        "| Parameter | Value |",
        "|-----------|-------|",
        f"| Dataset games | {config.DATASET_GAMES:,} |",
        f"| Dataset ε | {config.DATASET_EPSILON} |",
        f"| Counterfactual | {'on' if config.COUNTERFACTUAL_ENABLED else 'off'}"
        f" (p={config.COUNTERFACTUAL_PROBABILITY},"
        f" alts={config.COUNTERFACTUAL_ALTERNATIVES},"
        f" rollouts={config.COUNTERFACTUAL_ROLLOUTS},"
        f" weight={config.COUNTERFACTUAL_WEIGHT}) |",
        f"| Analysis games | {config.ANALYSIS_GAMES:,} |",
        f"| Tournament games | {config.TOURNEY_GAMES:,} |",
        f"| Promote threshold | CI lower ≥ {config.PROMOTE_MIN_CI_LOWER} |",
        f"| XGBoost | {config.N_ESTIMATORS:,} trees, lr={config.LEARNING_RATE},"
        f" depth={config.MAX_DEPTH}, device={config.DEVICE} |",
        "",
    ])

    return "\n".join(lines)


# ── Main runner ────────────────────────────────────────────────────────────────

def run_batch(n_iterations: int = 5, reset: bool = False) -> None:
    """Run *n_iterations* pipeline steps, saving progress after each one."""

    if reset and _STATE_FILE.exists():
        _STATE_FILE.unlink()
        logger.info("Previous batch state cleared.")

    state = _load_state()

    # ── Determine target ───────────────────────────────────────────────────
    if state.get("target_version") is not None:
        # Resume
        target = state["target_version"]
        # Drop last entry if it was an error — we're retrying that version
        if state.get("iterations") and state["iterations"][-1].get("status") == "error":
            failed = state["iterations"].pop()
            logger.info("Retrying previously failed: %s", failed["version"])
            _save_state(state)
        current_num, _ = latest_version()
        remaining = target - current_num
        if remaining <= 0:
            logger.info("Batch already complete (target v%d reached).", target)
            state["finished"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _save_state(state)
            report = _generate_report(state)
            _REPORT_FILE.write_text(report, encoding="utf-8")
            print(report)
            return
        logger.info(
            "Resuming batch → v%d (%d remaining).  Use --reset to start over.",
            target, remaining,
        )
    else:
        # Fresh start
        current_num, _ = latest_version()
        target = current_num + n_iterations
        state.update({
            "started": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "target_version": target,
            "n_requested": n_iterations,
            "iterations": [],
        })
        _save_state(state)
        logger.info("Batch: %d iterations → target v%d", n_iterations, target)

    # ── Iteration loop ─────────────────────────────────────────────────────
    try:
        while True:
            current_num, current_model = latest_version()
            next_num = current_num + 1
            if next_num > target:
                break

            if not current_model:
                src_label = "random"
            elif current_num == 0:
                src_label = "production"
            else:
                src_label = f"v{current_num}"

            n_done = len(state.get("iterations", []))
            n_total = state.get("n_requested", "?")

            logger.info("━" * 62)
            logger.info("  BATCH [%d/%s]  %s → v%d", n_done + 1, n_total, src_label, next_num)
            logger.info("━" * 62)

            t0 = time.time()
            prod_before = production_version()

            try:
                run_one()
            except Exception:
                elapsed = time.time() - t0
                logger.error("v%d FAILED after %s", next_num, _fmt_duration(elapsed))
                state.setdefault("iterations", []).append({
                    "version": f"v{next_num}",
                    "source": src_label,
                    "status": "error",
                    "promoted": False,
                    "duration_sec": round(elapsed, 1),
                    "error": tb_mod.format_exc(),
                })
                _save_state(state)
                break  # next version depends on this one

            elapsed = time.time() - t0
            prod_after = production_version()
            promoted = prod_after != prod_before

            ver_dir = TRAINING_ARTIFACTS_DIR / f"v{next_num}"
            tour = _parse_tournament(ver_dir)

            state.setdefault("iterations", []).append({
                "version": f"v{next_num}",
                "source": src_label,
                "status": "ok",
                "promoted": promoted,
                "duration_sec": round(elapsed, 1),
                "tournament": tour,
            })
            _save_state(state)
            logger.info("v%d done in %s — promoted=%s",
                        next_num, _fmt_duration(elapsed), promoted)

    except KeyboardInterrupt:
        logger.info("\nInterrupted — progress saved.  Re-run to resume.")

    # ── Report ─────────────────────────────────────────────────────────────
    state["finished"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _save_state(state)

    report = _generate_report(state)
    _REPORT_FILE.write_text(report, encoding="utf-8")
    logger.info("Report → %s", _REPORT_FILE)
    print()
    print(report)


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Run N sequential pipeline iterations with resume support.",
    )
    parser.add_argument(
        "--n", type=int, default=5,
        help="Number of iterations (default: 5)",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Discard previous batch state and start fresh",
    )
    args = parser.parse_args()
    run_batch(n_iterations=args.n, reset=args.reset)
