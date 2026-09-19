from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App-wide settings for the whole backend monolith. Every module
    (auth, and later campaigns/payouts/etc.) reads from this one place."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Async (asyncpg) URL used by the running app: postgresql+asyncpg://...
    database_url: str = "postgresql+asyncpg://clippit:clippit@localhost:5432/clippit"
    jwt_secret: str = "dev-only-not-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    port: int = 8000

    # Shared secret used between internal modules/services if any of this
    # backend is ever split out later. Not exposed to the browser.
    internal_service_secret: str = "dev-only-not-secret"
    frontend_origin: str = "http://localhost:5174"

    # In-memory by default (fine for one process/dev). Point this at Redis
    # (e.g. redis://localhost:6379) once this runs as more than one worker,
    # or rate limits won't be shared across processes.
    rate_limit_storage_uri: str = "memory://"

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

    x_client_id: str = ""
    x_client_secret: str = ""
    x_redirect_uri: str = "http://localhost:8000/social/x/callback"
    twitterapi_io_key: str = ""

    @property
    def sync_database_url(self) -> str:
        """Alembic migrations run synchronously (psycopg2), while the app
        talks to Postgres asynchronously (asyncpg) — same database, two
        drivers. Derived so there's only one URL to configure."""
        return self.database_url.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
