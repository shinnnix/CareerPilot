import hashlib
import math
import re
from collections.abc import Iterable
from typing import Protocol

VECTOR_DIMENSIONS = 1024

CONCEPT_ALIASES = {
    "rag": ("rag", "检索增强生成", "retrieval augmented generation"),
    "llm": ("llm", "大模型", "大语言模型"),
    "vue": ("vue", "vue3", "vue 3", "vue.js"),
    "postgresql": ("postgresql", "postgres"),
    "remote": ("remote", "远程"),
}


class EmbeddingAdapter(Protocol):
    model_name: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    for canonical, aliases in CONCEPT_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            lowered += f" {canonical}"
    ascii_terms = re.findall(r"[a-z][a-z0-9.+#-]*|\d+", lowered)
    chinese_runs = re.findall(r"[\u4e00-\u9fff]+", lowered)
    chinese_terms = [
        run[index : index + 2] for run in chinese_runs for index in range(max(1, len(run) - 1))
    ]
    return ascii_terms + chinese_terms


class DeterministicEmbeddingAdapter:
    """Feature-hashing baseline for tests and offline pipeline smoke checks.

    It is intentionally not presented as a neural model benchmark. Production
    experiments should select the sentence-transformers provider.
    """

    dimensions = VECTOR_DIMENSIONS

    def __init__(self, model_name: str = "careerpilot-hash-1024-v1") -> None:
        self.model_name = model_name
        self._seed = b"v2" if model_name.endswith("v2") else b"v1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        features = tokenize(text)
        if self._seed == b"v2":
            compact = re.sub(r"\s+", "", text.lower())
            features += [compact[i : i + 3] for i in range(max(1, len(compact) - 2))]
        for feature in features:
            digest = hashlib.blake2b(
                feature.encode("utf-8"), digest_size=8, key=self._seed
            ).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class SentenceTransformerEmbeddingAdapter:
    dimensions = VECTOR_DIMENSIONS

    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("使用真实 Embedding 前请安装：pip install -e '.[ml]'") from exc
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return [_fit_dimensions(vector.tolist()) for vector in vectors]


def create_embedding_adapter(provider: str, model_name: str) -> EmbeddingAdapter:
    if provider == "deterministic":
        return DeterministicEmbeddingAdapter(model_name)
    if provider == "sentence-transformers":
        return SentenceTransformerEmbeddingAdapter(model_name)
    raise ValueError(f"Unsupported embedding provider: {provider}")


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    left_values = list(left)
    right_values = list(right)
    dot = sum(a * b for a, b in zip(left_values, right_values))
    left_norm = math.sqrt(sum(value * value for value in left_values))
    right_norm = math.sqrt(sum(value * value for value in right_values))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _fit_dimensions(vector: list[float]) -> list[float]:
    if len(vector) > VECTOR_DIMENSIONS:
        vector = vector[:VECTOR_DIMENSIONS]
    elif len(vector) < VECTOR_DIMENSIONS:
        vector = vector + [0.0] * (VECTOR_DIMENSIONS - len(vector))
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]
