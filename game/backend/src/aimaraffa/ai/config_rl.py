"""Hyperparameters for the PPO-based RL training pipeline.

Mirrors the structure of config.py — one source of truth per pipeline.
"""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
_BACKEND_ROOT = Path(__file__).resolve().parents[3]   # …/backend
_SRC_ROOT     = Path(__file__).resolve().parents[2]   # …/backend/src

RL_ARTIFACTS_DIR = _BACKEND_ROOT / "artifacts" / "training_rl"

RL_MODEL_FILENAME   = "marafone_rl_model.pt"
RL_ONNX_FILENAME    = "marafone_rl_model.onnx"
RL_REPORT_FILENAME  = "strategy_report.md"

RL_PRODUCTION_MODEL_PATH = _SRC_ROOT / "scripts" / "artifacts" / RL_MODEL_FILENAME
RL_PRODUCTION_ONNX_PATH  = _SRC_ROOT / "scripts" / "artifacts" / RL_ONNX_FILENAME
RL_PRODUCTION_POINTER    = _SRC_ROOT / "scripts" / "artifacts" / "RL_PRODUCTION"
RL_PROMOTION_LOG         = _SRC_ROOT / "scripts" / "artifacts" / "RL_PROMOTION_LOG"

# ── Neural network ─────────────────────────────────────────────────────────────
# Input dim = len(_COL_NAMES) minus the drop-set columns excluded at inference
# time.  At runtime, rl_model.py imports N_FEATURES from ml_agent.
HIDDEN_DIM = 512
N_LAYERS   = 4    # trunk depth (1 input_proj + N_LAYERS-1 residual blocks)

# ── PPO hyperparameters ────────────────────────────────────────────────────────
LEARNING_RATE  = 3e-4
CLIP_EPS       = 0.15    # PPO clip coefficient — tighter to reduce win-rate oscillation
ENTROPY_COEF   = 0.05    # entropy bonus — higher early to prevent collapse on card game
VALUE_COEF     = 0.5     # critic loss weight
MAX_GRAD_NORM  = 0.5     # gradient clipping
GAE_LAMBDA     = 0.95    # GAE λ
GAMMA          = 1.0     # discount — set to 1.0 because episodes are short rounds

# ── Training loop ──────────────────────────────────────────────────────────────
N_EPISODES_PER_ITER = 2_000   # complete games per PPO iteration
PPO_EPOCHS          = 6       # update passes per collected batch
MINI_BATCH_SIZE     = 2_048   # decisions per gradient step (GPU has headroom)
N_WORKERS           = 8       # parallel CPU rollout workers (half of 16 cores)

# Fraction of training games played against the HeuristicAgent (for grounding).
# 1.0 = no self-play: eliminates the self-play drift spiral observed in R7
# (25% self-play caused ~1pp/iter systematic degradation after v4 peak).
HEURISTIC_OPPONENT_FRAC = 1.0

# ── Learning rate schedule ─────────────────────────────────────────────────────
# Linear warmup for the first WARMUP_ITERS pipeline iterations, then
# exponential decay: lr = max(LR_MIN, LR * LR_DECAY_GAMMA^(iter - WARMUP_ITERS))
WARMUP_ITERS    = 3
LR_DECAY_GAMMA  = 0.97   # per-iteration multiplicative decay after warmup
LR_MIN          = 5e-5   # floor — prevents LR collapsing to near zero

# ── Tournament / promotion ─────────────────────────────────────────────────────
TOURNEY_GAMES        = 8_000   # rounds (not games) — multiple of 8 for perfect seat×side balance
TOURNEY_SEED         = 42
PROMOTE_MIN_CI_LOWER = 0.505   # Wilson CI lower bound required for promotion

# ── Device & precision ─────────────────────────────────────────────────────────
DEVICE = "cuda"       # "cpu" or "cuda"

# Automatic Mixed Precision (BF16 on Ampere+ is lossless vs FP16 for training).
# Halves memory bandwidth pressure on the PPO update; free throughput.
USE_AMP = True        # False to disable; ignored when DEVICE="cpu"
AMP_DTYPE = "bfloat16"  # "bfloat16" (Ampere+) or "float16"

# TF32 — Ampere GPUs can compute FP32 matmuls at TF32 speed (10-bit mantissa).
# Negligible accuracy loss for RL; ~2-3× faster matmul.
USE_TF32 = True

# torch.compile the policy after loading.  First forward is slow (~30 s) but
# subsequent calls get ~20-40% faster.  Disable if triton not available.
USE_COMPILE = True
