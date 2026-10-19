from time import perf_counter

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import DocumentNotFoundError
from app.domains.retrieval.embeddings import (
    EmbeddingAdapter,
    cosine_similarity,
    create_embedding_adapter,
)
from app.domains.retrieval.ranking import (
    RankedItem,
    bm25_rank,
    create_reranker,
    reciprocal_rank_fusion,
)
from app.domains.retrieval.repository import ChunkRecord, RetrievalRepository
from app.domains.retrieval.schemas import (
    IndexRequest,
    IndexResponse,
    RetrievalMode,
    SearchHit,
    SearchRequest,
    SearchResponse,
)


class RetrievalService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        embedding_adapter: EmbeddingAdapter | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.embedding = embedding_adapter or create_embedding_adapter(
            self.settings.embedding_provider, self.settings.embedding_model
        )
        self.repository = RetrievalRepository(session)
        self.reranker = create_reranker(
            self.settings.reranker_provider, self.settings.reranker_model
        )

    def index(self, *, user_id: str, payload: IndexRequest) -> IndexResponse:
        if payload.document_id and not self.repository.document_exists(
            user_id=user_id, document_id=payload.document_id
        ):
            raise DocumentNotFoundError(payload.document_id)
        total_chunks = self.repository.count_chunks(
            user_id=user_id, document_id=payload.document_id
        )
        chunks = self.repository.pending_chunks(
            user_id=user_id,
            model_name=self.embedding.model_name,
            document_id=payload.document_id,
            force=payload.force,
        )
        vectors = self.embedding.embed([chunk.contextualized_content for chunk in chunks])
        try:
            for chunk, vector in zip(chunks, vectors):
                self.repository.replace_embedding(
                    chunk=chunk,
                    model_name=self.embedding.model_name,
                    vector=vector,
                )
                chunk.embedding_model = self.embedding.model_name
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return IndexResponse(
            model_name=self.embedding.model_name,
            indexed_chunks=len(chunks),
            skipped_chunks=max(total_chunks - len(chunks), 0) if not payload.force else 0,
        )

    def search(self, *, user_id: str, payload: SearchRequest) -> SearchResponse:
        started = perf_counter()
        records = self.repository.list_chunks(
            user_id=user_id,
            model_name=self.embedding.model_name,
            document_type=payload.document_type,
            document_id=payload.document_id,
            chunk_type=payload.chunk_type,
        )
        record_by_id = {record.chunk.id: record for record in records}
        texts = {record.chunk.id: record.chunk.contextualized_content for record in records}
        query_vector = self.embedding.embed([payload.query])[0]
        if self.repository.uses_postgresql:
            keyword = [
                RankedItem(item_id, score)
                for item_id, score in self.repository.postgres_keyword_rank(
                    query=payload.query,
                    chunk_ids=list(texts),
                    limit=payload.candidate_k,
                )
            ]
            dense = [
                RankedItem(item_id, score)
                for item_id, score in self.repository.postgres_dense_rank(
                    query_vector=query_vector,
                    chunk_ids=list(texts),
                    model_name=self.embedding.model_name,
                    limit=payload.candidate_k,
                )
            ]
        else:
            keyword = bm25_rank(payload.query, texts)[: payload.candidate_k]
            dense = sorted(
                (
                    RankedItem(
                        item_id=record.chunk.id,
                        score=cosine_similarity(query_vector, record.embedding),
                    )
                    for record in records
                    if record.embedding is not None
                ),
                key=lambda item: (-item.score, item.item_id),
            )[: payload.candidate_k]
        if payload.mode == RetrievalMode.keyword:
            ranking = keyword
        elif payload.mode == RetrievalMode.dense:
            ranking = dense
        else:
            ranking = reciprocal_rank_fusion([keyword, dense])[: payload.candidate_k]

        rerank_scores: dict[str, float] = {}
        if payload.mode == RetrievalMode.rerank:
            rerank_scores = dict(
                zip(
                    [item.item_id for item in ranking],
                    self.reranker.score(
                        payload.query,
                        [texts[item.item_id] for item in ranking],
                    ),
                )
            )
            ranking = sorted(
                ranking,
                key=lambda item: (-rerank_scores[item.item_id], -item.score, item.item_id),
            )

        keyword_scores = {item.item_id: item.score for item in keyword}
        dense_scores = {item.item_id: item.score for item in dense}
        fusion_scores = {item.item_id: item.score for item in ranking}
        hits = [
            self._to_hit(
                record_by_id[item.item_id],
                records,
                expand_parent=payload.expand_parent,
                keyword_score=keyword_scores.get(item.item_id),
                dense_score=dense_scores.get(item.item_id),
                fusion_score=fusion_scores.get(item.item_id)
                if payload.mode in {RetrievalMode.hybrid, RetrievalMode.rerank}
                else None,
                rerank_score=rerank_scores.get(item.item_id),
            )
            for item in ranking[: payload.top_k]
        ]
        return SearchResponse(
            query=payload.query,
            mode=payload.mode,
            embedding_model=self.embedding.model_name,
            reranker_model=(
                self.reranker.model_name if payload.mode == RetrievalMode.rerank else None
            ),
            latency_ms=round((perf_counter() - started) * 1000, 3),
            candidates_considered=len(records),
            items=hits,
        )

    @staticmethod
    def _to_hit(
        record: ChunkRecord,
        all_records: list[ChunkRecord],
        *,
        expand_parent: bool,
        keyword_score: float | None,
        dense_score: float | None,
        fusion_score: float | None,
        rerank_score: float | None,
    ) -> SearchHit:
        expanded = None
        if expand_parent:
            siblings = [
                candidate.chunk.content
                for candidate in all_records
                if candidate.chunk.document_id == record.chunk.document_id
                and candidate.chunk.section_path == record.chunk.section_path
            ]
            combined = "\n".join(siblings)
            expanded = combined if combined != record.chunk.content else None
        return SearchHit(
            chunk_id=record.chunk.id,
            document_id=record.chunk.document_id,
            document_name=record.document_name,
            document_type=record.document_type,
            section_path=record.chunk.section_path,
            chunk_type=record.chunk.chunk_type,
            content=record.chunk.content,
            expanded_content=expanded,
            keyword_score=keyword_score,
            dense_score=dense_score,
            fusion_score=fusion_score,
            rerank_score=rerank_score,
        )
