"""
Alembic environment.

The database URL comes from truthshield.settings rather than alembic.ini, so
there is exactly one place credentials are configured and nothing secret is
committed.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from truthshield.infra.database import Base
from truthshield.settings import get_settings

# Importing the models registers every table on Base.metadata. Without this,
# autogenerate would see an empty schema and helpfully offer to drop
# everything.
import truthshield.infra.models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
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
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Catch column type drift, which is the change most likely to pass
            # review unnoticed and corrupt data later.
            compare_type=True,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
