from fastapi.testclient import TestClient

DOCUMENT_TEXT = """AI 应用开发实习生
公司：星河智能
工作地点：上海

岗位职责：
- 使用 FastAPI 开发 API
- 建设 RAG 私人知识库

任职要求：
- 熟悉 Python 和 PostgreSQL
- 了解 Vue 3
"""


def import_document(
    client: TestClient, *, user_id: str = "demo-user", text: str = DOCUMENT_TEXT
) -> dict[str, object]:
    response = client.post(
        "/api/v1/documents/text",
        json={
            "display_name": "星河智能 AI 实习",
            "document_type": "job_description",
            "raw_text": text,
        },
        headers={"X-User-ID": user_id},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_import_text_creates_structured_data_and_chunks(client: TestClient) -> None:
    document = import_document(client)

    assert document["parse_status"] == "parsed"
    assert document["review_status"] == "pending"
    assert document["parse_version"] == "rule-parser-v1"
    assert document["index_version"] == "title-aware-v1"
    assert document["chunk_count"] >= 4
    assert document["extracted_data"]["company_name"] == "星河智能"
    assert "rag" in document["extracted_data"]["skills"]

    chunks = client.get(f"/api/v1/documents/{document['id']}/chunks")
    assert chunks.status_code == 200
    assert chunks.json()["total"] == document["chunk_count"]
    assert any(chunk["section_path"][-1] == "任职要求" for chunk in chunks.json()["items"])


def test_duplicate_content_returns_existing_document_id(client: TestClient) -> None:
    document = import_document(client)

    response = client.post(
        "/api/v1/documents/text",
        json={
            "display_name": "另一个名称",
            "document_type": "job_description",
            "raw_text": DOCUMENT_TEXT.replace("\n", "\r\n"),
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "DUPLICATE_DOCUMENT"
    assert response.json()["details"]["existing_document_id"] == document["id"]


def test_upload_markdown_document(client: TestClient) -> None:
    content = "# 项目经历\n\n- 使用 FastAPI 完成后端接口\n- 使用 Vue 3 完成前端页面"

    response = client.post(
        "/api/v1/documents/upload",
        data={"display_name": "我的简历", "document_type": "resume"},
        files={"file": ("resume.md", content.encode("utf-8"), "text/markdown")},
    )

    assert response.status_code == 201, response.text
    result = response.json()
    assert result["file_name"] == "resume.md"
    assert result["mime_type"] == "text/markdown"
    assert result["chunk_count"] == 2


def test_manual_correction_confirms_without_faking_parser_confidence(
    client: TestClient,
) -> None:
    document = import_document(client)
    original_confidence = document["parse_confidence"]

    response = client.patch(
        f"/api/v1/documents/{document['id']}",
        json={
            "extracted_data": {
                **document["extracted_data"],
                "city": "上海市",
                "skills": [*document["extracted_data"]["skills"], "sqlalchemy"],
            },
        },
    )

    assert response.status_code == 200
    corrected = response.json()
    assert corrected["review_status"] == "confirmed"
    assert corrected["confirmed_at"] is not None
    assert corrected["parse_confidence"] == original_confidence
    assert corrected["extracted_data"]["city"] == "上海市"


def test_reindex_replaces_chunks_and_resets_review(client: TestClient) -> None:
    document = import_document(client)
    client.patch(
        f"/api/v1/documents/{document['id']}",
        json={"extracted_data": document["extracted_data"]},
    )

    response = client.post(f"/api/v1/documents/{document['id']}/reindex")
    chunks = client.get(f"/api/v1/documents/{document['id']}/chunks").json()

    assert response.status_code == 200
    assert response.json()["review_status"] == "pending"
    assert response.json()["confirmed_at"] is None
    assert chunks["total"] == response.json()["chunk_count"]
    assert len({chunk["position"] for chunk in chunks["items"]}) == chunks["total"]


def test_documents_are_isolated_and_delete_cascades(client: TestClient) -> None:
    document = import_document(client, user_id="user-a")

    hidden = client.get(f"/api/v1/documents/{document['id']}", headers={"X-User-ID": "user-b"})
    deleted = client.delete(f"/api/v1/documents/{document['id']}", headers={"X-User-ID": "user-a"})
    chunks_after_delete = client.get(
        f"/api/v1/documents/{document['id']}/chunks",
        headers={"X-User-ID": "user-a"},
    )

    assert hidden.status_code == 404
    assert deleted.status_code == 204
    assert chunks_after_delete.status_code == 404


def test_list_filters_by_type_and_review_status(client: TestClient) -> None:
    import_document(client)
    import_document(
        client,
        text="# 项目经历\n\n使用 Python 与 FastAPI 构建一个完整的职位管理系统，并编写自动化测试。",
    )

    response = client.get(
        "/api/v1/documents",
        params={"document_type": "job_description", "review_status": "pending"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_rejects_unsupported_upload(client: TestClient) -> None:
    response = client.post(
        "/api/v1/documents/upload",
        data={"display_name": "不支持的文件", "document_type": "other"},
        files={"file": ("data.csv", b"a,b,c\n1,2,3", "text/csv")},
    )

    assert response.status_code == 415
    assert response.json()["code"] == "UNSUPPORTED_DOCUMENT"
