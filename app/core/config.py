from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    GROQ_API_KEY: str | None = Field(default=None)
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    ASR_PROVIDER: str = "groq_whisper"
    ASR_MODEL: str = "whisper-large-v3"
    ASR_LANGUAGE: str | None = None

    LLM_PROVIDER: str = "groq"
    LLM_MODEL: str = "llama-3.3-70b-versatile"

    DATABASE_URL: str = "sqlite:///./data/meetings.db"
    UPLOAD_DIR: str = "data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 100
    TRANSCRIPT_MAX_CHARS: int = 60000
    TRANSCRIPT_CHUNK_CHARS: int = 14000

    FRONTEND_ORIGINS: str = "http://localhost:8501,http://127.0.0.1:8501"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.FRONTEND_ORIGINS.split(",") if origin.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    if settings.DATABASE_URL.startswith("sqlite:///"):
        db_path = Path(settings.DATABASE_URL.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
