from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base
from app.domains.agent.model import AgentEvent, AgentRun, ToolReceipt  # noqa: F401
from app.domains.applications.model import (  # noqa: F401
    Application,
    ApplicationEvent,
    AutofillRun,
    GeneratedArtifact,
    MatchFeedback,
)
from app.domains.auth.model import User  # noqa: F401
from app.domains.documents.model import DocumentChunk, KnowledgeDocument  # noqa: F401
from app.domains.jobs.model import Job  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def include_object(object_, name, type_, reflected, compare_to) -> bool:
    # PostgreSQL reflects the to_tsvector expression differently from SQLAlchemy's
    # expression tree. Both indexes are declared in model metadata and managed by
    # migrations; excluding only these known names prevents false removals.
    reflected_fts = {"ix_document_chunks_fts"}
    return not (type_ == "index" and name in reflected_fts)


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
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
            compare_type=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
