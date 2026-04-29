"""Version directory management for AlphaZero-style training.

Mirrors ``rl_versions.py`` but in its own subtree so AZ runs do not
interfere with the legacy RL chain.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from . import config_az as cfg

logger = logging.getLogger(__name__)


_RX = re.compile(r"^az_v(\d+)$")


def list_versions() -> List[Tuple[int, Path]]:
    cfg.AZ_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for p in cfg.AZ_ARTIFACTS_DIR.iterdir():
        if not p.is_dir():
            continue
        m = _RX.match(p.name)
        if m:
            out.append((int(m.group(1)), p))
    return sorted(out)


def latest_version() -> Tuple[int, Optional[Path]]:
    versions = list_versions()
    if not versions:
        return 0, None
    n, p = versions[-1]
    return n, p / cfg.AZ_MODEL_FILENAME


def next_version_dir() -> Tuple[str, Path]:
    n, _ = latest_version()
    new_n = n + 1
    name = f"az_v{new_n}"
    p = cfg.AZ_ARTIFACTS_DIR / name
    p.mkdir(parents=True, exist_ok=True)
    return name, p


def promote(version_name: str, version_dir: Path) -> None:
    src_pt   = version_dir / cfg.AZ_MODEL_FILENAME
    src_onnx = version_dir / cfg.AZ_ONNX_FILENAME
    cfg.AZ_PRODUCTION_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    if src_pt.exists():
        shutil.copy2(src_pt, cfg.AZ_PRODUCTION_MODEL_PATH)
    if src_onnx.exists():
        shutil.copy2(src_onnx, cfg.AZ_PRODUCTION_ONNX_PATH)
    cfg.AZ_PRODUCTION_POINTER.write_text(version_name + "\n", encoding="utf-8")
    logger.info("Promoted %s → %s", version_name, cfg.AZ_PRODUCTION_MODEL_PATH)
