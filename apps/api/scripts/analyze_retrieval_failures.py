"""Turn machine-readable retrieval failures into an interview-ready analysis note."""

import json
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
REPORT = REPO_ROOT / "evals" / "reports" / "week3_week4_baseline.json"
OUTPUT = REPO_ROOT / "evals" / "reports" / "week7_failure_analysis.md"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    target = next(
        result
        for result in report["results"]
        if result["embedding_model"] == "careerpilot-hash-1024-v2"
        and result["chunk_strategy"] == "title-aware"
        and result["mode"] == "rerank"
    )
    failures = target.get("failures", [])
    failure_types = Counter(item["failure_type"] for item in failures)
    lines = [
        "# 第 7 周检索失败样例分析",
        "",
        "> 配置：`careerpilot-hash-1024-v2 + title-aware + rerank`。数据集是合成匿名入门集，结论不能替代真实职位查询评测。",
        "",
        "## 回归指标",
        "",
        f"- Recall@5：{target['recall_at_5']}",
        f"- MRR@10：{target['mrr_at_10']}",
        f"- NDCG@10：{target['ndcg_at_10']}",
        f"- P95 延迟：{target['p95_latency_ms']} ms（本机离线基准）",
        f"- 未排第一的查询：{len(failures)}；类型统计：{dict(failure_types)}",
        "",
        "## 代表性失败样例",
        "",
    ]
    for item in failures[:10]:
        lines.extend(
            [
                f"### {item['query_id']} · {item['failure_type']}",
                "",
                f"- 查询：{item['query']}",
                f"- 首个相关结果名次：{item['first_relevant_rank']}",
                f"- 标注相关文档：{', '.join(item['relevant_document_ids'])}",
                f"- 实际 Top 5：{', '.join(item['returned_top_5'])}",
                "",
            ]
        )
    lines.extend(
        [
            "## 根因与下一轮实验",
            "",
            "1. 目前主要是排序错误而非 Recall@5 漏召回，优先改进重排特征，不应盲目增大 Top K。",
            "2. Hash Embedding 只用于跑通实验与回归流程；应在同一标注集复测 BGE-M3/Qwen3-Embedding，并记录显存、吞吐和费用。",
            "3. 合成集仅 30 篇且 Recall@5 饱和，需要加入真实 JD、同义技能和否定条件等困难负例。",
            "4. 每次调整切分、Embedding 或融合权重后先跑回归门禁，再人工查看新增失败样例。",
            "",
        ]
    )
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
