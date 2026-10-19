# 第 7 周检索失败样例分析

> 配置：`careerpilot-hash-1024-v2 + title-aware + rerank`。数据集是合成匿名入门集，结论不能替代真实职位查询评测。

## 回归指标

- Recall@5：1.0
- MRR@10：0.7336
- NDCG@10：0.8005
- P95 延迟：17.975 ms（本机离线基准）
- 未排第一的查询：48；类型统计：{'ranking_error': 48}

## 代表性失败样例

### q-007 · ranking_error

- 查询：上海使用 Python FastAPI RAG 的 AI 应用开发实习
- 首个相关结果名次：2
- 标注相关文档：job-007
- 实际 Top 5：job-001, job-007, job-013, job-019, job-012

### q-008 · ranking_error

- 查询：杭州使用 Vue 3 TypeScript 的 AI 应用开发实习
- 首个相关结果名次：2
- 标注相关文档：job-008
- 实际 Top 5：job-002, job-008, job-014, job-020, job-003

### q-009 · ranking_error

- 查询：北京使用 LangChain pgvector 的 AI 应用开发实习
- 首个相关结果名次：2
- 标注相关文档：job-009
- 实际 Top 5：job-003, job-009, job-015, job-021, job-006

### q-010 · ranking_error

- 查询：深圳使用 PyTorch Transformers 的 AI 应用开发实习
- 首个相关结果名次：2
- 标注相关文档：job-010
- 实际 Top 5：job-004, job-010, job-016, job-022, job-003

### q-011 · ranking_error

- 查询：成都使用 Docker PostgreSQL 的 AI 应用开发实习
- 首个相关结果名次：2
- 标注相关文档：job-011
- 实际 Top 5：job-005, job-011, job-017, job-023, job-003

### q-012 · ranking_error

- 查询：上海使用 LangGraph Agent 的 AI 应用开发实习
- 首个相关结果名次：2
- 标注相关文档：job-012
- 实际 Top 5：job-006, job-012, job-018, job-024, job-007

### q-013 · ranking_error

- 查询：上海使用 Python FastAPI RAG 的 AI 应用开发实习
- 首个相关结果名次：3
- 标注相关文档：job-013
- 实际 Top 5：job-001, job-007, job-013, job-019, job-012

### q-014 · ranking_error

- 查询：杭州使用 Vue 3 TypeScript 的 AI 应用开发实习
- 首个相关结果名次：3
- 标注相关文档：job-014
- 实际 Top 5：job-002, job-008, job-014, job-020, job-003

### q-015 · ranking_error

- 查询：北京使用 LangChain pgvector 的 AI 应用开发实习
- 首个相关结果名次：3
- 标注相关文档：job-015
- 实际 Top 5：job-003, job-009, job-015, job-021, job-006

### q-016 · ranking_error

- 查询：深圳使用 PyTorch Transformers 的 AI 应用开发实习
- 首个相关结果名次：3
- 标注相关文档：job-016
- 实际 Top 5：job-004, job-010, job-016, job-022, job-003

## 根因与下一轮实验

1. 目前主要是排序错误而非 Recall@5 漏召回，优先改进重排特征，不应盲目增大 Top K。
2. Hash Embedding 只用于跑通实验与回归流程；应在同一标注集复测 BGE-M3/Qwen3-Embedding，并记录显存、吞吐和费用。
3. 合成集仅 30 篇且 Recall@5 饱和，需要加入真实 JD、同义技能和否定条件等困难负例。
4. 每次调整切分、Embedding 或融合权重后先跑回归门禁，再人工查看新增失败样例。
