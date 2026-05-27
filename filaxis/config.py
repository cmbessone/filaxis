from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Temporal
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "filaxis-pdf-pipeline"

    # Anthropic
    anthropic_api_key: str = ""

    # Database — Railway provides postgresql://, SQLAlchemy async needs postgresql+asyncpg://
    database_url: str = "sqlite+aiosqlite:///./filaxis.db"

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_async_driver(cls, v: str) -> str:
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    # AWS S3
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    s3_bucket: str = "filaxis-reports"

    # Auth
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # App
    port: int = 8000
    log_level: str = "INFO"
    environment: str = "development"

    @property
    def is_dev(self) -> bool:
        return self.environment in ("development", "dev")


settings = Settings()
