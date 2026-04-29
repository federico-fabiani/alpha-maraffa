"""Hyperparameters for the AlphaZero-style Marafone training pipeline.

Independent of ``config_rl.py`` so the legacy PPO stack keeps working
unchanged while we iterate on this one.
"""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
_BACKEND_ROOT = Path(__file__).resolve().parents[3]   # …/backend
_SRC_ROOT     = Path(__file__).resolve().parents[2]   # …/backend/src

AZ_ARTIFACTS_DIR = _BACKEND_ROOT / "artifacts" / "training_az"

AZ_MODEL_FILENAME  = "marafone_az_model.pt"
AZ_ONNX_FILENAME   = "marafone_az_model.onnx"

AZ_PRODUCTION_MODEL_PATH = _SRC_ROOT / "scripts" / "artifacts" / AZ_MODEL_FILENAME
AZ_PRODUCTION_ONNX_PATH  = _SRC_ROOT / "scripts" / "artifacts" / AZ_ONNX_FILENAME
AZ_PRODUCTION_POINTER    = _SRC_ROOT / "scripts" / "artifacts" / "AZ_PRODUCTION"

# ── Network ────────────────────────────────────────────────────────────────────
HIDDEN_DIM = 256
N_LAYERS   = 4

# ── ISMCTS during self-play ────────────────────────────────────────────────────
SP_N_SIMULATIONS      = 64    # tree expansions per decision
SP_N_DETERMINIZATIONS = 16    # opponent-hand resamples per decision
SP_C_PUCT             = 1.5
SP_DIRICHLET_ALPHA    = 0.3
SP_DIRICHLET_EPS      = 0.25  # noise mixed into root prior during self-play
SP_TEMPERATURE        = 1.0   # action sampling temperature for first 4 turns
SP_TEMP_FALLOFF_TURN  = 4     # after this turn argmax-sample (temp→0)

# ── ISMCTS at evaluation ───────────────────────────────────────────────────────
EVAL_N_SIMULATIONS      = 100
EVAL_N_DETERMINIZATIONS = 25
EVAL_C_PUCT             = 1.5

# ── Self-play data collection ──────────────────────────────────────────────────
N_ROUNDS_PER_ITER       = 1_000   # one round = one independent imperfect-info game
N_WORKERS               = 8
ROUNDS_PER_WORKER_CHUNK = 8       # imap_unordered chunk size

# ── Training ───────────────────────────────────────────────────────────────────
LEARNING_RATE   = 3e-4
WEIGHT_DECAY    = 1e-4
N_EPOCHS        = 4
MINI_BATCH_SIZE = 1_024
VALUE_LOSS_COEF = 1.0
GRAD_CLIP_NORM  = 1.0

# Replay-buffer style: keep last K iterations of self-play data to stabilise.
REPLAY_BUFFER_ITERS = 3

# ── Tournament / promotion ─────────────────────────────────────────────────────
TOURNEY_GAMES        = 4_000   # rounds (multiple of 8 for seat × side balance)
TOURNEY_SEED         = 42
PROMOTE_MIN_CI_LOWER = 0.505

# ── Hardware ───────────────────────────────────────────────────────────────────
DEVICE      = "cuda"
USE_AMP     = True
AMP_DTYPE   = "bfloat16"
USE_TF32    = True
