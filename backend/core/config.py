from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App-wide settings for the whole backend monolith. Every module
    (auth, and later campaigns/payouts/etc.) reads from this one place."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # `production` turns on the refusals in core.startup (no sandbox payment
    # provider, no default secrets). Anything else is treated as development.
    environment: str = "development"

    # Async (asyncpg) URL used by the running app: postgresql+asyncpg://...
    database_url: str = "postgresql+asyncpg://clippit:clippit@localhost:5432/clippit"
    jwt_secret: str = "dev-only-not-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    # Work factor for password hashing. 12 is right for production; the test
    # suite lowers it (a signup per test made hashing most of its runtime).
    bcrypt_rounds: int = 12
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

    # --- Email / one-time codes -------------------------------------------
    # `console` logs the message (and keeps the last few in memory so dev
    # and tests can read a code). `smtp` sends for real.
    email_backend: str = "console"
    email_from: str = "Clippit <no-reply@clippit.local>"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    require_email_verification: bool = True
    otp_ttl_minutes: int = 10
    otp_max_attempts: int = 5
    otp_resend_cooldown_seconds: int = 60

    # --- Uploads -----------------------------------------------------------
    # `local` writes under storage_local_dir and serves it at /media. R2 is
    # the plan's production target and slots in behind core.storage.
    storage_backend: str = "local"
    storage_local_dir: str = "./var/uploads"
    public_base_url: str = "http://localhost:8000"
    max_image_bytes: int = 5 * 1024 * 1024
    max_video_bytes: int = 250 * 1024 * 1024
    max_evidence_bytes: int = 25 * 1024 * 1024

    # --- Money -------------------------------------------------------------
    # `sandbox` is deterministic and never touches a network. A real
    # provider (Squad / Paystack / Payaza — plan §26, undecided) is an
    # adapter behind integrations.payments.PaymentProvider.
    payment_provider: str = "sandbox"
    payment_webhook_secret: str = "dev-only-not-secret"
    funding_fee_rate: float = 0.015
    earnings_hold_days: int = 5
    min_withdrawal: int = 1000

    # Run periodic jobs (earnings settlement, campaign expiry, payout
    # reconciliation) inside the API process. Off by default: tests and
    # one-off scripts must not start background loops.
    background_jobs_enabled: bool = False

    @property
    def sync_database_url(self) -> str:
        """Alembic migrations run synchronously (psycopg2), while the app
        talks to Postgres asynchronously (asyncpg) — same database, two
        drivers. Derived so there's only one URL to configure."""
        return self.database_url.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
