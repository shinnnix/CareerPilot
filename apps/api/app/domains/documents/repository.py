from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.domains.documents.model import (
    DocumentChunk,
    DocumentType,
    KnowledgeDocument,
    ReviewStatus,
)


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_documents(
        self,
        *,
        user_id: str,
        document_type: DocumentType | None,
        review_status: ReviewStatus | None,
        page: int,
        page_size: int,
    ) -> tuple[list[KnowledgeDocument], int]:
        filters = [KnowledgeDocument.user_id == user_id]
        if document_type:
            filters.append(KnowledgeDocument.document_type == document_type)
        if review_status:
            filters.append(KnowledgeDocument.review_status == review_status)
        total = (
            self.session.scalar(select(func.count()).select_from(KnowledgeDocument).where(*filters))
            or 0
        )
        statement = (
            select(KnowledgeDocument)
            .where(*filters)
            .order_by(KnowledgeDocument.created_at.desc(), KnowledgeDocument.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.session.scalars(statement)), total

    def get(
        self, *, user_id: str, document_id: str, with_chunks: bool = False
    ) -> KnowledgeDocument | None:
        statement = select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.user_id == user_id,
        )
        if with_chunks:
            statement = statement.options(selectinload(KnowledgeDocument.chunks))
        return self.session.scalar(statement)

    def get_by_hash(self, *, user_id: str, content_hash: str) -> KnowledgeDocument | None:
        return self.session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.user_id == user_id,
                KnowledgeDocument.content_hash == content_hash,
            )
        )

    def add(self, document: KnowledgeDocument) -> KnowledgeDocument:
        self.session.add(document)
        self.session.flush()
        return document

    def replace_chunks(self, *, document: KnowledgeDocument, chunks: list[DocumentChunk]) -> None:
        document.chunks.clear()
        self.session.flush()
        document.chunks.extend(chunks)
        document.chunk_count = len(chunks)
        self.session.flush()

    def delete(self, document: KnowledgeDocument) -> None:
        self.session.delete(document)
        self.session.flush()
