"""Application configuration loaded from environment variables via pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings

_DEFAULT_MODEL = str(
    Path(__file__).resolve().parent.parent
    / "scripts" / "artifacts" / "marafone_model.joblib"
)


class Settings(BaseSettings):
    """All tuneable knobs for the server; override via environment variables."""

    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["*"]
    max_rooms: int = 40
    ml_model_path: str = _DEFAULT_MODEL   # override via env var to disable or swap model


settings = Settings()
