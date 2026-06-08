from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://devcore:devcore@localhost:5433/devcore"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "devcore123"
    redis_url: str = "redis://localhost:6379"
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
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    playwright_max_concurrency: int = 4
    judge0_api_key: str = ""
    serp_api_key: str = ""
    devcore_file_index_path: str = "~/.devcore/file_index"
    groq_api_key: str = ""
    deepgram_api_key: str = ""
    deepseek_api_key: str = ""

settings = Settings()
