from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql://arap:arap@localhost:5433/arap_dev"
    ANTHROPIC_API_KEY: str
    OPENAI_API_KEY: str
    GROQ_API_KEY: str
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "arap"
    S3_SECRET_KEY: str = "arap_secret"
    S3_BUCKET_RESUMES: str = "arap-resumes"
    LARGE_DOC_BYTES: int = 5_242_880
    LARGE_DOC_PARSE_TIMEOUT: float = 8.0


settings = Settings()
