"""Application configuration loaded from environment variables via pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All tuneable knobs for the server; override via environment variables."""

    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["*"]


settings = Settings()
