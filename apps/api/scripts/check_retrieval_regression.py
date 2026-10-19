"""Fail CI when the selected retrieval configuration drops below quality gates."""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report",
        type=Path,
        default=REPO_ROOT / "evals" / "reports" / "week3_week4_baseline.json",
    )
    parser.add_argument("--model", default="careerpilot-hash-1024-v2")
    parser.add_argument("--strategy", default="title-aware")
    parser.add_argument("--mode", default="rerank")
    parser.add_argument("--min-recall", type=float, default=0.95)
    parser.add_argument("--min-mrr", type=float, default=0.70)
    parser.add_argument("--min-ndcg", type=float, default=0.75)
    parser.add_argument("--max-p95-ms", type=float, default=100.0)
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    selected = next(
        (
            result
            for result in report["results"]
            if result["embedding_model"] == args.model
            and result["chunk_strategy"] == args.strategy
            and result["mode"] == args.mode
        ),
        None,
    )
    if selected is None:
        print("Regression gate failed: configuration not found.")
        return 2
    checks = {
        "recall_at_5": selected["recall_at_5"] >= args.min_recall,
        "mrr_at_10": selected["mrr_at_10"] >= args.min_mrr,
        "ndcg_at_10": selected["ndcg_at_10"] >= args.min_ndcg,
        "p95_latency_ms": selected["p95_latency_ms"] <= args.max_p95_ms,
    }
    failed = [name for name, passed in checks.items() if not passed]
    summary = {
        key: selected[key]
        for key in (
            "embedding_model",
            "chunk_strategy",
            "mode",
            "query_count",
            "recall_at_5",
            "mrr_at_10",
            "ndcg_at_10",
            "p95_latency_ms",
            "failure_count",
        )
        if key in selected
    }
    print(json.dumps({"configuration": summary, "checks": checks}, ensure_ascii=False))
    if failed:
        print(f"Regression gate failed: {', '.join(failed)}")
        return 1
    print("Retrieval regression gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
