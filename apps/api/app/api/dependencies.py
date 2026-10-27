from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.domains.agent.service import AgentService
from app.domains.applications.service import (
    ApplicationService,
    AutofillService,
    PersonalizationService,
    WorkspaceApplicationService,
)
from app.domains.auth.model import User
from app.domains.auth.repository import UserRepository
from app.domains.auth.security import decode_access_token
from app.domains.auth.service import AuthService
from app.domains.documents.service import DocumentService
from app.domains.jobs.service import JobCatalogService, JobService
from app.domains.matching.service import MatchingService
from app.domains.reminders.service import ReminderService
from app.domains.resumes.service import (
    ResumeOptimizationService,
    ResumeService,
    ResumeVersionService,
)
from app.domains.retrieval.service import RetrievalService

bearer_scheme = HTTPBearer(auto_error=False)


def _invalid_token() -> AppError:
    return AppError(
        code="INVALID_TOKEN",
        message="登录凭证无效或已过期",
        status_code=401,
    )


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(
            code="AUTH_REQUIRED",
            message="请先登录",
            status_code=401,
        )
    settings = get_settings()
    claims = decode_access_token(credentials.credentials, secret=settings.auth_secret)
    if claims is None:
        raise _invalid_token()
    user = UserRepository(session).get_by_id(claims.subject)
    if user is None or user.token_version != claims.token_version:
        raise _invalid_token()
    request.state.user_id = user.id
    return user


def get_current_user_id(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    x_user_id: Annotated[str | None, Header(max_length=64)] = None,
) -> str:
    settings = get_settings()
    if credentials is not None:
        if credentials.scheme.lower() != "bearer":
            raise _invalid_token()
        claims = decode_access_token(credentials.credentials, secret=settings.auth_secret)
        if claims is None:
            raise _invalid_token()
        user = UserRepository(session).get_by_id(claims.subject)
        if user is None or user.token_version != claims.token_version:
            raise _invalid_token()
        request.state.user_id = user.id
        return user.id

    if settings.allow_demo_auth:
        user_id = x_user_id or settings.demo_user_id
        request.state.user_id = user_id
        return user_id

    raise AppError(
        code="AUTH_REQUIRED",
        message="生产模式不接受 X-User-ID，请使用 Bearer Token",
        status_code=401,
    )


def get_auth_service(session: Annotated[Session, Depends(get_db)]) -> AuthService:
    return AuthService(session)


def get_job_service(session: Annotated[Session, Depends(get_db)]) -> JobService:
    return JobService(session)


def get_job_catalog_service(
    session: Annotated[Session, Depends(get_db)],
) -> JobCatalogService:
    return JobCatalogService(session)


def get_document_service(
    session: Annotated[Session, Depends(get_db)],
) -> DocumentService:
    return DocumentService(session)


def get_retrieval_service(
    session: Annotated[Session, Depends(get_db)],
) -> RetrievalService:
    return RetrievalService(session)


def get_matching_service(
    session: Annotated[Session, Depends(get_db)],
) -> MatchingService:
    return MatchingService(session)


def get_application_service(
    session: Annotated[Session, Depends(get_db)],
) -> ApplicationService:
    return ApplicationService(session)


def get_workspace_application_service(
    session: Annotated[Session, Depends(get_db)],
) -> WorkspaceApplicationService:
    return WorkspaceApplicationService(session)


def get_personalization_service(
    session: Annotated[Session, Depends(get_db)],
) -> PersonalizationService:
    return PersonalizationService(session)


def get_autofill_service(session: Annotated[Session, Depends(get_db)]) -> AutofillService:
    return AutofillService(session)


def get_agent_service(
    session: Annotated[Session, Depends(get_db)],
) -> AgentService:
    return AgentService(session)


def get_resume_service(
    session: Annotated[Session, Depends(get_db)],
) -> ResumeService:
    return ResumeService(session)


def get_resume_optimization_service(
    session: Annotated[Session, Depends(get_db)],
) -> ResumeOptimizationService:
    return ResumeOptimizationService(session)


def get_resume_version_service(
    session: Annotated[Session, Depends(get_db)],
) -> ResumeVersionService:
    return ResumeVersionService(session)


def get_reminder_service(
    session: Annotated[Session, Depends(get_db)],
) -> ReminderService:
    return ReminderService(session)
