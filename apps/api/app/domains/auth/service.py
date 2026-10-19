from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.domains.agent.model import AgentEvent, AgentRun, ToolReceipt
from app.domains.applications.model import (
    Application,
    ApplicationEvent,
    GeneratedArtifact,
    MatchFeedback,
)
from app.domains.auth.model import User
from app.domains.auth.repository import UserRepository
from app.domains.auth.schemas import (
    LoginRequest,
    PurgeAccountRequest,
    PurgeAccountResponse,
    RegisterRequest,
    TokenResponse,
    UserRead,
)
from app.domains.auth.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.domains.documents.model import ChunkEmbedding, DocumentChunk, KnowledgeDocument
from app.domains.jobs.model import Job

PURGE_CONFIRMATION = "DELETE MY DATA"
DUMMY_PASSWORD_HASH = hash_password("not-a-real-password")


class AuthService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.repository = UserRepository(session)

    def register(self, payload: RegisterRequest) -> TokenResponse:
        email = str(payload.email).strip().lower()
        if self.repository.get_by_email(email):
            raise AppError(
                code="EMAIL_ALREADY_REGISTERED",
                message="该邮箱已注册",
                status_code=409,
            )
        user = User(email=email, password_hash=hash_password(payload.password))
        try:
            self.repository.add(user)
            self.session.commit()
            self.session.refresh(user)
        except IntegrityError:
            self.session.rollback()
            raise AppError(
                code="EMAIL_ALREADY_REGISTERED",
                message="该邮箱已注册",
                status_code=409,
            ) from None
        return self._token_response(user)

    def login(self, payload: LoginRequest) -> TokenResponse:
        email = str(payload.email).strip().lower()
        user = self.repository.get_by_email(email)
        encoded = user.password_hash if user else DUMMY_PASSWORD_HASH
        if not verify_password(payload.password, encoded) or user is None:
            raise AppError(
                code="INVALID_CREDENTIALS",
                message="邮箱或密码错误",
                status_code=401,
            )
        return self._token_response(user)

    def purge(self, *, user: User, payload: PurgeAccountRequest) -> PurgeAccountResponse:
        if payload.confirmation != PURGE_CONFIRMATION:
            raise AppError(
                code="PURGE_CONFIRMATION_REQUIRED",
                message=f"请输入确认短语：{PURGE_CONFIRMATION}",
                status_code=422,
            )
        if not verify_password(payload.password, user.password_hash):
            raise AppError(
                code="INVALID_CREDENTIALS",
                message="密码错误，未删除任何数据",
                status_code=401,
            )
        user_id = user.id
        counts: dict[str, int] = {}
        targets = [
            ("agent_events", AgentEvent),
            ("tool_receipts", ToolReceipt),
            ("agent_runs", AgentRun),
            ("generated_artifacts", GeneratedArtifact),
            ("match_feedback", MatchFeedback),
            ("application_events", ApplicationEvent),
            ("applications", Application),
            ("chunk_embeddings", ChunkEmbedding),
            ("document_chunks", DocumentChunk),
            ("knowledge_documents", KnowledgeDocument),
            ("jobs", Job),
        ]
        try:
            for label, model in targets:
                result = self.session.execute(delete(model).where(model.user_id == user_id))
                counts[label] = int(result.rowcount or 0)
            self.session.delete(user)
            counts["users"] = 1
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return PurgeAccountResponse(deleted=True, deleted_counts=counts)

    def _token_response(self, user: User) -> TokenResponse:
        ttl_seconds = self.settings.access_token_ttl_minutes * 60
        token = create_access_token(
            subject=user.id,
            token_version=user.token_version,
            secret=self.settings.auth_secret,
            ttl_seconds=ttl_seconds,
        )
        return TokenResponse(
            access_token=token,
            expires_in=ttl_seconds,
            user=UserRead(id=user.id, email=user.email, created_at=user.created_at),
        )
