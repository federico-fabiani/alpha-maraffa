"""Application configuration loaded from environment variables via pydantic-settings."""

from pydantic_settings import BaseSettings

_DEFAULT_MODEL = ""


class Settings(BaseSettings):
    """All tuneable knobs for the server; override via environment variables."""

    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["*"]
    max_rooms: int = 40
    live_bot_policy: str = "heuristic"
    ml_model_path: str = _DEFAULT_MODEL   # used when live_bot_policy is "ml"


settings = Settings()
