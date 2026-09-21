from functools import lru_cache

from core.config import get_settings

from .base import PaymentProvider
from .sandbox import SandboxProvider


@lru_cache
def get_provider() -> PaymentProvider:
    """The configured provider. Adding one means writing an adapter that
    satisfies `PaymentProvider` and registering it here — no caller changes."""
    name = get_settings().payment_provider
    if name == "sandbox":
        return SandboxProvider()
    raise RuntimeError(
        f"PAYMENT_PROVIDER={name!r} has no adapter yet. Implement one behind "
        "integrations.payments.base.PaymentProvider (plan §26 leaves the choice open)."
    )
