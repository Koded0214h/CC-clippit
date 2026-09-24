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

    # YouTube: OAuth for channel identity; Data API key for public metrics
    # (same split as X / twitterapi.io — see integrations/social/youtube.py).
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    youtube_redirect_uri: str = "http://localhost:8000/social/youtube/callback"
    youtube_api_key: str = ""

    # Google Sign-In (identity, not a connected social account — see
    # modules/auth/google.py). Verifies id_tokens via Google's tokeninfo
    # endpoint rather than local JWKS/RS256 verification: this environment
    # doesn't have the `cryptography` package (slow source build, no
    # prebuilt wheel here — see backend/README's test-setup notes), and
    # tokeninfo is Google's own documented alternative for exactly that case.
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    # --- Intelligence polling cadence (env-tunable; PRD leaves exact
    # intervals TBD — these are the defaults documented in scheduling.py) ---
    intelligence_poll_tick_seconds: int = 60
    intelligence_cadence_day1_minutes: int = 30
    intelligence_cadence_week1_hours: int = 2
    intelligence_cadence_month_hours: int = 12
    intelligence_tracking_window_days: int = 30

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
    # `local` writes under storage_local_dir and serves it at /media.
    # `cloudinary` stages the same way, then uploads to Cloudinary and
    # serves its CDN URL directly — see core.storage.CloudinaryStorage.
    storage_backend: str = "local"
    storage_local_dir: str = "./var/uploads"
    public_base_url: str = "http://localhost:8000"
    max_image_bytes: int = 5 * 1024 * 1024
    max_video_bytes: int = 250 * 1024 * 1024
    max_evidence_bytes: int = 25 * 1024 * 1024

    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # --- Money -------------------------------------------------------------
    # `sandbox` is deterministic and never touches a network. Paystack is
    # the PRD V1 locked provider (integrations.payments.PaymentProvider).
    payment_provider: str = "sandbox"  # sandbox | paystack
    # Paystack: the secret key is also the webhook signing key. Use an
    # sk_test_ key while developing; production requires sk_live_.
    paystack_secret_key: str = ""
    paystack_base_url: str = "https://api.paystack.co"
    payment_webhook_secret: str = "dev-only-not-secret"
    # PRD V1 §"Locked platform decisions": 15% on the initial campaign pot
    # (non-refundable), 2.5% on a top-up (wallet or live-campaign), 2.5% on
    # the refundable remainder of a manual cancellation, 7% on a wallet
    # withdrawal — the same rate for both a creator and a brand withdrawal.
    funding_fee_rate: float = 0.15
    topup_fee_rate: float = 0.025
    cancellation_fee_rate: float = 0.025
    withdrawal_fee_rate: float = 0.07
    earnings_hold_days: int = 5
    min_withdrawal: int = 5000

    # Run settlement / sweeps / payout reconciliation inside the API process.
    background_jobs_enabled: bool = False

    # --- Compliance (yt-dlp + Qwen3.8-Omni-Flash) ---------------------------
    # `manual` = brand review queue (default, keeps tests deterministic).
    # `qwen` = retrieve posted media with yt-dlp and judge via Model Studio.
    compliance_verifier: str = "manual"  # manual | qwen
    dashscope_api_key: str = ""
    #: Alias accepted so either env name works.
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen3.8-omni-flash"
    compliance_media_dir: str = "./var/compliance"
    #: Public HTTPS base that can reach files under compliance_media_dir.
    #: Required for videos too large for inline Base64 (~7MB). Leave empty
    #: to use data URLs for small clips (localhost is not reachable by Qwen).
    compliance_public_media_base: str = ""
    compliance_max_duration_seconds: int = 150
    compliance_max_filesize_mb: int = 80
    compliance_keep_media: bool = True

    @property
    def sync_database_url(self) -> str:
        """Alembic migrations run synchronously (psycopg2), while the app
        talks to Postgres asynchronously (asyncpg) — same database, two
        drivers. Derived so there's only one URL to configure."""
        return self.database_url.replace("+asyncpg", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
