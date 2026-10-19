from fastapi.testclient import TestClient

from app.domains.retrieval.embeddings import DeterministicEmbeddingAdapter
from app.domains.retrieval.evaluation import (
    EvalDocument,
    EvalQuery,
    evaluate_configuration,
)
from app.domains.retrieval.ranking import RankedItem, reciprocal_rank_fusion


def import_document(client: TestClient, *, name: str, text: str) -> str:
    response = client.post(
        "/api/v1/documents/text",
        json={
            "display_name": name,
            "document_type": "learning_note",
            "raw_text": text,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_index_and_search_all_retrieval_modes(client: TestClient) -> None:
    rag_id = import_document(
        client,
        name="RAG 笔记",
        text="## 检索增强生成\nRAG 使用向量检索、关键词召回和重排提高回答证据质量。",
    )
    import_document(
        client,
        name="前端笔记",
        text="## Vue\nVue 3 使用 Composition API 和 TypeScript 构建交互页面。",
    )
    index_response = client.post("/api/v1/retrieval/index", json={})
    assert index_response.status_code == 200
    assert index_response.json()["indexed_chunks"] == 2
    second_index = client.post("/api/v1/retrieval/index", json={})
    assert second_index.json()["indexed_chunks"] == 0
    assert second_index.json()["skipped_chunks"] == 2

    for mode in ("keyword", "dense", "hybrid", "rerank"):
        response = client.post(
            "/api/v1/retrieval/search",
            json={"query": "RAG 向量检索", "mode": mode, "top_k": 2},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["items"][0]["document_id"] == rag_id
        assert payload["latency_ms"] >= 0
        if mode == "rerank":
            assert payload["items"][0]["rerank_score"] is not None


def test_retrieval_is_scoped_by_user(client: TestClient) -> None:
    import_document(
        client,
        name="私有笔记",
        text="## 私有\n这是 demo-user 的 FastAPI 私人知识库内容。",
    )
    client.post("/api/v1/retrieval/index", json={})
    response = client.post(
        "/api/v1/retrieval/search",
        headers={"X-User-ID": "another-user"},
        json={"query": "FastAPI", "mode": "hybrid"},
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_index_unknown_document_returns_404(client: TestClient) -> None:
    response = client.post("/api/v1/retrieval/index", json={"document_id": "missing-document"})
    assert response.status_code == 404
    assert response.json()["code"] == "DOCUMENT_NOT_FOUND"


def test_search_rejects_top_k_larger_than_candidate_window(client: TestClient) -> None:
    response = client.post(
        "/api/v1/retrieval/search",
        json={"query": "RAG", "top_k": 10, "candidate_k": 5},
    )
    assert response.status_code == 422


def test_rrf_fuses_rank_positions_without_mixing_raw_scores() -> None:
    fused = reciprocal_rank_fusion(
        [
            [RankedItem("a", 99), RankedItem("b", 1)],
            [RankedItem("b", 0.9), RankedItem("c", 0.8)],
        ]
    )
    assert fused[0].item_id == "b"


def test_evaluation_returns_retrieval_metrics() -> None:
    report = evaluate_configuration(
        documents=[
            EvalDocument("rag", "RAG", "## 技术\n检索增强生成 FastAPI"),
            EvalDocument("vue", "Vue", "## 技术\nVue 3 TypeScript"),
        ],
        queries=[
            EvalQuery("q1", "RAG FastAPI", ["rag"], {"rag": 3}),
        ],
        adapter=DeterministicEmbeddingAdapter(),
        chunk_strategy="title-aware",
        mode="hybrid",
    )
    assert report["recall_at_5"] == 1.0
    assert report["mrr_at_10"] == 1.0
    assert report["ndcg_at_10"] == 1.0
