from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://updatr:updatr_dev@localhost:5432/updatr"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "dev-secret-change-in-production"
    ENCRYPTION_KEY: str = "dev-encryption-key-change-in-production"
    CORS_ORIGINS: str = "http://localhost:3000"
    EXTERNAL_DATABASE_URL: str | None = None
    EXTERNAL_REDIS_URL: str | None = None

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
