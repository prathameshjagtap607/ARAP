from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql://arap:arap@localhost:5433/arap_dev"
    SECRET_KEY: str = "change-me-in-production"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "info"
    APP_VERSION: str = "0.1.0"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3002"]

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    LOGIN_TOKEN_EXPIRE_MINUTES: int = 15
    REDIS_URL: str = "redis://localhost:6379/0"

    ANTHROPIC_API_KEY: str
    OPENAI_API_KEY: str
    INGESTION_SERVICE_URL: str = "http://localhost:8001"

    CANDIDATE_PORTAL_URL: str = "http://localhost:3000"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@arap.dev"
    SENDGRID_API_KEY: str = ""


settings = Settings()
