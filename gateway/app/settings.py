from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    name: str = "Gateway Service"
    version: str = "0.1.0"
    
    env: str = "DEV"
    port: int = 8000
    # Reserved for the future persistence layer; nothing reads it yet.
    mongodb_uri: str = ""

    chat_service: str


@lru_cache
def get_settings() -> Settings:
    return Settings()