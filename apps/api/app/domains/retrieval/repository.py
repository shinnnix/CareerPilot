from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.domains.documents.model import (
    ChunkEmbedding,
    DocumentChunk,
    DocumentType,
    KnowledgeDocument,
)


@dataclass(frozen=True)
class ChunkRecord:
    chunk: DocumentChunk
    document_name: str
    document_type: DocumentType
    embedding: list[float] | None


class RetrievalRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_chunks(
        self,
        *,
        user_id: str,
        model_name: str,
        document_type: DocumentType | None = None,
        document_id: str | None = None,
        chunk_type: str | None = None,
    ) -> list[ChunkRecord]:
        statement = (
            select(DocumentChunk, KnowledgeDocument, ChunkEmbedding)
            .join(KnowledgeDocument, KnowledgeDocument.id == DocumentChunk.document_id)
            .outerjoin(
                ChunkEmbedding,
                (ChunkEmbedding.chunk_id == DocumentChunk.id)
                & (ChunkEmbedding.model_name == model_name),
            )
            .where(DocumentChunk.user_id == user_id)
            .where(KnowledgeDocument.prompt_injection_detected.is_(False))
            .order_by(DocumentChunk.document_id, DocumentChunk.position)
        )
        if document_type:
            statement = statement.where(KnowledgeDocument.document_type == document_type)
        if document_id:
            statement = statement.where(DocumentChunk.document_id == document_id)
        if chunk_type:
            statement = statement.where(DocumentChunk.chunk_type == chunk_type)
        return [
            ChunkRecord(
                chunk=chunk,
                document_name=document.display_name,
                document_type=document.document_type,
                embedding=(
                    embedding.embedding.tolist()
                    if embedding is not None and hasattr(embedding.embedding, "tolist")
                    else list(embedding.embedding)
                    if embedding is not None
                    else None
                ),
            )
            for chunk, document, embedding in self.session.execute(statement)
        ]

    def document_exists(self, *, user_id: str, document_id: str) -> bool:
        return (
            self.session.scalar(
                select(KnowledgeDocument.id).where(
                    KnowledgeDocument.id == document_id,
                    KnowledgeDocument.user_id == user_id,
                )
            )
            is not None
        )

    def pending_chunks(
        self, *, user_id: str, model_name: str, document_id: str | None, force: bool
    ) -> list[DocumentChunk]:
        statement = (
            select(DocumentChunk)
            .join(KnowledgeDocument, KnowledgeDocument.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.user_id == user_id,
                KnowledgeDocument.prompt_injection_detected.is_(False),
            )
        )
        if document_id:
            statement = statement.where(DocumentChunk.document_id == document_id)
        if not force:
            existing = select(ChunkEmbedding.chunk_id).where(
                ChunkEmbedding.model_name == model_name
            )
            statement = statement.where(DocumentChunk.id.not_in(existing))
        return list(self.session.scalars(statement.order_by(DocumentChunk.id)))

    def count_chunks(self, *, user_id: str, document_id: str | None) -> int:
        statement = (
            select(func.count())
            .select_from(DocumentChunk)
            .join(KnowledgeDocument, KnowledgeDocument.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.user_id == user_id,
                KnowledgeDocument.prompt_injection_detected.is_(False),
            )
        )
        if document_id:
            statement = statement.where(DocumentChunk.document_id == document_id)
        return int(self.session.scalar(statement) or 0)

    def replace_embedding(
        self,
        *,
        chunk: DocumentChunk,
        model_name: str,
        vector: list[float],
    ) -> None:
        self.session.execute(
            delete(ChunkEmbedding).where(
                ChunkEmbedding.chunk_id == chunk.id,
                ChunkEmbedding.model_name == model_name,
            )
        )
        self.session.add(
            ChunkEmbedding(
                chunk_id=chunk.id,
                user_id=chunk.user_id,
                model_name=model_name,
                dimensions=len(vector),
                embedding=vector,
            )
        )

    @property
    def uses_postgresql(self) -> bool:
        bind = self.session.get_bind()
        return bind.dialect.name == "postgresql"

    def postgres_keyword_rank(
        self, *, query: str, chunk_ids: list[str], limit: int
    ) -> list[tuple[str, float]]:
        if not chunk_ids:
            return []
        search_query = func.websearch_to_tsquery("simple", query)
        vector = func.to_tsvector("simple", DocumentChunk.contextualized_content)
        score = func.ts_rank_cd(vector, search_query).label("score")
        statement = (
            select(DocumentChunk.id, score)
            .where(DocumentChunk.id.in_(chunk_ids), vector.op("@@")(search_query))
            .order_by(score.desc(), DocumentChunk.id)
            .limit(limit)
        )
        return [(chunk_id, float(value)) for chunk_id, value in self.session.execute(statement)]

    def postgres_dense_rank(
        self,
        *,
        query_vector: list[float],
        chunk_ids: list[str],
        model_name: str,
        limit: int,
    ) -> list[tuple[str, float]]:
        if not chunk_ids:
            return []
        distance = ChunkEmbedding.embedding.cosine_distance(query_vector)
        statement = (
            select(ChunkEmbedding.chunk_id, distance.label("distance"))
            .where(
                ChunkEmbedding.chunk_id.in_(chunk_ids),
                ChunkEmbedding.model_name == model_name,
            )
            .order_by(distance, ChunkEmbedding.chunk_id)
            .limit(limit)
        )
        return [
            (chunk_id, 1.0 - float(value)) for chunk_id, value in self.session.execute(statement)
        ]
