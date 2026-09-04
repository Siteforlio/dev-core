import os
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to backend/ (two levels up from this file: app/core/config.py → backend/app/core → backend/app → backend)
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

# Use the Electron userData directory for the database if available (passed by
# Electron in both dev and packaged modes via DEVCORE_USER_DATA env var).
_user_data = os.environ.get('DEVCORE_USER_DATA', '')
if _user_data:
    os.makedirs(_user_data, exist_ok=True)  # ensure dir exists before SQLite creates the file
_default_db_url = (
    f"sqlite+aiosqlite:///{os.path.join(_user_data, 'devcore.db')}"
    if _user_data
    else "sqlite+aiosqlite:///./devcore.db"
)
# Kokoro model files are large (~400 MB) and downloaded on first TTS use.
_default_kokoro_dir = (
    os.path.join(_user_data, 'models', 'kokoro')
    if _user_data
    else "backend/models/kokoro"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    database_url: str = _default_db_url
    redis_url: str = ""
    jwt_secret: str = ""  # REQUIRED — no default; app refuses to start if missing or weak
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 10080  # 7 days — practical for desktop app
    jwt_refresh_expire_days: int = 90
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    vertex_api_key: str = ""  # aiplatform.googleapis.com key for gemini-2.5-flash-lite
    heygen_api_key: str = ""
    simli_api_key: str = ""
    openai_api_key: str = ""
    environment: str = "development"
    job_hunter_encryption_key: str | None = None  # Fernet 32-byte URL-safe base64 key
    # Google OAuth — https://console.cloud.google.com/
    google_client_id: str = ""
    google_client_secret: str = ""
    # Microsoft OAuth — https://portal.azure.com/
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_tenant_id: str = "common"   # "common" = personal + org accounts
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
    # Kokoro TTS — local ONNX model directory, auto-downloaded on first TTS use
    kokoro_models_dir: str = _default_kokoro_dir

    @field_validator("jwt_secret")
    @classmethod
    def _require_strong_jwt_secret(cls, v: str) -> str:
        _WEAK = {"", "change-me-in-production", "devcore-jwt-secret-change-in-prod",
                 "secret", "changeme", "change-me", "your-secret-here"}
        if v in _WEAK or len(v) < 32:
            import secrets as _secrets
            suggestion = _secrets.token_hex(32)
            raise ValueError(
                f"JWT_SECRET is missing or too weak (must be ≥32 chars, not a known placeholder). "
                f"Add this to backend/.env:\n  JWT_SECRET={suggestion}"
            )
        return v

settings = Settings()


async def get_api_key(user_id: str, key_name: str, db) -> str:
    """Get a user API key from the database (Settings screen).

    All user-configurable keys must be set in Settings → API Keys.
    There is no .env fallback for these keys by design.
    """
    from app.services.api_keys_service import ApiKeysService
    service = ApiKeysService(db)
    return await service.get_decrypted(user_id, key_name) or ""
