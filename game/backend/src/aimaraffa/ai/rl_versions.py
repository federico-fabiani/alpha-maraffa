"""Version management for RL model checkpoints.

Mirrors versions.py but for the separate RL artifact directory.
Each version is a directory ``rl_v<N>`` under RL_ARTIFACTS_DIR containing
at minimum a ``marafone_rl_model.pt`` file.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from .config_rl import (
    RL_ARTIFACTS_DIR,
    RL_MODEL_FILENAME,
    RL_ONNX_FILENAME,
    RL_PRODUCTION_MODEL_PATH,
    RL_PRODUCTION_ONNX_PATH,
    RL_PRODUCTION_POINTER,
    RL_PROMOTION_LOG,
)

_VER_RE = re.compile(r"^rl_v(\d+)$")


def recent_rl_versions(limit: int | None = None) -> list[tuple[int, Path]]:
    """Return RL versions sorted newest → oldest.

    Falls back to the loose production model as version 0 when present, so
    the first iteration always has a baseline to train against.
    """
    found: list[tuple[int, Path]] = []
    if RL_ARTIFACTS_DIR.exists():
        for child in RL_ARTIFACTS_DIR.iterdir():
            if not child.is_dir():
                continue
            m = _VER_RE.match(child.name)
            if not m:
                continue
            model_path = child / RL_MODEL_FILENAME
            if model_path.exists():
                found.append((int(m.group(1)), model_path))
    found.sort(key=lambda x: x[0], reverse=True)
    if RL_PRODUCTION_MODEL_PATH.exists() and not any(n == 0 for n, _ in found):
        found.append((0, RL_PRODUCTION_MODEL_PATH))
    return found[:limit] if limit is not None else found


def latest_rl_version() -> tuple[int, Path | None]:
    """Return ``(num, model_path)`` for the newest RL checkpoint, or ``(0, None)``."""
    found = recent_rl_versions(limit=1)
    return found[0] if found else (0, None)


def next_rl_version_dir() -> tuple[str, Path]:
    """Allocate ``rl_v<N+1>`` and return ``(name, path)``."""
    n, _ = latest_rl_version()
    name = f"rl_v{n + 1}"
    path = RL_ARTIFACTS_DIR / name
    path.mkdir(parents=True, exist_ok=True)
    return name, path


def rl_production_version() -> str | None:
    """Read the currently-promoted RL version name."""
    if not RL_PRODUCTION_POINTER.exists():
        return None
    return RL_PRODUCTION_POINTER.read_text(encoding="utf-8").strip() or None


def promoted_rl_versions(limit: int | None = None) -> list[tuple[int, Path]]:
    """Return promoted RL versions sorted newest → oldest."""
    if not RL_PROMOTION_LOG.exists():
        current = rl_production_version()
        if current:
            m = _VER_RE.match(current)
            if m:
                p = RL_ARTIFACTS_DIR / current / RL_MODEL_FILENAME
                if p.exists():
                    return [(int(m.group(1)), p)]
        return []

    entries: list[tuple[int, Path]] = []
    for line in RL_PROMOTION_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        m = _VER_RE.match(line)
        if not m:
            continue
        p = RL_ARTIFACTS_DIR / line / RL_MODEL_FILENAME
        if p.exists():
            entries.append((int(m.group(1)), p))

    seen: dict[int, Path] = {}
    for num, path in entries:
        seen[num] = path
    result = sorted(seen.items(), key=lambda x: x[0], reverse=True)
    return result[:limit] if limit is not None else result


def rl_promote(version_name: str, version_dir: Path) -> None:
    """Copy the model to the production slot and update the pointer + log."""
    src = version_dir / RL_MODEL_FILENAME
    if not src.exists():
        raise FileNotFoundError(f"Cannot promote — model not found: {src}")
    RL_PRODUCTION_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, RL_PRODUCTION_MODEL_PATH)

    onnx_src = version_dir / RL_ONNX_FILENAME
    if onnx_src.exists():
        shutil.copyfile(onnx_src, RL_PRODUCTION_ONNX_PATH)

    RL_PRODUCTION_POINTER.write_text(version_name + "\n", encoding="utf-8")
    RL_PROMOTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RL_PROMOTION_LOG.open("a", encoding="utf-8") as f:
        f.write(version_name + "\n")
