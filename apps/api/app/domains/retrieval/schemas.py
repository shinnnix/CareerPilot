from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.domains.documents.model import DocumentType


class RetrievalMode(str, Enum):
    keyword = "keyword"
    dense = "dense"
    hybrid = "hybrid"
    rerank = "rerank"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    mode: RetrievalMode = RetrievalMode.hybrid
    document_type: DocumentType | None = None
    document_id: str | None = None
    chunk_type: str | None = Field(default=None, max_length=50)
    top_k: int = Field(default=5, ge=1, le=20)
    candidate_k: int = Field(default=30, ge=5, le=100)
    expand_parent: bool = True

    @model_validator(mode="after")
    def validate_candidate_window(self) -> "SearchRequest":
        if self.candidate_k < self.top_k:
            raise ValueError("candidate_k must be greater than or equal to top_k")
        return self


class SearchHit(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    document_type: DocumentType
    section_path: list[str]
    chunk_type: str
    content: str
    expanded_content: str | None = None
    keyword_score: float | None = None
    dense_score: float | None = None
    fusion_score: float | None = None
    rerank_score: float | None = None


class SearchResponse(BaseModel):
    query: str
    mode: RetrievalMode
    embedding_model: str
    reranker_model: str | None = None
    latency_ms: float
    candidates_considered: int
    items: list[SearchHit]


class IndexRequest(BaseModel):
    document_id: str | None = None
    force: bool = False


class IndexResponse(BaseModel):
    model_name: str
    indexed_chunks: int
    skipped_chunks: int
