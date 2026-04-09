from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    redis_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 7
    anthropic_api_key: str = ""
    heygen_api_key: str = ""
    simli_api_key: str = ""
    openai_api_key: str = ""
    environment: str = "development"

    class Config:
        env_file = ".env"

settings = Settings()
