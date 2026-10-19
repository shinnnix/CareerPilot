"""Run E1-E4 without an LLM judge and write a reproducible JSON report."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
sys.path.insert(0, str(API_ROOT))

from app.domains.retrieval.embeddings import (
    DeterministicEmbeddingAdapter,
    SentenceTransformerEmbeddingAdapter,
)
from app.domains.retrieval.evaluation import (
    EvalDocument,
    EvalQuery,
    evaluate_configuration,
)


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--models",
        nargs="+",
        default=["careerpilot-hash-1024-v1", "careerpilot-hash-1024-v2"],
        help="Hash baselines or sentence-transformers model ids",
    )
    arguments = parser.parse_args()
    documents = [
        EvalDocument(**record)
        for record in read_jsonl(REPO_ROOT / "datasets" / "retrieval_corpus.jsonl")
    ]
    queries = [
        EvalQuery(
            query_id=str(record["query_id"]),
            query=str(record["query"]),
            relevant_document_ids=list(record["relevant_document_ids"]),
            relevance_grades=dict(record["relevance_grades"]),
        )
        for record in read_jsonl(REPO_ROOT / "datasets" / "retrieval_gold.jsonl")
    ]
    results = []
    for model in arguments.models:
        adapter = (
            DeterministicEmbeddingAdapter(model)
            if model.startswith("careerpilot-hash-")
            else SentenceTransformerEmbeddingAdapter(model)
        )
        for strategy in ("fixed", "title-aware", "parent-child"):
            for mode in ("keyword", "dense", "hybrid", "rerank"):
                results.append(
                    evaluate_configuration(
                        documents=documents,
                        queries=queries,
                        adapter=adapter,
                        chunk_strategy=strategy,
                        mode=mode,
                        include_failures=True,
                    )
                )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "documents": len(documents),
            "queries": len(queries),
            "double_reviewed": 24,
            "nature": "synthetic anonymized starter set",
        },
        "warning": (
            "hash adapters validate the experiment pipeline, not Qwen/BGE quality; "
            "install the ml extra and rerun with real model adapters before model selection"
        ),
        "results": results,
    }
    report_dir = REPO_ROOT / "evals" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    output = report_dir / "week3_week4_baseline.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
