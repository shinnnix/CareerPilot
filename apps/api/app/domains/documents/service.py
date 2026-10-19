from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.content_security import scan_untrusted_content
from app.core.errors import (
    DocumentNotFoundError,
    DuplicateDocumentError,
    UnsupportedDocumentError,
)
from app.domains.documents.file_text import extract_text_from_upload
from app.domains.documents.model import (
    DocumentChunk,
    DocumentType,
    KnowledgeDocument,
    ParseStatus,
    ReviewStatus,
)
from app.domains.documents.parser import INDEX_VERSION, PARSER_VERSION, parse_document
from app.domains.documents.repository import DocumentRepository
from app.domains.documents.schemas import (
    ChunkList,
    ChunkRead,
    DocumentCorrection,
    DocumentDetail,
    DocumentList,
    DocumentSummary,
    DocumentTextImport,
)


class DocumentService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = DocumentRepository(session)

    def import_text(self, *, user_id: str, payload: DocumentTextImport) -> DocumentDetail:
        return self._import(
            user_id=user_id,
            display_name=payload.display_name,
            document_type=payload.document_type,
            raw_text=payload.raw_text,
            file_name=None,
            mime_type="text/plain",
            source_size_bytes=len(payload.raw_text.encode("utf-8")),
        )

    def import_upload(
        self,
        *,
        user_id: str,
        display_name: str,
        document_type: DocumentType,
        file_name: str,
        content: bytes,
    ) -> DocumentDetail:
        raw_text, mime_type = extract_text_from_upload(file_name=file_name, content=content)
        return self._import(
            user_id=user_id,
            display_name=display_name,
            document_type=document_type,
            raw_text=raw_text,
            file_name=file_name,
            mime_type=mime_type,
            source_size_bytes=len(content),
        )

    def list_documents(
        self,
        *,
        user_id: str,
        document_type: DocumentType | None,
        review_status: ReviewStatus | None,
        page: int,
        page_size: int,
    ) -> DocumentList:
        documents, total = self.repository.list_documents(
            user_id=user_id,
            document_type=document_type,
            review_status=review_status,
            page=page,
            page_size=page_size,
        )
        return DocumentList(
            items=[DocumentSummary.model_validate(item) for item in documents],
            page=page,
            page_size=page_size,
            total=total,
        )

    def get_document(self, *, user_id: str, document_id: str) -> DocumentDetail:
        return DocumentDetail.model_validate(
            self._get_owned_document(user_id=user_id, document_id=document_id)
        )

    def get_chunks(self, *, user_id: str, document_id: str) -> ChunkList:
        document = self._get_owned_document(
            user_id=user_id, document_id=document_id, with_chunks=True
        )
        return ChunkList(
            items=[ChunkRead.model_validate(chunk) for chunk in document.chunks],
            total=len(document.chunks),
        )

    def correct_document(
        self,
        *,
        user_id: str,
        document_id: str,
        payload: DocumentCorrection,
    ) -> DocumentDetail:
        document = self._get_owned_document(user_id=user_id, document_id=document_id)
        document.extracted_data = payload.extracted_data.model_dump(mode="json")
        document.review_status = ReviewStatus.confirmed
        document.confirmed_at = datetime.now(timezone.utc)
        try:
            self.session.commit()
            self.session.refresh(document)
        except Exception:
            self.session.rollback()
            raise
        return DocumentDetail.model_validate(document)

    def reindex_document(self, *, user_id: str, document_id: str) -> DocumentDetail:
        document = self._get_owned_document(
            user_id=user_id, document_id=document_id, with_chunks=True
        )
        result = parse_document(
            raw_text=document.raw_text,
            document_type=document.document_type,
            display_name=document.display_name,
        )
        document.parse_version = PARSER_VERSION
        document.index_version = INDEX_VERSION
        document.parse_confidence = Decimal(str(result.confidence))
        document.parse_status = ParseStatus.parsed
        document.extracted_data = result.extracted_data.model_dump(mode="json")
        document.review_status = ReviewStatus.pending
        document.confirmed_at = None
        security = scan_untrusted_content(result.normalized_text)
        document.prompt_injection_detected = security.prompt_injection_detected
        document.security_flags = security.flags
        self.repository.replace_chunks(
            document=document,
            chunks=self._to_models(user_id=user_id, result=result),
        )
        try:
            self.session.commit()
            self.session.refresh(document)
        except Exception:
            self.session.rollback()
            raise
        return DocumentDetail.model_validate(document)

    def delete_document(self, *, user_id: str, document_id: str) -> None:
        document = self._get_owned_document(
            user_id=user_id, document_id=document_id, with_chunks=True
        )
        try:
            self.repository.delete(document)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def _import(
        self,
        *,
        user_id: str,
        display_name: str,
        document_type: DocumentType,
        raw_text: str,
        file_name: str | None,
        mime_type: str,
        source_size_bytes: int,
    ) -> DocumentDetail:
        text_length = len(raw_text.strip())
        if text_length < 20:
            raise UnsupportedDocumentError("文档正文至少需要 20 个字符")
        if text_length > 200_000:
            raise UnsupportedDocumentError("文档正文超过 200,000 字符的第二周处理上限")
        result = parse_document(
            raw_text=raw_text,
            document_type=document_type,
            display_name=display_name,
        )
        security = scan_untrusted_content(result.normalized_text)
        duplicate = self.repository.get_by_hash(user_id=user_id, content_hash=result.content_hash)
        if duplicate:
            raise DuplicateDocumentError(duplicate.id)

        document = KnowledgeDocument(
            user_id=user_id,
            display_name=display_name,
            file_name=file_name,
            mime_type=mime_type,
            document_type=document_type,
            raw_text=result.normalized_text,
            content_hash=result.content_hash,
            source_size_bytes=source_size_bytes,
            parse_status=ParseStatus.parsed,
            parse_version=PARSER_VERSION,
            parse_confidence=Decimal(str(result.confidence)),
            review_status=ReviewStatus.pending,
            extracted_data=result.extracted_data.model_dump(mode="json"),
            prompt_injection_detected=security.prompt_injection_detected,
            security_flags=security.flags,
            index_version=INDEX_VERSION,
            chunk_count=len(result.chunks),
        )
        document.chunks = self._to_models(user_id=user_id, result=result)
        try:
            self.repository.add(document)
            self.session.commit()
            self.session.refresh(document)
        except IntegrityError:
            self.session.rollback()
            duplicate = self.repository.get_by_hash(
                user_id=user_id, content_hash=result.content_hash
            )
            if duplicate:
                raise DuplicateDocumentError(duplicate.id) from None
            raise
        except Exception:
            self.session.rollback()
            raise
        return DocumentDetail.model_validate(document)

    @staticmethod
    def _to_models(*, user_id: str, result) -> list[DocumentChunk]:
        return [
            DocumentChunk(
                user_id=user_id,
                position=chunk.position,
                section_path=chunk.section_path,
                chunk_type=chunk.chunk_type,
                content=chunk.content,
                contextualized_content=chunk.contextualized_content,
                char_count=chunk.char_count,
                estimated_token_count=chunk.estimated_token_count,
                content_hash=chunk.content_hash,
                parser_version=PARSER_VERSION,
                index_version=INDEX_VERSION,
                embedding_model=None,
            )
            for chunk in result.chunks
        ]

    def _get_owned_document(
        self, *, user_id: str, document_id: str, with_chunks: bool = False
    ) -> KnowledgeDocument:
        document = self.repository.get(
            user_id=user_id, document_id=document_id, with_chunks=with_chunks
        )
        if document is None:
            raise DocumentNotFoundError(document_id)
        return document
