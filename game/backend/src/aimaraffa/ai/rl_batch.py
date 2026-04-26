"""Batch RL pipeline runner — N sequential iterations with resume and report.

Usage (from repo root)::

    train_rl_batch.bat               # 5 iterations (default)
    train_rl_batch.bat --n 10        # 10 iterations
    train_rl_batch.bat --reset       # clear saved state and restart

Progress is saved after each iteration to ``RL_ARTIFACTS_DIR/rl_batch_state.json``.
A Markdown report is written to ``RL_ARTIFACTS_DIR/rl_batch_report.md``.

Identical structure to batch.py — just wired to the RL pipeline and version system.
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

from . import config_rl as cfg
from .config_rl import RL_ARTIFACTS_DIR, RL_MODEL_FILENAME
from .rl_pipeline import run as run_one
from .rl_versions import latest_rl_version, rl_production_version

logger = logging.getLogger(__name__)

_STATE_FILE  = RL_ARTIFACTS_DIR / "rl_batch_state.json"
_REPORT_FILE = RL_ARTIFACTS_DIR / "rl_batch_report.md"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"


# ── State persistence ──────────────────────────────────────────────────────────

def _load_state() -> dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, KeyError):
            logger.warning("Corrupt RL batch state — starting fresh.")
    return {}


def _save_state(state: dict) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    tmp.replace(_STATE_FILE)


# ── Tournament result parser ───────────────────────────────────────────────────

def _parse_tournament(version_dir: Path) -> dict | None:
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
                info["ci_lo"]    = float(m.group(2))
                info["ci_hi"]    = float(m.group(3))
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


# ── Report generator ───────────────────────────────────────────────────────────

def _generate_report(state: dict) -> str:
    iters    = state.get("iterations", [])
    n_ok     = sum(1 for it in iters if it["status"] == "ok")
    n_err    = sum(1 for it in iters if it["status"] == "error")
    n_req    = state.get("n_requested", "?")
    total_s  = sum(it.get("duration_sec", 0) for it in iters)

    if n_err:
        badge = f"✗ STOPPED — {n_ok}/{n_req} completed, 1 error"
    elif isinstance(n_req, int) and n_ok >= n_req:
        badge = f"✓ COMPLETED ({n_ok}/{n_req})"
    else:
        badge = f"… IN PROGRESS ({n_ok}/{n_req})"

    lines = [
        "# RL Batch Training Report",
        "",
        f"**{badge}**",
        "",
        "| | |",
        "|---|---|",
        f"| Started  | {state.get('started', '—')} |",
        f"| Finished | {state.get('finished', '—')} |",
        f"| Total duration | {_fmt_duration(total_s)} |",
        f"| Iterations | {n_ok} ok"
        + (f", {n_err} error" if n_err else "")
        + f" / {n_req} requested |",
        "",
        "## Results",
        "",
        "| # | Version | Source | Opponent | Status | Win Rate | 95% CI | Margin | Promoted | Duration |",
        "|--:|---------|--------|----------|:------:|----------|--------|-------:|:--------:|---------:|",
    ]

    for i, it in enumerate(iters, 1):
        ver      = it.get("version", "?")
        src      = it.get("source", "?")
        status   = {"ok": "✓", "error": "✗"}.get(it.get("status", ""), "?")
        dur      = _fmt_duration(it["duration_sec"]) if it.get("duration_sec") else "—"
        promoted = "✓" if it.get("promoted") else ""
        tour     = it.get("tournament")

        if tour and tour.get("win_rate") is not None:
            opp    = tour.get("opponent", "?")
            wr     = f"{tour['win_rate']:.1f}%"
            ci     = f"{tour['ci_lo']:.1f}% – {tour['ci_hi']:.1f}%"
            margin = f"{tour['avg_margin']:+.1f}" if tour.get("avg_margin") is not None else "—"
        else:
            opp, wr, ci, margin = "—", "—", "—", "—"

        lines.append(
            f"| {i} | {ver} | {src} | {opp} | {status} | {wr} | {ci} | {margin} | {promoted} | {dur} |"
        )

    lines.append("")
    prod = rl_production_version() or "(none)"
    promoted_list = [it["version"] for it in iters if it.get("promoted")]
    lines.extend([
        "## Production",
        "",
        f"Current RL production model: **{prod}**",
    ])
    if promoted_list:
        lines.append("")
        lines.append(f"Promoted during batch: {' → '.join(promoted_list)}")
    lines.append("")

    errors = [it for it in iters if it.get("status") == "error"]
    if errors:
        lines.extend(["## Errors", ""])
        for it in errors:
            lines.extend([f"### {it.get('version', '?')}", "", "```",
                          it.get("error", "unknown"), "```", ""])

    lines.extend([
        "## Config",
        "",
        "| Parameter | Value |",
        "|-----------|-------|",
        f"| Episodes/iter | {cfg.N_EPISODES_PER_ITER:,} |",
        f"| Heuristic frac | {cfg.HEURISTIC_OPPONENT_FRAC:.0%} |",
        f"| PPO epochs | {cfg.PPO_EPOCHS} |",
        f"| Mini-batch | {cfg.MINI_BATCH_SIZE:,} |",
        f"| Tournament games | {cfg.TOURNEY_GAMES:,} |",
        f"| Promote threshold | CI lower ≥ {cfg.PROMOTE_MIN_CI_LOWER} |",
        f"| Network | hidden={cfg.HIDDEN_DIM}, layers={cfg.N_LAYERS} |",
        f"| Device | {cfg.DEVICE} |",
        "",
    ])

    return "\n".join(lines)


# ── Main runner ────────────────────────────────────────────────────────────────

def run_rl_batch(n_iterations: int = 5, reset: bool = False) -> None:
    if reset:
        import shutil
        import zipfile
        from .config_rl import RL_PRODUCTION_POINTER, RL_PROMOTION_LOG, RL_PRODUCTION_MODEL_PATH

        # Zip everything before wiping so accidental resets are recoverable.
        _backup_dir = RL_ARTIFACTS_DIR.parent / "training_rl_backups"
        _backup_dir.mkdir(parents=True, exist_ok=True)
        _ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        _backup_zip = _backup_dir / f"pre_reset_{_ts}.zip"
        _files_backed_up = 0
        with zipfile.ZipFile(_backup_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for src in (RL_ARTIFACTS_DIR, RL_PRODUCTION_POINTER.parent):
                if src.exists():
                    for f in src.rglob("*"):
                        if f.is_file():
                            zf.write(f, f.relative_to(src.parent))
                            _files_backed_up += 1
        if _files_backed_up:
            logger.info("Backup saved → %s (%d files)", _backup_zip, _files_backed_up)
        else:
            _backup_zip.unlink(missing_ok=True)
            logger.info("Nothing to back up — artifacts empty.")

        if _STATE_FILE.exists():
            _STATE_FILE.unlink()
        # Wipe all rl_v* version directories so latest_rl_version() returns (0, None).
        if RL_ARTIFACTS_DIR.exists():
            import re as _re
            for child in RL_ARTIFACTS_DIR.iterdir():
                if child.is_dir() and _re.match(r"^rl_v\d+$", child.name):
                    if child.name == "rl_v0":
                        logger.info("Preserving BC pre-trained model: %s", child)
                        continue
                    shutil.rmtree(child)
                    logger.info("Deleted %s", child)
        # Clear production pointer and log so promotion state is clean.
        for f in (RL_PRODUCTION_POINTER, RL_PROMOTION_LOG, RL_PRODUCTION_MODEL_PATH):
            if f.exists():
                f.unlink()
                logger.info("Deleted %s", f)
        logger.info("Full reset complete — starting from scratch.")

    state = _load_state()

    if state.get("target_version") is not None:
        target = state["target_version"]
        original_start = target - state.get("n_requested", target)
        new_target = original_start + n_iterations
        if new_target > target:
            target = new_target
            state["target_version"] = target
            state["n_requested"]    = n_iterations
            _save_state(state)
            logger.info("Extending RL batch target to rl_v%d.", target)

        if state.get("iterations") and state["iterations"][-1].get("status") == "error":
            failed = state["iterations"].pop()
            logger.info("Retrying previously failed: %s", failed["version"])
            _save_state(state)

        current_num, _ = latest_rl_version()
        remaining = target - current_num
        if remaining <= 0:
            logger.info("RL batch already complete (target rl_v%d reached).", target)
            state["finished"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _save_state(state)
            report = _generate_report(state)
            _REPORT_FILE.write_text(report, encoding="utf-8")
            print(report)
            return
        logger.info(
            "Resuming RL batch → rl_v%d (%d remaining).  Use --reset to start over.",
            target, remaining,
        )
    else:
        current_num, _ = latest_rl_version()
        target = current_num + n_iterations
        state.update({
            "started":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "target_version": target,
            "n_requested":    n_iterations,
            "iterations":     [],
        })
        _save_state(state)
        logger.info("RL batch: %d iterations → target rl_v%d", n_iterations, target)

    try:
        while True:
            current_num, current_model = latest_rl_version()
            next_num = current_num + 1
            if next_num > target:
                break

            src_label = "scratch" if not current_model else (
                "production" if current_num == 0 else f"rl_v{current_num}"
            )

            n_done  = len(state.get("iterations", []))
            n_total = state.get("n_requested", "?")
            logger.info("━" * 62)
            logger.info("  RL BATCH [%d/%s]  %s → rl_v%d", n_done + 1, n_total, src_label, next_num)
            logger.info("━" * 62)

            t0           = time.time()
            prod_before  = rl_production_version()

            try:
                run_one()
            except Exception:
                elapsed = time.time() - t0
                logger.error("rl_v%d FAILED after %s", next_num, _fmt_duration(elapsed))
                state.setdefault("iterations", []).append({
                    "version":      f"rl_v{next_num}",
                    "source":       src_label,
                    "status":       "error",
                    "promoted":     False,
                    "duration_sec": round(elapsed, 1),
                    "error":        tb_mod.format_exc(),
                })
                _save_state(state)
                break

            elapsed     = time.time() - t0
            prod_after  = rl_production_version()
            promoted    = prod_after != prod_before

            ver_dir = RL_ARTIFACTS_DIR / f"rl_v{next_num}"
            tour    = _parse_tournament(ver_dir)

            state.setdefault("iterations", []).append({
                "version":      f"rl_v{next_num}",
                "source":       src_label,
                "status":       "ok",
                "promoted":     promoted,
                "duration_sec": round(elapsed, 1),
                "tournament":   tour,
            })
            _save_state(state)
            logger.info("rl_v%d done in %s — promoted=%s",
                        next_num, _fmt_duration(elapsed), promoted)

    except KeyboardInterrupt:
        logger.info("\nInterrupted — progress saved.  Re-run to resume.")

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
        level   = logging.INFO,
        format  = "%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Run N sequential RL pipeline iterations with resume support.",
    )
    parser.add_argument("--n", type=int, default=5,
                        help="Number of iterations (default: 5)")
    parser.add_argument("--reset", action="store_true",
                        help="Discard previous batch state and start fresh")
    args = parser.parse_args()
    run_rl_batch(n_iterations=args.n, reset=args.reset)
