from atlas.db.migrations_env import run_migrations_offline, run_migrations_online
from alembic import context


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
