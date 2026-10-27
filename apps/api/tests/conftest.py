from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.rate_limit import rate_limiter
from app.db.base import Base
from app.db.session import get_db
from app.domains.agent.model import AgentEvent, AgentRun, ToolReceipt  # noqa: F401
from app.domains.applications.model import (  # noqa: F401
    Application,
    ApplicationEvent,
    AutofillRun,
    GeneratedArtifact,
    MatchFeedback,
)
from app.domains.auth.model import User  # noqa: F401
from app.domains.documents.model import (  # noqa: F401
    ChunkEmbedding,
    DocumentChunk,
    KnowledgeDocument,
)
from app.domains.jobs.model import Job  # noqa: F401
from app.domains.reminders.model import Reminder  # noqa: F401
from app.domains.resumes.model import Resume, ResumeOptimization, ResumeVersion  # noqa: F401
from app.main import app


@pytest.fixture(autouse=True)
def reset_rate_limits() -> Generator[None, None, None]:
    rate_limiter.reset()
    yield
    rate_limiter.reset()


@pytest.fixture
def session_factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def job_payload() -> dict[str, object]:
    return {
        "title": "AI 应用开发实习生",
        "company_name": "示例科技",
        "city": "上海",
        "employment_type": "internship",
        "remote_type": "hybrid",
        "salary_min": "200",
        "salary_max": "300",
        "internship_days_per_week": 4,
        "internship_months": 4,
        "required_skills": ["Python", "FastAPI", "RAG"],
        "preferred_skills": ["Vue 3", "LangChain"],
        "source_url": "https://example.com/jobs/ai-intern",
        "raw_text": "负责 AI 应用开发，使用 FastAPI、RAG 与 Vue 构建面向用户的智能产品。",
        "status": "active",
    }
