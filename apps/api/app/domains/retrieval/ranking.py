import math
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from app.domains.retrieval.embeddings import tokenize


@dataclass(frozen=True)
class RankedItem:
    item_id: str
    score: float


def bm25_rank(query: str, documents: dict[str, str]) -> list[RankedItem]:
    query_terms = tokenize(query)
    document_terms = {key: tokenize(value) for key, value in documents.items()}
    average_length = (
        sum(len(terms) for terms in document_terms.values()) / len(document_terms)
        if document_terms
        else 1.0
    )
    document_frequency = Counter(term for terms in document_terms.values() for term in set(terms))
    total = len(document_terms)
    ranked: list[RankedItem] = []
    for item_id, terms in document_terms.items():
        frequencies = Counter(terms)
        score = 0.0
        for term in query_terms:
            frequency = frequencies[term]
            if not frequency:
                continue
            inverse_frequency = math.log(
                1 + (total - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5)
            )
            denominator = frequency + 1.2 * (1 - 0.75 + 0.75 * len(terms) / max(average_length, 1))
            score += inverse_frequency * frequency * 2.2 / denominator
        if score > 0:
            ranked.append(RankedItem(item_id=item_id, score=score))
    return sorted(ranked, key=lambda item: (-item.score, item.item_id))


def reciprocal_rank_fusion(rankings: list[list[RankedItem]], *, k: int = 60) -> list[RankedItem]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item.item_id] = scores.get(item.item_id, 0.0) + 1 / (k + rank)
    return sorted(
        (RankedItem(item_id=item_id, score=score) for item_id, score in scores.items()),
        key=lambda item: (-item.score, item.item_id),
    )


class OverlapReranker:
    model_name = "careerpilot-overlap-reranker-v1"

    def score(self, query: str, documents: list[str]) -> list[float]:
        query_terms = set(tokenize(query))
        return [
            len(query_terms & set(tokenize(document))) / max(len(query_terms), 1)
            for document in documents
        ]


class SentenceTransformerCrossEncoderReranker:
    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError("使用真实 Cross-Encoder 前请安装：pip install -e '.[ml]'") from exc
        repository, separator, revision = model_name.rpartition("@")
        if separator and (not repository or not revision):
            raise ValueError("MODEL_REFERENCE_INVALID: expected repository@revision")
        self.model_name = model_name
        self._model = CrossEncoder(
            repository if separator else model_name,
            revision=revision if separator else None,
        )

    def score(self, query: str, documents: list[str]) -> list[float]:
        values = self._model.predict([(query, document) for document in documents])
        results: list[float] = []
        for value in values:
            raw = float(value)
            results.append(raw if 0 <= raw <= 1 else 1 / (1 + math.exp(-raw)))
        return results


@lru_cache(maxsize=4)
def create_reranker(provider: str, model_name: str):
    if provider == "deterministic":
        reranker = OverlapReranker()
        reranker.model_name = model_name
        return reranker
    if provider == "sentence-transformers":
        return SentenceTransformerCrossEncoderReranker(model_name)
    raise ValueError(f"Unsupported reranker provider: {provider}")
