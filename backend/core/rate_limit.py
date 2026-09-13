"""Shared slowapi Limiter. Defined once here so both main.py (to attach it
to the app) and individual routers (to decorate endpoints) can import the
same instance without a circular import."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import get_settings

settings = get_settings()

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.rate_limit_storage_uri)
