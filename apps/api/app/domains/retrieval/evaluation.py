import math
from dataclasses import dataclass
from time import perf_counter

from app.domains.retrieval.embeddings import EmbeddingAdapter, cosine_similarity
from app.domains.retrieval.ranking import (
    OverlapReranker,
    RankedItem,
    bm25_rank,
    reciprocal_rank_fusion,
)


@dataclass(frozen=True)
class EvalDocument:
    document_id: str
    title: str
    text: str


@dataclass(frozen=True)
class EvalQuery:
    query_id: str
    query: str
    relevant_document_ids: list[str]
    relevance_grades: dict[str, int]


@dataclass(frozen=True)
class EvalChunk:
    chunk_id: str
    document_id: str
    text: str


def chunk_documents(
    documents: list[EvalDocument], strategy: str, *, chunk_size: int = 240
) -> list[EvalChunk]:
    chunks: list[EvalChunk] = []
    for document in documents:
        sections = _sections(document.text)
        if strategy == "fixed":
            pieces = [
                document.text[index : index + chunk_size]
                for index in range(0, len(document.text), chunk_size)
            ]
        elif strategy == "title-aware":
            pieces = [f"{document.title}\n{heading}\n{body}" for heading, body in sections]
        elif strategy == "parent-child":
            pieces = []
            for heading, body in sections:
                parent = f"{document.title}\n{heading}\n{body}"
                children = [line.strip("-*• ") for line in body.splitlines() if line.strip()]
                pieces.extend(f"{parent}\n证据：{child}" for child in children)
        else:
            raise ValueError(f"Unsupported chunk strategy: {strategy}")
        chunks.extend(
            EvalChunk(
                chunk_id=f"{document.document_id}:{strategy}:{index}",
                document_id=document.document_id,
                text=piece,
            )
            for index, piece in enumerate(pieces)
            if piece.strip()
        )
    return chunks


def evaluate_configuration(
    *,
    documents: list[EvalDocument],
    queries: list[EvalQuery],
    adapter: EmbeddingAdapter,
    chunk_strategy: str,
    mode: str,
    top_k: int = 10,
    include_failures: bool = False,
) -> dict[str, object]:
    chunks = chunk_documents(documents, chunk_strategy)
    texts = {chunk.chunk_id: chunk.text for chunk in chunks}
    chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    vectors = dict(zip(texts, adapter.embed(list(texts.values()))))
    reranker = OverlapReranker()
    latencies: list[float] = []
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    ndcgs: list[float] = []
    failures: list[dict[str, object]] = []
    for query in queries:
        started = perf_counter()
        keyword = bm25_rank(query.query, texts)[:30]
        query_vector = adapter.embed([query.query])[0]
        dense = sorted(
            (
                RankedItem(chunk_id, cosine_similarity(query_vector, vector))
                for chunk_id, vector in vectors.items()
            ),
            key=lambda item: (-item.score, item.item_id),
        )[:30]
        if mode == "keyword":
            ranking = keyword
        elif mode == "dense":
            ranking = dense
        else:
            ranking = reciprocal_rank_fusion([keyword, dense])[:30]
        if mode == "rerank":
            scores = reranker.score(query.query, [texts[item.item_id] for item in ranking])
            ranking = [
                item
                for item, _ in sorted(
                    zip(ranking, scores),
                    key=lambda pair: (-pair[1], -pair[0].score, pair[0].item_id),
                )
            ]
        ranked_documents = _unique_documents(ranking, chunk_by_id)[:top_k]
        latencies.append((perf_counter() - started) * 1000)
        relevant = set(query.relevant_document_ids)
        if not relevant:
            continue
        hits = relevant & set(ranked_documents[:5])
        recalls.append(len(hits) / len(relevant))
        first_rank = next(
            (rank for rank, doc_id in enumerate(ranked_documents, 1) if doc_id in relevant),
            None,
        )
        reciprocal_ranks.append(1 / first_rank if first_rank else 0.0)
        ndcgs.append(_ndcg(ranked_documents, query.relevance_grades, top_k))
        if include_failures and first_rank != 1:
            failures.append(
                {
                    "query_id": query.query_id,
                    "query": query.query,
                    "failure_type": "recall_miss" if not hits else "ranking_error",
                    "first_relevant_rank": first_rank,
                    "relevant_document_ids": query.relevant_document_ids,
                    "returned_top_5": ranked_documents[:5],
                }
            )
    result: dict[str, object] = {
        "embedding_model": adapter.model_name,
        "chunk_strategy": chunk_strategy,
        "mode": mode,
        "query_count": len(queries),
        "chunk_count": len(chunks),
        "recall_at_5": round(_mean(recalls), 4),
        "mrr_at_10": round(_mean(reciprocal_ranks), 4),
        "ndcg_at_10": round(_mean(ndcgs), 4),
        "p95_latency_ms": round(_percentile(latencies, 0.95), 3),
        "estimated_cost_usd": 0.0,
    }
    if include_failures:
        result["failure_count"] = len(failures)
        result["failures"] = failures
    return result


def _sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    heading = "正文"
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if lines:
                sections.append((heading, "\n".join(lines)))
            heading = stripped[3:]
            lines = []
        else:
            lines.append(line)
    if lines:
        sections.append((heading, "\n".join(lines)))
    return sections or [("正文", text)]


def _unique_documents(ranking: list[RankedItem], chunk_by_id: dict[str, EvalChunk]) -> list[str]:
    result: list[str] = []
    for item in ranking:
        document_id = chunk_by_id[item.item_id].document_id
        if document_id not in result:
            result.append(document_id)
    return result


def _ndcg(ranking: list[str], grades: dict[str, int], k: int) -> float:
    dcg = sum(
        (2 ** grades.get(document_id, 0) - 1) / math.log2(rank + 1)
        for rank, document_id in enumerate(ranking[:k], start=1)
    )
    ideal = sorted(grades.values(), reverse=True)[:k]
    ideal_dcg = sum(
        (2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(ideal, start=1)
    )
    return dcg / ideal_dcg if ideal_dcg else 0.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(math.ceil(len(ordered) * percentile) - 1, len(ordered) - 1)
    return ordered[max(index, 0)]
