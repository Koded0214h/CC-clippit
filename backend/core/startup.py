"""Refuse to boot in a configuration that would be dangerous in production.

A sandbox payment provider "confirms" funding and "sends" transfers without
any real money — harmless in development, and a free-money bug in production.
Default secrets are equally unacceptable there. Failing loudly at startup is
the point: a misconfigured deploy must not come up half-working.
"""

from .config import Settings, get_settings

_DEFAULT_SECRETS = {"dev-only-not-secret", "change_me", "change_me_to_a_long_random_string", ""}


class UnsafeConfiguration(RuntimeError):
    pass


def check(settings: Settings | None = None) -> list[str]:
    """Returns human-readable problems; empty means fine."""
    settings = settings or get_settings()
    if settings.environment != "production":
        return []
    problems: list[str] = []
    if settings.payment_provider == "sandbox":
        problems.append("PAYMENT_PROVIDER=sandbox in production (no real money would move)")
    for name in ("jwt_secret", "internal_service_secret", "payment_webhook_secret"):
        if getattr(settings, name) in _DEFAULT_SECRETS:
            problems.append(f"{name.upper()} is a default value")
    if settings.email_backend == "console":
        problems.append("EMAIL_BACKEND=console in production (codes would only be logged)")
    return problems


def assert_safe_to_start(settings: Settings | None = None) -> None:
    problems = check(settings)
    if problems:
        raise UnsafeConfiguration("Refusing to start: " + "; ".join(problems))
