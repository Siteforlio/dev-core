import sys
import os
from logging.config import fileConfig

from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.models.pg.base import Base
from app.models.pg.user import User
from app.models.pg.session import InterviewSession, Round, RoundMoment, InterviewProfile
from app.models.pg.community import CommunityData
from app.models.pg.job_hunter import (
    JobHunterProfile,
    JobHunterCampaign,
    JobListing,
    Application,
    EmailEvent,
    CalendarEvent,
)
from app.models.pg.knowledge import KnowledgeProfile
from app.models.pg.progress import UserProgress
from app.models.pg.cluely_session import CluelySession, CluelyTranscriptLine, CluelyInteraction

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    from app.core.config import settings
    url = settings.database_url.replace("+asyncpg", "")  # alembic needs sync URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    from app.core.config import settings
    from sqlalchemy import create_engine
    url = settings.database_url.replace("+asyncpg", "")
    connectable = create_engine(url)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
