# RL Training — Experiments Log

## Summary

| Run | Key config | Peak vs heuristic | Outcome |
|-----|-----------|-------------------|---------|
| R1 | baseline | ~23% | plateau |
| R2 | more episodes + LR decay | ~23% | plateau |
| R3 | new arch (wrong value head) | ~18% then collapse | worse |
| R4 | new arch (fixed) | ~17% | plateau |
| R5 | BC warm-start + 25% heuristic | 53% → collapse to 29% | death spiral |
| R6 | BC warm-start + 75% heuristic | 55% → collapse to 43% | death spiral (slower) |
| R7 | BC + 75% heuristic + always-vs-heuristic eval + round tournament | 51.8% (v4) → 48.8% (v8) | slow drift |
| R8 | R7 + 100% heuristic (no self-play) | in progress | — |

---

## R1 — Baseline

**Config:** 1000 eps/iter · 50% heuristic · 256×3 model · CLIP_EPS=0.2 · flat LR 3e-4 · no residuals

**Curve:** v1=4% → v9=10.8% → plateau 18–23% → v29=19.6%

**Issues:**
- Slow initial learning (~1pp/iter)
- Hard plateau at ~20–23%
- Oscillations ±4pp (CI width ~3.5pp, partially noise)
- Two anomalous slow runs (v7: 7h, v10: 26min) — likely torch.compile cold start or process hang

**Diagnosis:** Thin gradient signal (1000 eps = ~40k decisions, PPO running 6 epochs on same small batch). LR flat at 3e-4 forever → overshooting. No residuals limits depth.

---

## R2 — More episodes + LR decay

**Changes vs R1:**
- `N_EPISODES_PER_ITER`: 1000 → 2000
- `HEURISTIC_OPPONENT_FRAC`: 0.50 → 0.25
- LR decay: `3e-4 × 0.97^(iter−3)` floored at `5e-5`

**Curve:** v1=4.4% → v9=18% → plateau 18–23%

**Result:** 3× faster gain rate early. Same ceiling. Self-play degradation starting (v13 regression). Plateau confirmed not a gradient-signal problem — structural.

---

## R3 — New architecture, attempt 1 (wrong)

**Changes vs R2:**
- `HIDDEN_DIM`: 256 → 512, `N_LAYERS`: 3 → 4
- `CLIP_EPS`: 0.2 → 0.15
- Value head: pool **raw inputs** instead of trunk outputs ← MISTAKE
- Residuals: post-norm style (unstable)

**Curve:** v3=12% → v9=18% → collapse → v25=16%

**Issue:** Pooling raw inputs for value head is too weak. Raw mean ≠ V(s). Advantage estimates garbage → harmful PPO updates → collapse after v9.

**Lesson:** Pool trunk outputs for value head (original approach was correct).

---

## R4 — New architecture, fixed

**Changes vs R3:**
- Value head: reverted to pool **trunk outputs**
- Residuals: pre-norm style `h = h + GELU(linear(norm(h)))` — more stable

**Curve:** 13–17% range. Plateau at lower level than R1/R2.

**Diagnosis:** Architecture correct but not sufficient. Ceiling is not an architecture problem — PPO learning to beat a strong heuristic from random init is fundamentally hard (sparse positive signal when losing 85% of games).

---

## BC Pre-training (introduced before R5)

**What:** Generate 10k heuristic-vs-heuristic games → cross-entropy train policy to imitate heuristic → save as `rl_v0`.

**Result:** Loss 0.54 → 0.28 over 10 epochs (~75% accuracy on heuristic moves). Model starts near-heuristic level.

**Files:** `rl_bc.py`, `train_rl_bc.bat`. Output: `RL_ARTIFACTS_DIR/rl_v0/`. Batch `--reset` preserves rl_v0.

---

## R5 — BC + 25% heuristic + champion-based tournament

**Config:** rl_v0 warm-start · `HEURISTIC_FRAC=0.25` · tournament vs latest promoted RL model

**Curve:**
```
v1=48% vs heuristic → PROMOTED
v2=53.9% → PROMOTED
v5=53.4% vs rl_v2 → PROMOTED
v6–v35: 49% → 44% → 35% → 29%  (collapse)
```

**Issue 1 — self-play death spiral:** After v5 promoted, champion=rl_v5. PPO trains 75% self-play (current policy vs itself). Each bad update degrades the self-play partner → next iter trains against weaker partner → learns to exploit weak opponent → forgets real strategy. Cycle repeats.

