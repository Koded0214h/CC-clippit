from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class NormalizedToken:
    """What every provider's exchange_code() must produce, regardless of how
    many hops (short-lived -> long-lived, PKCE, etc.) getting there took."""

    access_token: str
    platform_user_id: str
    refresh_token: str | None = None
    expires_in: int | None = None  # seconds

    @property
    def expires_at(self) -> datetime | None:
        if self.expires_in is None:
            return None
        return datetime.now(timezone.utc) + timedelta(seconds=self.expires_in)


class OAuthError(RuntimeError):
    """Raised when a provider rejects authorization or a token exchange."""


@dataclass
class ProfileInfo:
    """Who the connected account is, as its owner would recognise it."""

    handle: str | None = None
    display_name: str | None = None
