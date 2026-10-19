from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domains.documents.model import DocumentType, ParseStatus, ReviewStatus


class ExtractedDocumentData(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    skills: list[str] = Field(default_factory=list, max_length=100)
    section_titles: list[str] = Field(default_factory=list, max_length=100)
    desired_cities: list[str] = Field(default_factory=list, max_length=20)
    available_days_per_week: int | None = Field(default=None, ge=1, le=7)
    available_months: int | None = Field(default=None, ge=1, le=36)


class DocumentTextImport(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    document_type: DocumentType
    raw_text: str = Field(min_length=20, max_length=200_000)


class DocumentCorrection(BaseModel):
    extracted_data: ExtractedDocumentData


class DocumentSummary(BaseModel):
    id: str
    display_name: str
    file_name: str | None
    mime_type: str
    document_type: DocumentType
    content_hash: str
    source_size_bytes: int
    parse_status: ParseStatus
    parse_version: str
    parse_confidence: Decimal
    review_status: ReviewStatus
    prompt_injection_detected: bool
    security_flags: list[str]
    index_version: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentDetail(DocumentSummary):
    raw_text: str
    extracted_data: ExtractedDocumentData
    confirmed_at: datetime | None


class DocumentList(BaseModel):
    items: list[DocumentSummary]
    page: int
    page_size: int
    total: int


class ChunkRead(BaseModel):
    id: str
    document_id: str
    position: int
    section_path: list[str]
    chunk_type: str
    content: str
    contextualized_content: str
    char_count: int
    estimated_token_count: int
    content_hash: str
    parser_version: str
    index_version: str
    embedding_model: str | None

    model_config = ConfigDict(from_attributes=True)


class ChunkList(BaseModel):
    items: list[ChunkRead]
    total: int
