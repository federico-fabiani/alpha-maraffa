"""Single source of truth for the training pipeline.

No CLI args — constants here are the contract between pipeline stages.
Tweak a value, re-run ``python -m aimaraffa.ai``.
"""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
# Training outputs live outside ``src`` so generated datasets and reports don't
# sit inside the importable source tree.
_BACKEND_ROOT = Path(__file__).resolve().parents[3]  # …/backend
TRAINING_ARTIFACTS_DIR = _BACKEND_ROOT / "artifacts" / "training"

# The runtime model stays in the legacy location because Docker and the server
# config still treat it as the stable production slot.
_SRC_ROOT = Path(__file__).resolve().parents[2]      # …/backend/src

MODEL_FILENAME        = "marafone_model.joblib"
DATASET_FILENAME      = "marafone_dataset.parquet"
ANALYSIS_FILENAME     = "marafone_analysis_dataset.parquet"
IMPORTANCE_FILENAME   = "marafone_importance.csv"
REPORT_FILENAME       = "strategy_report.md"

# What Docker ships: a stable file path + a pointer telling which v<N> it came from.
PRODUCTION_MODEL_PATH = _SRC_ROOT / "scripts" / "artifacts" / MODEL_FILENAME
PRODUCTION_POINTER    = _SRC_ROOT / "scripts" / "artifacts" / "PRODUCTION"

# ── Pipeline knobs ─────────────────────────────────────────────────────────────
DATASET_GAMES   = 10_000   # self-play games used to train v<N+1>
DATASET_EPSILON = 0.10     # ε-greedy exploration during dataset self-play
DATASET_EXPLORATION_TOP_K = 3

# Seat-level policy mix used only while generating the training dataset.
# Labels resolve to the latest model, one/two previous versions when available,
# or random play when a referenced older checkpoint does not exist yet.
DATASET_POLICY_MIX = (
	("latest", 0.60),
	("prev1", 0.20),
	("prev2", 0.10),
	("random", 0.10),
)

# Counterfactual action sampling — training dataset only.
# When enabled, the simulator forks alternative actions at a subset of decision
# points and rolls out the rest of the round to get a contrastive target.
COUNTERFACTUAL_ENABLED      = False
COUNTERFACTUAL_PROBABILITY  = 0.30   # chance of sampling alternatives per decision
COUNTERFACTUAL_ALTERNATIVES = 2      # how many alternative actions to evaluate
COUNTERFACTUAL_ROLLOUTS     = 3      # rollouts per alternative (averaged → less noise)
COUNTERFACTUAL_WEIGHT       = 0.5    # sample_weight for CF rows (1.0 = same as executed)

ANALYSIS_GAMES  = 2_000    # ε=0 self-play used by analyze.py to study v<N+1>

TOURNEY_GAMES   = 2_000    # head-to-head new vs source version
TOURNEY_SEED    = 42

# Promote (= copy to PRODUCTION_MODEL_PATH) only when the new model wins
# decisively against the source. The lower bound of the Wilson 95% CI is
# what gates promotion — point estimate alone is too noisy at TOURNEY_GAMES.
PROMOTE_MIN_CI_LOWER = 0.505

# Parallel simulation workers.
# Each worker spawns a separate process that loads its own model copy and
# simulates an independent chunk of games. Set to 1 to disable (single process).
# With a GPU model each worker needs its own GPU context; keep an eye on VRAM.
SIMULATE_N_WORKERS = 4

# ── Training hyperparameters ───────────────────────────────────────────────────
TARGET         = "future_pts_diff"
TEST_SIZE      = 0.20
N_ESTIMATORS   = 2_000
LEARNING_RATE  = 0.05
MAX_DEPTH      = 6
SUBSAMPLE      = 0.8
DEVICE         = "cuda"   # "cpu" or "cuda"

# ── Analysis ───────────────────────────────────────────────────────────────────
ANALYSIS_TOP_FEATURES = 30
ANALYSIS_SHAP         = False