**Issue 2 — Goodhart's Law:** Training objective = beat heuristic. Evaluation = beat rl_v5 (fixed specific opponent). Policy over-specialises to beat rl_v5 via narrow exploits, losing general skill.

---

## R6 — BC + 75% heuristic + champion-based tournament

**Change:** `HEURISTIC_FRAC`: 0.25 → 0.75

**Curve:**
```
v1=53% PROMOTED · v3=55.9% PROMOTED
v10=46.5% vs rl_v3 (losing)
v14=43.9%
```

**Result:** Spiral slowed by ~4 versions, not stopped. 25% self-play still enough for bad gradient. Champion-based evaluation still creates false ceiling (rl_v3 possibly promoted with noisy inflated score → unreachable benchmark for successors).

---

## R7 — BC + 75% heuristic + always-heuristic eval + round tournament (current)

**Changes:**

*Pipeline (`rl_pipeline.py`):*
- Always evaluate vs heuristic regardless of promoted RL models
- Promote only when `CI_lo > 0.505` AND `win_rate > previous_best_vs_heuristic`
- Best-ever win rate stored in pointer file (version\nwin_rate)

*Tournament (`rl_tournament.py`):*
- Round-based: one deal = one round (agents can't leverage cross-round info → round-win rate is the correct metric)
- Systematic seat rotation `briscola_selector = i % 4` → every seat leads exactly N/4 rounds, positional bias analytically eliminated
- Paired design: `rng2 = random.Random(seed)` same deals replayed with sides swapped → card luck fully canceled
- `TOURNEY_GAMES = 8000` rounds (same wall-clock as 2000 full games, tighter CI)

*Engine (`engine.py`):*
- `Deck.shuffle(rng=None)` — accepts explicit rng for reproducibility

**Rationale:**
- Always-heuristic eval aligns measurement with training objective → no Goodhart drift
- Best-ever promotion ensures monotone improvement signal
- Round tournament is lower variance and faster

**Curve (v1–v8):**
```
v1=48.6% ✗ · v2=50.2% ✗ · v3=51.6% ✓ · v4=51.8% ✓ (peak)
v5=51.5% ✗ · v6=50.7% ✗ · v7=49.7% ✗ · v8=48.8% ✗
```

**Issue — slow self-play drift:** 25% self-play (500 games/iter) causes ~1pp/iter systematic degradation after the peak. Mechanism: once a version fails to promote, next iter trains against the same slightly-degraded policy in self-play → PPO shifts weights to exploit the self-play partner → strategy drifts away from heuristic-optimal. Compounds each iteration. Masked by small CI (~1.1pp half-width) so looks like noise at first.

**Key difference from R5/R6:** Eval/promotion is correct (always vs heuristic, best-ever gate). Self-play is the only remaining corruption source.

**Status:** Closed. Superseded by R8.

---

## R8 — BC + 100% heuristic (no self-play)

**Changes vs R7:**
- `HEURISTIC_OPPONENT_FRAC`: 0.75 → 1.0

**Rationale:** Eliminates self-play drift entirely. Training objective = evaluation objective = beat heuristic. No degraded self-play partner can corrupt gradients. The "self-play explores novel lines" benefit is theoretical — 8 iterations of R7 showed no empirical benefit, only harm.

**Start:** rl_v8 (continuing chain, not reset).

**Status:** In progress.

---

## Config history

| Parameter | R1 baseline | R7 | R8 (current) |
|-----------|------------|-----|--------------|
| `HIDDEN_DIM` | 256 | 512 | 512 |
| `N_LAYERS` | 3 | 4 | 4 |
| Residuals | none | pre-norm | pre-norm |
| `N_EPISODES_PER_ITER` | 1000 | 2000 | 2000 |
| `HEURISTIC_OPPONENT_FRAC` | 0.50 | 0.75 | **1.0** |
| `CLIP_EPS` | 0.2 | 0.15 | 0.15 |
| `ENTROPY_COEF` | 0.05 | 0.05 | 0.05 |
| LR schedule | flat 3e-4 | warmup 3 iters → decay 0.97^step → floor 5e-5 | same |
| Tournament unit | full game | single round | single round |
| Tournament games | 2000 | 8000 rounds | 8000 rounds |
| Seat balance | statistical (swap sides) | deterministic (i % 4) | same |
| Eval opponent | latest champion | always heuristic | same |
| Promotion criterion | CI_lo > 0.505 vs champion | CI_lo > 0.505 vs heuristic AND WR > best-ever | same |
| Warm-start | random init | BC pre-trained (rl_v0) | same |
