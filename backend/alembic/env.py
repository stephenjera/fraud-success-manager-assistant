"""Alembic environment — connects as ``app_rw`` so it can only manage ``appstate``.

ADR-0015: Alembic owns *tables only*. The two roles, the two schemas, and the
GRANTs are infrastructure owned by ``db-init/*.sql`` (idempotent entrypoint/repair
scripts) and ``scripts/seed_reference.py`` owns the ``reference`` tables+data.
Connecting here as the non-superuser ``app_rw`` role (which owns the ``appstate``
schema) is the enforcement: a wrong ``downgrade`` is a plain ``DROP TABLE`` and
*cannot* rename a data schema, drop roles, or touch ``reference`` — the failure
mode the old superuser-migration setup allowed (ADR-0015 incident).
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.common.settings import settings

# Alembic runs as app_rw (owns appstate), not the superuser.
# Override the URL here (not in alembic.ini) and normalise ``%3D`` to ``=``:
# configparser interprets a bare ``%`` as interpolation syntax, and the DSN's
# ``options=-csearch_path=appstate`` query would otherwise trip it. psycopg
# parses the unencoded ``=`` identically.
config = context.config
_dsn = settings.appstate_dsn.replace(
    "postgresql://", "postgresql+psycopg://", 1
).replace("%3D", "=")
config.set_main_option("sqlalchemy.url", _dsn)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
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
            connection=connection, target_metadata=None, compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
