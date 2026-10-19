from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.api.dependencies import (
    get_current_user_id,
    get_document_service,
)
from app.core.errors import ErrorResponse
from app.domains.documents.file_text import MAX_UPLOAD_BYTES
from app.domains.documents.model import DocumentType, ReviewStatus
from app.domains.documents.schemas import (
    ChunkList,
    DocumentCorrection,
    DocumentDetail,
    DocumentList,
    DocumentTextImport,
)
from app.domains.documents.service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])

DOCUMENT_ERRORS = {
    404: {"model": ErrorResponse, "description": "Document not found"},
    409: {"model": ErrorResponse, "description": "Duplicate document"},
    415: {"model": ErrorResponse, "description": "Unsupported document"},
    422: {"model": ErrorResponse, "description": "Invalid document data"},
}


@router.get("", response_model=DocumentList)
def list_documents(
    service: Annotated[DocumentService, Depends(get_document_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    document_type: Annotated[DocumentType | None, Query()] = None,
    review_status: Annotated[ReviewStatus | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DocumentList:
    return service.list_documents(
        user_id=user_id,
        document_type=document_type,
        review_status=review_status,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/text",
    response_model=DocumentDetail,
    status_code=status.HTTP_201_CREATED,
    responses=DOCUMENT_ERRORS,
)
def import_text_document(
    payload: DocumentTextImport,
    service: Annotated[DocumentService, Depends(get_document_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> DocumentDetail:
    return service.import_text(user_id=user_id, payload=payload)


@router.post(
    "/upload",
    response_model=DocumentDetail,
    status_code=status.HTTP_201_CREATED,
    responses=DOCUMENT_ERRORS,
)
def upload_document(
    service: Annotated[DocumentService, Depends(get_document_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
    file: Annotated[UploadFile, File(description="TXT, Markdown or text-based PDF")],
    display_name: Annotated[str, Form(min_length=1, max_length=200)],
    document_type: Annotated[DocumentType, Form()],
) -> DocumentDetail:
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    return service.import_upload(
        user_id=user_id,
        display_name=display_name,
        document_type=document_type,
        file_name=file.filename or display_name,
        content=content,
    )


@router.get("/{document_id}", response_model=DocumentDetail, responses=DOCUMENT_ERRORS)
def get_document(
    document_id: str,
    service: Annotated[DocumentService, Depends(get_document_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> DocumentDetail:
    return service.get_document(user_id=user_id, document_id=document_id)


@router.get("/{document_id}/chunks", response_model=ChunkList, responses=DOCUMENT_ERRORS)
def get_document_chunks(
    document_id: str,
    service: Annotated[DocumentService, Depends(get_document_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> ChunkList:
    return service.get_chunks(user_id=user_id, document_id=document_id)


@router.patch("/{document_id}", response_model=DocumentDetail, responses=DOCUMENT_ERRORS)
def correct_document(
    document_id: str,
    payload: DocumentCorrection,
    service: Annotated[DocumentService, Depends(get_document_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> DocumentDetail:
    return service.correct_document(user_id=user_id, document_id=document_id, payload=payload)


@router.post("/{document_id}/reindex", response_model=DocumentDetail, responses=DOCUMENT_ERRORS)
def reindex_document(
    document_id: str,
    service: Annotated[DocumentService, Depends(get_document_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> DocumentDetail:
    return service.reindex_document(user_id=user_id, document_id=document_id)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: DOCUMENT_ERRORS[404]},
)
def delete_document(
    document_id: str,
    service: Annotated[DocumentService, Depends(get_document_service)],
    user_id: Annotated[str, Depends(get_current_user_id)],
) -> Response:
    service.delete_document(user_id=user_id, document_id=document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
