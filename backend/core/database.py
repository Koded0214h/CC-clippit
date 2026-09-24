from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

settings = get_settings()


def _asyncpg_url_and_connect_args(url: str) -> tuple[str, dict]:
    """asyncpg's connect() rejects libpq-only query params — Neon's connection
    strings include `sslmode=` and `channel_binding=`, and asyncpg raises
    `TypeError: connect() got an unexpected keyword argument 'sslmode'`
    the moment SQLAlchemy forwards them. Strip both from the URL and, if
    sslmode was set, pass it through connect_args instead (asyncpg accepts
    the same 'require'/'verify-full'/... vocabulary there)."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    clean_url = urlunsplit(parts._replace(query=urlencode(query)))
    return clean_url, ({"ssl": sslmode} if sslmode else {})


_database_url, _connect_args = _asyncpg_url_and_connect_args(settings.database_url)
engine = create_async_engine(_database_url, pool_pre_ping=True, connect_args=_connect_args)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    """Shared declarative base for every module's models in this monolith."""
