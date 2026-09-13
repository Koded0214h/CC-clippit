from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App-wide settings for the whole backend monolith. Every module
    (auth, and later campaigns/payouts/etc.) reads from this one place."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://clippit:clippit@localhost:5432/clippit"
    jwt_secret: str = "dev-only-not-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    port: int = 8000

    # Shared secret used between internal modules/services if any of this
    # backend is ever split out later. Not exposed to the browser.
    internal_service_secret: str = "dev-only-not-secret"
    frontend_origin: str = "http://localhost:3000"

    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    tiktok_redirect_uri: str = "http://localhost:8000/social/tiktok/callback"

    facebook_app_id: str = ""
    facebook_app_secret: str = ""
    facebook_redirect_uri: str = "http://localhost:8000/social/facebook/callback"

    instagram_app_id: str = ""
    instagram_app_secret: str = ""
    instagram_redirect_uri: str = "http://localhost:8000/social/instagram/callback"

    threads_app_id: str = ""
    threads_app_secret: str = ""
    threads_redirect_uri: str = "http://localhost:8000/social/threads/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()
