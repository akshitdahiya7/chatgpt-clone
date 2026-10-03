from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    name: str = "Chat Service"
    version: str = "0.1.0"

    env: str = "DEV"
    host: str = "0.0.0.0"
    port: int = 8001

    # Storage
    storage_provider: str = "s3"
    s3_bucket_name: str = ""

    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # Downstream service
    ai_service_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
