from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base for every module's models in this monolith."""


def init_db() -> None:
    """Create tables if they don't exist. Fine for dev; once the schema needs
    to evolve without dropping data, switch to Alembic migrations.

    Every module's models must be imported here so SQLAlchemy knows about
    them before create_all runs — add the import when a new module lands."""
    from modules.auth import models as auth_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
