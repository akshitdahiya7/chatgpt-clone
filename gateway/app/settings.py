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

    # Downstream service
    chat_service: str

    # Signs the session cookie. Changing it signs everyone out, which is the
    # right behaviour if it ever leaks.
    session_secret: str = "change-me"

    # Requests allowed per caller within the window.
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 3600

    # Named users, as "token1:alice,token2:bob". A caller sending
    # "Authorization: Bearer token1" is treated as alice rather than as an
    # anonymous session.
    api_tokens: str = ""

    @property
    def token_map(self) -> dict[str, str]:
        pairs = {}

        for entry in self.api_tokens.split(","):
            token, _, user = entry.partition(":")
            if token.strip() and user.strip():
                pairs[token.strip()] = user.strip()

        return pairs


@lru_cache
def get_settings() -> Settings:
    return Settings()
