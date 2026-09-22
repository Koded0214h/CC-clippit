from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from core.config import get_settings
from core.database import Base

# Every module's models must be imported here so autogenerate can see them —
# add the import when a new module (campaigns, payouts, ...) lands.
import modules.audit.models  # noqa: E402,F401
import modules.auth.models  # noqa: E402,F401
import modules.campaigns.models  # noqa: E402,F401
import modules.creators.models  # noqa: E402,F401
import modules.disputes.models  # noqa: E402,F401
import modules.earnings.models  # noqa: E402,F401
import modules.funding.models  # noqa: E402,F401
import modules.intelligence.models  # noqa: E402,F401
import modules.legal.models  # noqa: E402,F401
import modules.notifications.models  # noqa: E402,F401
import modules.organisations.models  # noqa: E402,F401
import modules.payouts.models  # noqa: E402,F401
import modules.refunds.models  # noqa: E402,F401
import modules.reports.models  # noqa: E402,F401
import modules.submissions.models  # noqa: E402,F401
import modules.support.models  # noqa: E402,F401
import modules.uploads.models  # noqa: E402,F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.sync_database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.sync_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
