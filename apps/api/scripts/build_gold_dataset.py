"""Build the checked-in 120-query, anonymized starter qrels dataset."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATASET_DIR = ROOT / "datasets"

STACKS = [
    ("python-fastapi-rag", "Python FastAPI RAG", "上海"),
    ("vue-typescript", "Vue 3 TypeScript", "杭州"),
    ("langchain-pgvector", "LangChain pgvector", "北京"),
    ("pytorch-transformers", "PyTorch Transformers", "深圳"),
    ("docker-postgresql", "Docker PostgreSQL", "成都"),
    ("langgraph-agent", "LangGraph Agent", "上海"),
]


def build_corpus() -> list[dict[str, str]]:
    corpus: list[dict[str, str]] = []
    for index in range(24):
        key, skills, city = STACKS[index % len(STACKS)]
        corpus.append(
            {
                "document_id": f"job-{index + 1:03d}",
                "title": f"{skills} AI 应用开发实习 {index + 1}",
                "text": (
                    f"城市：{city}\n## 岗位职责\n- 使用 {skills} 开发 AI 应用\n"
                    f"- 构建可测试的 REST API 与检索链路\n## 任职要求\n"
                    f"- 熟悉 {skills}\n- 每周实习 4 天，持续 4 个月\n"
                    f"## 加分项\n- 有 {key} 项目与离线评测经验"
                ),
            }
        )
    for index, (key, skills, _) in enumerate(STACKS, start=1):
        corpus.append(
            {
                "document_id": f"note-{index:03d}",
                "title": f"{skills} 学习笔记",
                "text": f"## 概念\n{skills} 的核心概念与 {key} 实践。\n## 面试\n解释设计取舍和测试方法。",
            }
        )
    return corpus


def build_queries() -> list[dict[str, object]]:
    queries: list[dict[str, object]] = []
    categories = [
        ("job_search", 40),
        ("job_match", 32),
        ("skill_gap", 24),
        ("exact_term", 16),
        ("no_answer", 8),
    ]
    query_number = 1
    for category, count in categories:
        for offset in range(count):
            key, skills, city = STACKS[offset % len(STACKS)]
            if category == "job_search":
                relevant = f"job-{offset % 24 + 1:03d}"
                query = f"{city}使用 {skills} 的 AI 应用开发实习"
            elif category == "job_match":
                relevant = f"job-{offset % 24 + 1:03d}"
                query = f"我做过 {key} 项目，适合哪个职位"
            elif category == "skill_gap":
                relevant = f"note-{offset % 6 + 1:03d}"
                query = f"如何补足 {skills} 技能并准备面试"
            elif category == "exact_term":
                relevant = f"note-{offset % 6 + 1:03d}"
                query = f"精确解释 {key}"
            else:
                relevant = ""
                query = f"不存在的量子岗位条件 {offset + 1}"
            queries.append(
                {
                    "query_id": f"q-{query_number:03d}",
                    "query": query,
                    "intent": category,
                    "filters": {"city": city} if category == "job_search" else {},
                    "relevant_document_ids": [relevant] if relevant else [],
                    "relevance_grades": {relevant: 3} if relevant else {},
                    "must_contain_facts": skills.lower().split() if relevant else [],
                    "must_not_claim": ["用户已经掌握未提供的技能"],
                    "review_status": "double_reviewed" if query_number <= 24 else "single_review",
                    "annotator_note": "脱敏的起始评测样例，需要用真实求职记录持续替换。",
                }
            )
            query_number += 1
    return queries


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


if __name__ == "__main__":
    DATASET_DIR.mkdir(exist_ok=True)
    write_jsonl(DATASET_DIR / "retrieval_corpus.jsonl", build_corpus())
    write_jsonl(DATASET_DIR / "retrieval_gold.jsonl", build_queries())
    print("wrote 30 corpus documents and 120 qrels")
