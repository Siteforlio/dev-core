from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to backend/ (two levels up from this file: app/core/config.py → backend/app/core → backend/app → backend)
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./devcore.db"
    redis_url: str = ""
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 10080  # 7 days — practical for dev
    jwt_refresh_expire_days: int = 90
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    vertex_api_key: str = ""  # aiplatform.googleapis.com key for gemini-2.5-flash-lite
    heygen_api_key: str = ""
    simli_api_key: str = ""
    openai_api_key: str = ""
    environment: str = "development"
    job_hunter_encryption_key: str | None = None  # Fernet 32-byte URL-safe base64 key
    playwright_max_concurrency: int = 4
    judge0_api_key: str = ""
    serp_api_key: str = ""
    devcore_file_index_path: str = "~/.devcore/file_index"
    groq_api_key: str = ""
    deepgram_api_key: str = ""
    deepseek_api_key: str = ""
    # Global job board API keys (free tier — optional, boards skip gracefully if unset)
    adzuna_app_id: str = ""   # https://developer.adzuna.com/
    adzuna_api_key: str = ""  # https://developer.adzuna.com/
    reed_api_key: str = ""    # https://www.reed.co.uk/developers/jobseeker
    scrapfly_key: str = ""    # https://scrapfly.io/ — used for Wellfound
    # Kokoro TTS — local ONNX model directory (run backend/scripts/download_kokoro.py first)
    kokoro_models_dir: str = "backend/models/kokoro"

settings = Settings()
