from functools import lru_cache

from core.config import get_settings

from .base import PaymentProvider
from .sandbox import SandboxProvider


@lru_cache
def get_provider() -> PaymentProvider:
    """The configured provider. Adding one means writing an adapter that
    satisfies `PaymentProvider` and registering it here — no caller changes."""
    settings = get_settings()
    name = settings.payment_provider
    if name == "sandbox":
        return SandboxProvider()
    if name == "paystack":
        if not settings.paystack_secret_key:
            raise RuntimeError("PAYMENT_PROVIDER=paystack needs PAYSTACK_SECRET_KEY")
        from .paystack import PaystackProvider

        return PaystackProvider(settings.paystack_secret_key, settings.paystack_base_url)
    raise RuntimeError(f"Unknown PAYMENT_PROVIDER {name!r} (expected 'sandbox' or 'paystack').")
