from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context
from src.config import get_settings
from src.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    # Tests pass an explicit URL via config.set_main_option; otherwise use DATABASE_URL from .env
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def _include_object(obj, name, type_, reflected, compare_to) -> bool:
    # The agent's conversation memory tables (checkpoints, checkpoint_*) belong to langgraph's own migrations
    if type_ == "table" and reflected and compare_to is None and name.startswith("checkpoint"):
        return False
    # The generated tstzrange columns are managed by Postgres; don't let autogenerate fight over them
    return not (type_ == "column" and name == "period" and reflected and compare_to is not None)


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, include_object=_include_object)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
