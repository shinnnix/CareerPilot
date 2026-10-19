# CareerPilot 实习简历项目说明

> 用途：投递 AI 应用开发、Python 后端或 AI 全栈实习。时间、链接和部署地址请按本人真实情况替换，不能把合成评测写成线上业务效果。

**简历项目链接：** `GitHub：<发布仓库后替换为真实 URL>`  ·  **本地演示：** `http://localhost:8080`（仅本机）

# 第一部分：3 天项目上手与后端面试冲刺指南

## 1. 三天后的目标

三天不是要逐行背完整个仓库，而是要达到下面四个层级：

1. **能讲清楚**：不看代码，用 1–2 分钟说明产品目标、总体架构、核心数据流和主要技术取舍；
2. **能跑通**：独立启动数据库和后端，完成登录、职位 CRUD、文档导入、索引、检索、Agent 确认和账号删除；
3. **能修改**：可以在现有分层中增加一个字段、一个筛选条件或一个只读 Agent Tool，并补迁移与测试；
4. **能定位问题**：知道接口错误、事务异常、检索退化、权限串库和 Agent 重复写入分别从哪一层排查。

时间分配建议：后端与数据库约 45%，RAG 与 Agent 约 35%，安全、测试和部署约 15%，Vue 约 5%。前端只需理解页面如何通过 Axios 调用 API、如何保存页面状态、如何处理登录和错误，不必在三天内深入 CSS 和组件库。

### 学习优先级

- **P0，必须能独立讲解和演示**：FastAPI 请求链、Schema/ORM/Migration、事务与用户隔离、文档三种表示、Hybrid/RRF/Rerank、评测指标、LangGraph 确认/恢复/幂等、JWT 与 Prompt Injection 防护；
- **P1，必须理解设计取舍**：申请状态机、Citation 校验、HNSW、限流、结构化日志、健康检查和 Docker Compose；
- **P2，知道入口和边界即可**：Vue 视觉细节、Element Plus、真实模型部署、Redis/任务队列、Kubernetes 和大规模压测。这些是后续优化，不要在三天内挤占 P0 时间。

## 2. 先建立项目全景

### 2.1 一句话产品定义

CareerPilot 是一个帮助用户管理 AI 实习职位、建立私人求职知识库、评估岗位匹配、生成有证据的准备材料，并通过人工确认安全执行申请管理操作的全栈 Agent。

### 2.2 后端分层

```text
HTTP Request
→ FastAPI Router：HTTP 方法、状态码、依赖注入、响应模型
→ Service：业务规则、用例编排、事务边界
→ Repository / Retriever：SQL、用户隔离、检索候选
→ PostgreSQL / pgvector：结构化数据、原文、Chunk、向量、事件

Agent Request
→ LangGraph：路由、计划、暂停、恢复
→ 受控 Tool
→ 已有 Service
→ 人工确认后才允许写操作
```

面试前必须能解释：Router 不直接写 SQL；Service 不处理 HTTP 细节；Repository 不决定业务状态转换；Agent Tool 不绕过 Service 直接操作数据库。

### 2.3 六条核心业务链路

1. 注册/登录 → Bearer Token → 用户级职位 CRUD；
2. 导入简历/JD → 规范化 → 结构化字段 → 标题感知 Chunk；
3. Chunk 建立向量 → Keyword/Dense 召回 → RRF → Rerank；
4. 职位硬条件检查 → 技能匹配 → 带证据的匹配报告；
5. Agent 意图路由 → 只读 Tool 自动运行 / 写 Tool 等待确认 → 幂等执行；
6. 密码二次确认 → 单事务删除账号及全部私人数据。

## 3. 必读代码：按顺序阅读，不要按目录随机翻

### 3.1 第一层：应用入口与 HTTP 合同（约 1.5 小时）

| 顺序 | 代码 | 重点看什么 | 看完要能回答 |
|---|---|---|---|
| 1 | [`app/main.py`](apps/api/app/main.py) | FastAPI 创建、CORS、Request ID、限流、结构化日志、健康检查、路由挂载 | 一个请求进入应用后先后经过什么？liveness 和 readiness 有何区别？ |
| 2 | [`core/config.py`](apps/api/app/core/config.py) | Pydantic Settings、环境变量、生产安全校验 | 为什么配置不能散落在代码里？生产环境为什么拒绝默认密钥和演示身份？ |
| 3 | [`core/errors.py`](apps/api/app/core/errors.py) | 业务异常、统一错误响应、参数校验错误 | 为什么错误需要稳定 code，而不能只返回字符串？ |
| 4 | [`api/v1/router.py`](apps/api/app/api/v1/router.py) | 各领域 Router 聚合 | API 为什么统一放在 `/api/v1`？ |
| 5 | [`api/v1/jobs.py`](apps/api/app/api/v1/jobs.py) | GET/POST/PATCH/DELETE、依赖注入、状态码、response model | RESTful API 中 POST、PATCH、DELETE 应如何设计？ |

阅读方法：先打开 Swagger 的一个接口，再对照 Router 看输入 Schema、依赖和返回类型；不要一开始钻进 ORM。

#### 看完代码后必须回答

| 问题 | 合格回答要点 | 回看位置 |
|---|---|---|
| 一个请求从进入应用到返回，经过哪些关键环节？ | 请求边界中间件生成或校验 Request ID、执行限流、调用路由，路由再通过依赖注入获得用户与 Service；响应返回时记录状态码和耗时，并回传 `X-Request-ID`。 | [`request_boundary()`](apps/api/app/main.py)、[`api/dependencies.py`](apps/api/app/api/dependencies.py) |
| 为什么业务错误不能只返回一句字符串？ | 客户端需要依赖稳定的错误 `code` 做分支处理，`message` 可以调整或国际化；统一结构还要带 Request ID，便于把用户报错与服务端日志关联。 | [`core/errors.py`](apps/api/app/core/errors.py)、[`main.py`](apps/api/app/main.py) |
| `response_model` 除了生成 Swagger 文档，还有什么作用？ | 它校验并裁剪响应，避免 ORM 对象中的密码哈希、内部字段等被意外序列化，是 API 输出边界。 | [`api/v1/jobs.py`](apps/api/app/api/v1/jobs.py)、[`auth/schemas.py`](apps/api/app/domains/auth/schemas.py) |
| `/health/live` 与 `/health/ready` 为什么不能合并？ | live 只确认进程可运行；ready 还验证数据库依赖，失败时应停止接收流量，但不一定立即重启进程。 | [`liveness()` 与 `readiness()`](apps/api/app/main.py) |
| 为什么统一使用 `/api/v1`？ | 给客户端稳定版本合同，使未来不兼容升级可以并存迁移；健康检查这类基础设施接口不必放在业务版本下。 | [`api/v1/router.py`](apps/api/app/api/v1/router.py)、[`main.py`](apps/api/app/main.py) |

### 3.2 第二层：最标准的后端纵切——职位 CRUD（约 2 小时）

按下面顺序完整跟踪一次 `POST /jobs` 和一次 `PATCH /jobs/{id}`：

1. [`jobs/schemas.py`](apps/api/app/domains/jobs/schemas.py)：区分创建、更新、读取 Schema，关注跨字段校验；
2. [`jobs/model.py`](apps/api/app/domains/jobs/model.py)：ORM 字段、枚举、索引、UTC 时间和 `Numeric`；
3. [`jobs/service.py`](apps/api/app/domains/jobs/service.py)：业务用例、提交/回滚、404 与删除保护；
4. [`jobs/repository.py`](apps/api/app/domains/jobs/repository.py)：分页、筛选和 `user_id` 数据隔离；
5. [`20260729_0001_create_jobs.py`](apps/api/migrations/versions/20260729_0001_create_jobs.py)：数据库真实结构如何由迁移创建；
6. [`test_jobs_api.py`](apps/api/tests/test_jobs_api.py)：成功、参数错误、分页和跨用户访问如何验收。

必须掌握的区别：

- Pydantic Schema 是 API 边界合同，负责输入输出校验；
- SQLAlchemy Model 是数据库映射，负责表、列、关系和约束；
- Alembic Migration 是数据库结构的历史变更，不能因为 Model 已修改就省略；
- Service 决定事务何时提交，Repository 只封装数据访问。

#### 看完代码后必须回答

| 问题 | 合格回答要点 | 回看位置 |
|---|---|---|
| `JobCreate`、`JobUpdate`、`JobRead` 为什么分开？ | 创建字段、部分更新字段和对外返回字段的必填性不同；拆分后能防止客户端写入服务端字段，也能让 PATCH 真正只修改已提供字段。 | [`jobs/schemas.py`](apps/api/app/domains/jobs/schemas.py) |
| 薪资为什么使用 `Decimal/Numeric(12,2)`，而不是 `float`？ | 二进制浮点不能精确表示很多十进制金额，比较、求和和边界校验可能出现误差；`Decimal` 与数据库 `Numeric` 能保持十进制定点语义。 | [`jobs/model.py`](apps/api/app/domains/jobs/model.py)、[`jobs/schemas.py`](apps/api/app/domains/jobs/schemas.py) |
| 为什么 Repository 的读取必须接收 `user_id`？ | 用户身份必须进入 SQL 查询条件，在数据库读取阶段就完成租户隔离；先按 ID 查出对象再在内存判断，容易漏判并暴露对象是否存在。 | [`jobs/repository.py`](apps/api/app/domains/jobs/repository.py)、[`api/dependencies.py`](apps/api/app/api/dependencies.py) |
| 为什么 Service 负责 `commit/rollback/refresh`？ | 一个业务用例可能包含多次写入，Service 知道原子边界；失败时统一回滚，提交后 refresh 才能得到数据库生成的 ID、时间等字段。 | [`jobs/service.py`](apps/api/app/domains/jobs/service.py) |
| 为什么删除已有关联申请的职位返回 409？ | 数据库 `RESTRICT` 守住最终完整性，Service 先给出可理解的冲突错误；这比级联删除求职历史更符合业务语义。 | [`jobs/service.py`](apps/api/app/domains/jobs/service.py)、[`applications/model.py`](apps/api/app/domains/applications/model.py) |
| Model 改完后为什么还必须有 Migration？ | ORM 只描述当前代码期望的结构，不会自动、安全地变更已有数据库；Migration 才是可审计、可回滚和可部署的结构历史。 | [`migrations/versions`](apps/api/migrations/versions/)、[`migrations/env.py`](apps/api/migrations/env.py) |

### 3.3 第三层：私人知识库与数据建模（约 2 小时）

重点文件：

- [`documents/model.py`](apps/api/app/domains/documents/model.py)：Document、Chunk、Embedding 三层数据；
- [`documents/parser.py`](apps/api/app/domains/documents/parser.py)：文本规范化、字段抽取、章节识别和标题感知切分；
- [`documents/service.py`](apps/api/app/domains/documents/service.py)：导入、去重、重新索引、人工纠正和删除；
- [`documents/repository.py`](apps/api/app/domains/documents/repository.py)：文档归属查询和 Chunk 替换；
- [`core/content_security.py`](apps/api/app/core/content_security.py)：不可信文档的 Prompt Injection 扫描；
- [`test_documents_api.py`](apps/api/tests/test_documents_api.py) 与 [`test_document_parser.py`](apps/api/tests/test_document_parser.py)：解析、重复导入、删除级联和隔离测试。

看完要能解释为什么同一份资料保存三种表示：

- 结构化字段用于精确筛选、排序和统计；
- 规范化原文用于审计、展示和重新解析；
- 语义 Chunk 用于关键词与向量检索。

切分不是越细越好：太大导致一个向量混入多个主题，太小则上下文不足并增加向量数量。项目保留章节路径，并给子 Chunk 补父标题，让短片段仍然带有语义上下文。

#### 看完代码后必须回答

| 问题 | 合格回答要点 | 回看位置 |
|---|---|---|
| 为什么一份文档要同时保存结构化字段、规范化原文和 Chunk？ | 三者分别服务于筛选统计、审计重解析、语义检索；只存 Chunk 会丢失原始证据，只存原文又无法高效过滤与召回。 | [`documents/model.py`](apps/api/app/domains/documents/model.py)、[`documents/parser.py`](apps/api/app/domains/documents/parser.py) |
| 文档去重为什么既在应用层检查，又有数据库唯一约束？ | 应用层通过内容哈希快速返回友好错误；数据库的 `(user_id, content_hash)` 唯一约束处理并发导入竞态，二者缺一不可。 | [`documents/service.py`](apps/api/app/domains/documents/service.py)、[`documents/model.py`](apps/api/app/domains/documents/model.py) |
| 标题感知切分比固定字符切分多保留了什么？ | 它保留章节路径，并把父标题带入子块，使“负责模型评测”这类短句仍带有“项目经历/职责”等上下文。 | [`build_chunks()`](apps/api/app/domains/documents/parser.py)、[`test_document_parser.py`](apps/api/tests/test_document_parser.py) |
| 重新索引为什么要放在同一事务中？ | 旧 Chunk/Embedding 的替换与新索引写入应原子完成；中途失败必须回滚，否则查询会看到半新半旧的知识库。 | [`documents/service.py`](apps/api/app/domains/documents/service.py)、[`retrieval/service.py`](apps/api/app/domains/retrieval/service.py) |
| 为什么用户上传的简历仍然要做 Prompt Injection 扫描？ | 被检索文本会进入模型上下文，文档中的“忽略系统指令”等内容可能劫持模型；用户拥有文档不代表内容可信。 | [`core/content_security.py`](apps/api/app/core/content_security.py)、[`test_week7_security.py`](apps/api/tests/test_week7_security.py) |
| 删除文档后 Chunk 与 Embedding 如何避免成为孤儿数据？ | 外键级联负责完整性，测试验证删除行为；业务层仍负责检查归属，避免删除其他用户的数据。 | [`documents/model.py`](apps/api/app/domains/documents/model.py)、[`test_documents_api.py`](apps/api/tests/test_documents_api.py) |

### 3.4 第四层：RAG 检索与评测（约 3 小时）

按数据流阅读：

1. [`retrieval/embeddings.py`](apps/api/app/domains/retrieval/embeddings.py)：Embedding Adapter、确定性测试向量和真实模型适配；
2. [`retrieval/ranking.py`](apps/api/app/domains/retrieval/ranking.py)：BM25、RRF、Reranker；
3. [`retrieval/repository.py`](apps/api/app/domains/retrieval/repository.py)：PostgreSQL FTS、pgvector 距离查询、安全文档过滤；
4. [`retrieval/service.py`](apps/api/app/domains/retrieval/service.py)：索引和四种检索模式的编排；
5. [`retrieval/evaluation.py`](apps/api/app/domains/retrieval/evaluation.py)：Recall、MRR、NDCG、P95；
6. [`run_retrieval_eval.py`](apps/api/scripts/run_retrieval_eval.py) 与 [`check_retrieval_regression.py`](apps/api/scripts/check_retrieval_regression.py)：实验矩阵和回归门禁；
7. [`week7_failure_analysis.md`](evals/reports/week7_failure_analysis.md)：平均指标之外如何分析具体失败。

面试必须掌握：

- 关键词检索擅长技能名、城市、框架版本等精确匹配；Dense 擅长语义改写；
- 两种召回分数不可直接相加，RRF 使用排名位置融合，减少尺度校准问题；
- Reranker 只处理有限候选，提高精度并控制延迟；
- Recall@5 衡量相关结果是否被召回，MRR 强调第一个相关结果的位置，NDCG 同时考虑位置和分级相关性；
- 当前 Recall@5 为 1.0 只代表小型合成集 Top 5 已饱和，MRR 0.7336 和 48 个排序错误说明第一名仍需优化。

#### 看完代码后必须回答

| 问题 | 合格回答要点 | 回看位置 |
|---|---|---|
| 一份 Chunk 从导入到可检索经历什么？ | 文档规范化与切分后生成 Chunk，Embedding Adapter 批量编码并保存模型名和向量；查询时先做用户与安全过滤，再按模式召回、融合、重排并截取 Top K。 | [`documents/service.py`](apps/api/app/domains/documents/service.py)、[`retrieval/service.py`](apps/api/app/domains/retrieval/service.py) |
| Keyword、Dense、Hybrid、Hybrid+Rerank 分别适合什么？ | Keyword 适合精确术语且便宜；Dense 适合语义改写但有推理成本；Hybrid 用 RRF 合并互补召回；Rerank 对少量候选做更贵的成对判断以改善头部排序。 | [`retrieval/ranking.py`](apps/api/app/domains/retrieval/ranking.py)、[`retrieval/service.py`](apps/api/app/domains/retrieval/service.py) |
| 为什么 RRF 不直接相加 BM25 分数与余弦相似度？ | 两类分数尺度、分布与含义不同，直接加权需要反复校准；RRF 只使用排名位置，以 `1/(k+rank)` 融合，作为稳健基线。 | [`reciprocal_rank_fusion()`](apps/api/app/domains/retrieval/ranking.py) |
| PostgreSQL 与 SQLite 的检索路径为什么不同？ | 生产路径利用 PostgreSQL FTS 与 pgvector；测试环境的 SQLite 不支持这些能力，所以采用可重复的本地实现验证业务编排，但它不能替代真实数据库性能测试。 | [`retrieval/repository.py`](apps/api/app/domains/retrieval/repository.py)、[`tests/conftest.py`](apps/api/tests/conftest.py) |
| Recall@5 为 1.0 为什么不代表检索已经完成？ | 它只说明相关文档在小型合成集的前五名出现；MRR 0.7336 与失败样本显示第一名排序仍有问题，也没有覆盖真实数据分布与在线延迟。 | [`retrieval/evaluation.py`](apps/api/app/domains/retrieval/evaluation.py)、[`week7_failure_analysis.md`](evals/reports/week7_failure_analysis.md) |
| 如何选择向量模型而不是只看排行榜？ | 固定真实查询、相关性标注、切分与候选数，对候选模型比较 Recall/MRR/NDCG、P95、索引体积、吞吐和价格，再按质量门槛下的总成本选择。 | [`run_retrieval_eval.py`](apps/api/scripts/run_retrieval_eval.py)、[`check_retrieval_regression.py`](apps/api/scripts/check_retrieval_regression.py) |

### 3.5 第五层：可解释匹配与证据约束（约 1.5 小时）

- [`matching/skills.py`](apps/api/app/domains/matching/skills.py)：技能别名如何规范化；
- [`matching/service.py`](apps/api/app/domains/matching/service.py)：城市、到岗时间等硬条件与技能软评分为什么分开；
- [`applications/service.py`](apps/api/app/domains/applications/service.py)：申请状态机、反馈、个性化材料与 Citation 校验；
- [`applications/model.py`](apps/api/app/domains/applications/model.py)：当前状态、历史事件和生成产物如何存储；
- [`test_matching_api.py`](apps/api/tests/test_matching_api.py) 与 [`test_applications_api.py`](apps/api/tests/test_applications_api.py)：硬条件、状态转换、引用归属和职位删除保护。

核心认识：LLM 可以解释结果，但不负责城市冲突、金额计算、权限判断或最终匹配分。生成的简历要点必须引用用户自己的 Chunk；JD 只能证明岗位需要什么，不能证明用户会什么。

#### 看完代码后必须回答

| 问题 | 合格回答要点 | 回看位置 |
|---|---|---|
| 为什么硬条件与软评分要分开？ | 城市、到岗时间等不满足时应直接暴露冲突，不能让技能高分掩盖；技能覆盖适合连续评分和解释，两者混成一个分数会误导用户。 | [`MatchingService._hard_gate()`](apps/api/app/domains/matching/service.py)、[`matching/schemas.py`](apps/api/app/domains/matching/schemas.py) |
| 技能别名为什么必须统一规范化？ | `Vue.js`、`Vue3`、`vue` 若不归一会造成假缺口；同一套标准化应复用于匹配、检索和展示，避免不同模块结论冲突。 | [`matching/skills.py`](apps/api/app/domains/matching/skills.py)、[`matching/service.py`](apps/api/app/domains/matching/service.py) |
| 申请状态为什么使用有限状态机，而不是任意字符串更新？ | 业务只允许有意义的迁移，并要同时记录事件和关键时间；例如不允许从 `rejected` 随意跳回 `interviewing`。 | [`ALLOWED_TRANSITIONS`](apps/api/app/domains/applications/service.py)、[`applications/model.py`](apps/api/app/domains/applications/model.py) |
| Citation 校验具体检查什么？ | 用户、职位和简历归属必须一致；文档引用必须指向真实 Chunk 且引文存在于内容中，岗位引用必须来自当前 JD，空引用或伪造引用应拒绝保存。 | [`_validate_citations()`](apps/api/app/domains/applications/service.py)、[`applications/schemas.py`](apps/api/app/domains/applications/schemas.py) |
| 为什么 JD 引用不能证明候选人掌握某技能？ | JD 是岗位需求证据，不是个人经历证据；生成“我会某技能”必须引用用户自己的简历或项目 Chunk，否则属于证据类型错配。 | [`applications/service.py`](apps/api/app/domains/applications/service.py)、[`test_applications_api.py`](apps/api/tests/test_applications_api.py) |

### 3.6 第六层：LangGraph Agent（约 2.5 小时）

- [`agent/graph.py`](apps/api/app/domains/agent/graph.py)：状态、节点、条件路由、`interrupt`；
- [`agent/service.py`](apps/api/app/domains/agent/service.py)：Run 创建、恢复、Tool 调用、确认、幂等和事件；
- [`agent/model.py`](apps/api/app/domains/agent/model.py)：Run、Event、Tool Receipt；
- [`agent/schemas.py`](apps/api/app/domains/agent/schemas.py)：Agent 对外输入输出合同；
- [`api/v1/agent.py`](apps/api/app/api/v1/agent.py)：运行、确认、恢复和 SSE；
- [`test_agent_api.py`](apps/api/tests/test_agent_api.py)：只读执行、拒绝、重复确认、最大步数和恢复测试。

必须能讲清三个不同概念：

- **Checkpoint** 保存工作流进行到哪里，支持暂停后恢复；
- **Human-in-the-loop** 在产生副作用前让用户检查准确参数；
- **Idempotency** 保证确认请求或网络重试不会重复创建申请。

它们不能互相替代：能恢复不等于不会重复写，要求确认也不等于网络只会请求一次。

#### 看完代码后必须回答

| 问题 | 合格回答要点 | 回看位置 |
|---|---|---|
| Agent 从用户意图到结束有哪些状态？ | 图负责意图路由、动作规划、必要时中断等待确认并结束计划；持久层另存 Run 状态与 Event，使 API 可查询、恢复和审计。 | [`agent/graph.py`](apps/api/app/domains/agent/graph.py)、[`agent/model.py`](apps/api/app/domains/agent/model.py) |
| 为什么查职位可以直接执行，创建申请必须确认？ | 查询是可重复的只读操作，风险较低；创建申请会产生持久副作用，必须向用户展示工具名和准确参数后再执行。 | [`AgentService`](apps/api/app/domains/agent/service.py)、[`AgentView.vue`](apps/web/src/views/AgentView.vue) |
| 内存 Checkpointer 与数据库 Run/Event 分别解决什么？ | Checkpointer 保存图执行现场；Run/Event 保存跨 API 请求的业务状态和审计轨迹。当前 `InMemorySaver` 重启会丢，因此生产应换持久化 Checkpointer。 | [`CHECKPOINTER`](apps/api/app/domains/agent/graph.py)、[`agent/model.py`](apps/api/app/domains/agent/model.py) |
| 用户重复点击确认，为什么不会创建两次申请？ | 写工具使用 `(user_id, idempotency_key)` 唯一回执；重复请求读取已有结果，并由数据库唯一约束处理并发竞态。 | [`ToolReceipt`](apps/api/app/domains/agent/model.py)、[`agent/service.py`](apps/api/app/domains/agent/service.py) |
| 最大步数和输入校验分别阻止什么问题？ | 最大步数阻止循环或成本失控；执行前的必填参数校验阻止工具拿到残缺参数，二者都应在产生副作用前完成。 | [`agent/graph.py`](apps/api/app/domains/agent/graph.py)、[`agent/service.py`](apps/api/app/domains/agent/service.py)、[`test_agent_api.py`](apps/api/tests/test_agent_api.py) |
| SSE 在这里解决什么，不解决什么？ | 它按顺序向页面回放 Run 事件，改善进度可见性；当前实现不是消息队列，也不保证多实例下实时推送，生产仍需持久事件流或 Broker。 | [`stream_events()`](apps/api/app/api/v1/agent.py)、[`AgentView.vue`](apps/web/src/views/AgentView.vue) |

### 3.7 第七层：鉴权、安全与工程质量（约 2 小时）

- [`auth/security.py`](apps/api/app/domains/auth/security.py)：PBKDF2 密码哈希、HMAC 签名 Token、过期校验；
- [`api/dependencies.py`](apps/api/app/api/dependencies.py)：从 Token 得到可信用户身份；
- [`auth/service.py`](apps/api/app/domains/auth/service.py)：注册、登录和账号原子删除；
- [`core/rate_limit.py`](apps/api/app/core/rate_limit.py)：固定窗口限流及其单进程边界；
- [`main.py`](apps/api/app/main.py)：Request ID、脱敏 JSON 日志、429、存活与就绪检查；
- [`test_week7_security.py`](apps/api/tests/test_week7_security.py)：篡改 Token、生产身份、串库、删除、注入和限流；
- [`infra/docker-compose.yml`](infra/docker-compose.yml)：数据库健康检查、自动迁移、初始化数据和服务依赖。

#### 看完代码后必须回答

| 问题 | 合格回答要点 | 回看位置 |
|---|---|---|
| 密码哈希与访问 Token 签名有什么本质区别？ | PBKDF2 是带盐、刻意变慢的单向密码验证；Token 使用服务端密钥签名并校验过期时间，用于证明请求身份，不能把两者当作同一种“加密”。 | [`auth/security.py`](apps/api/app/domains/auth/security.py) |
| 认证通过后，为什么每条查询仍要带 `user_id`？ | Token 只证明“是谁”，授权还要限制“能访问什么”；若 Repository 漏掉用户条件，合法登录用户仍可能读取他人对象。 | [`api/dependencies.py`](apps/api/app/api/dependencies.py)、[`jobs/repository.py`](apps/api/app/domains/jobs/repository.py) |
| 为什么生产环境拒绝默认密钥和演示身份？ | 默认值公开且可预测，演示身份可能绕过正常认证；启动时 fail fast 比带着危险配置提供服务更安全。 | [`Settings.validate_production_security()`](apps/api/app/core/config.py)、[`test_week7_security.py`](apps/api/tests/test_week7_security.py) |
| 当前限流器为什么不能直接用于多实例生产？ | 计数保存在单进程内存，每个实例看到的窗口不同，重启也会清空；生产应使用 Redis 等共享、原子存储。 | [`core/rate_limit.py`](apps/api/app/core/rate_limit.py)、[`main.py`](apps/api/app/main.py) |
| 日志为什么记录 Request ID、路由、状态和耗时，却不记正文？ | 这些字段足以关联故障与慢请求；简历正文、Token 和请求体属于敏感数据，写入日志会扩大泄露面。 | [`main.py`](apps/api/app/main.py)、[`core/observability.py`](apps/api/app/core/observability.py) |
| 注销账号为什么必须是一个原子事务？ | 用户、文档、申请、Agent 事件和回执等数据要么全部删除，要么失败后全部保留，不能留下半删除账户。 | [`AuthService.purge_account()`](apps/api/app/domains/auth/service.py)、[`test_week7_security.py`](apps/api/tests/test_week7_security.py) |

### 3.8 前端只需要掌握的最小集合（约 1.5 小时）

1. [`router/index.ts`](apps/web/src/router/index.ts)：URL 如何映射页面、生产环境如何做登录守卫；
2. [`api/client.ts`](apps/web/src/api/client.ts)：Axios Base URL、Bearer Token、401 处理；
3. [`api/jobs.ts`](apps/web/src/api/jobs.ts)：TypeScript 如何封装 REST API；
4. [`views/JobListView.vue`](apps/web/src/views/JobListView.vue)：`ref/computed/onMounted` 和 loading/error 状态；
5. [`views/AgentView.vue`](apps/web/src/views/AgentView.vue)：运行状态、确认卡片和事件展示；
6. [`auth-storage.ts`](apps/web/src/auth-storage.ts)：为什么当前 Session Storage 只是阶段性方案。

前端面试只需能说明 Composition API、组件状态、API 层、路由和 TypeScript 类型如何协作；不要假装自己深入实现了复杂前端工程化。

#### 看完代码后必须回答

| 问题 | 合格回答要点 | 回看位置 |
|---|---|---|
| 页面、API 封装和通用 Client 为什么分三层？ | View 管交互与状态，领域 API 管请求路径和类型，Client 统一 Base URL、Token 与错误处理；这样接口变化和页面逻辑不会互相污染。 | [`JobListView.vue`](apps/web/src/views/JobListView.vue)、[`api/jobs.ts`](apps/web/src/api/jobs.ts)、[`api/client.ts`](apps/web/src/api/client.ts) |
| `ref`、`computed`、`onMounted` 在职位页各自做什么？ | `ref` 保存响应式列表和 loading/error，`computed` 派生展示数据，`onMounted` 在页面挂载后触发首次加载。 | [`JobListView.vue`](apps/web/src/views/JobListView.vue) |
| Bearer Token 在哪里加入请求，401 如何处理？ | Axios 请求拦截器从会话存储读取 Token 并设置 Authorization；响应遇到 401 时清理失效身份并引导重新登录。 | [`api/client.ts`](apps/web/src/api/client.ts)、[`auth-storage.ts`](apps/web/src/auth-storage.ts) |
| 为什么每个页面都必须显式处理 loading、empty 和 error？ | 网络请求不是瞬时且可能失败；没有这些状态会出现重复提交、空白页面或把“尚未加载”误认为“没有数据”。 | [`JobListView.vue`](apps/web/src/views/JobListView.vue)、[`AgentView.vue`](apps/web/src/views/AgentView.vue) |
| Session Storage 方案有什么边界？ | 它便于演示且关闭标签页后清理，但仍可被 XSS 读取；更成熟方案会结合严格 CSP、短期 Token、刷新机制或 HttpOnly Cookie 与 CSRF 防护。 | [`auth-storage.ts`](apps/web/src/auth-storage.ts)、[`api/client.ts`](apps/web/src/api/client.ts) |
| 前后端如何共享 REST 合同？ | 当前靠 Pydantic/OpenAPI 与手写 TypeScript 类型对齐；规模变大后应从 OpenAPI 生成 Client/类型，并用契约测试防漂移。 | [`jobs/schemas.py`](apps/api/app/domains/jobs/schemas.py)、[`api/jobs.ts`](apps/web/src/api/jobs.ts) |

## 4. 后端核心知识点清单

### 4.1 FastAPI 与 REST

- 依赖注入如何提供数据库 Session、当前用户和 Service；
- Pydantic 如何做字段、枚举、范围和跨字段校验；
- GET/POST/PATCH/DELETE 的语义及 200/201/204/401/404/409/422/429；
- `response_model` 为什么既是文档也是数据泄露边界；
- OpenAPI 如何作为前后端合同；
- 同步数据库 Session 不应被包装成假异步，CPU 密集任务未来应放入 Worker。

#### 项目内示例

| 知识点 | 本项目中的示例与设计理由 | 常见错误 | 代码位置 |
|---|---|---|---|
| 依赖注入 | Router 不自行创建数据库连接，而是通过 `Depends` 获取 Session、当前用户和领域 Service，便于测试替换数据库依赖并集中鉴权。 | 在每个接口里解析 Token、创建 Session，造成重复逻辑和资源泄漏。 | [`api/dependencies.py`](apps/api/app/api/dependencies.py)、[`api/v1/jobs.py`](apps/api/app/api/v1/jobs.py) |
| Pydantic 边界校验 | 创建职位时校验金额、枚举和区间；PATCH 使用“仅处理显式传入字段”，使未传字段与传入 `null` 的含义可区分。 | 把全部校验留到数据库，客户端只能收到晦涩异常；或 PATCH 意外清空未提交字段。 | [`jobs/schemas.py`](apps/api/app/domains/jobs/schemas.py)、[`jobs/service.py`](apps/api/app/domains/jobs/service.py) |
| REST 状态码 | 创建职位返回 201，成功删除返回 204；资源不存在或不属于当前用户统一返回 404，状态冲突返回 409，参数不合法返回 422，限流返回 429。 | 所有结果都返回 200，再把成功失败塞进正文；客户端和监控难以正确处理。 | [`api/v1/jobs.py`](apps/api/app/api/v1/jobs.py)、[`core/errors.py`](apps/api/app/core/errors.py)、[`main.py`](apps/api/app/main.py) |
| 输出模型 | `JobRead`、`UserRead` 等只公开合同字段，FastAPI 据此生成 OpenAPI 并过滤响应。 | 直接返回 ORM `__dict__`，可能泄露密码哈希或内部控制字段。 | [`jobs/schemas.py`](apps/api/app/domains/jobs/schemas.py)、[`auth/schemas.py`](apps/api/app/domains/auth/schemas.py) |
| 同步与异步边界 | 当前 SQLAlchemy 使用同步 Session，因此路由保持普通 `def`；真正耗时的批量 Embedding 或评测应进入后台 Worker，而不是在 `async def` 中阻塞。 | 为“看起来现代”把同步 I/O 包进 `async def`，实际仍阻塞事件循环。 | [`db/session.py`](apps/api/app/db/session.py)、[`api/v1/jobs.py`](apps/api/app/api/v1/jobs.py)、[`retrieval/service.py`](apps/api/app/domains/retrieval/service.py) |

### 4.2 SQLAlchemy、PostgreSQL 与事务

- ORM Session 是工作单元，不等于数据库连接本身；
- `commit/rollback/refresh` 的作用；
- 唯一约束、外键、CASCADE 和 RESTRICT 分别解决什么；
- 应用层校验提供友好错误，数据库约束处理并发下的最终一致性；
- 金额使用 `Decimal/Numeric`，避免二进制浮点无法精确表示十进制金额；
- 时间以 UTC 保存，展示时再转换；
- Alembic 迁移负责历史演进，`alembic check` 防止 ORM 与数据库漂移。

#### 项目内示例

| 知识点 | 本项目中的示例与设计理由 | 常见错误 | 代码位置 |
|---|---|---|---|
| 工作单元与事务 | Service 完成一个用例内的写入后统一提交，异常时回滚；Repository 只组装查询与持久化对象，不擅自决定事务结束。 | Repository 每写一条就 commit，后续步骤失败时无法整体回滚。 | [`jobs/service.py`](apps/api/app/domains/jobs/service.py)、[`jobs/repository.py`](apps/api/app/domains/jobs/repository.py) |
| 精确金额 | `salary_min/max` 在 Python 使用 `Decimal`，数据库使用 `Numeric(12,2)`；例如 `0.1 + 0.2` 的金额语义不应依赖二进制浮点近似。 | 使用 `float` 后再 `round`，比较边界、累计计算和跨语言序列化仍可能不一致。 | [`jobs/model.py`](apps/api/app/domains/jobs/model.py)、[`jobs/schemas.py`](apps/api/app/domains/jobs/schemas.py) |
| 应用校验 + 数据库约束 | 创建申请前先检查重复并返回 409，同时数据库以 `(user_id, job_id)` 唯一约束兜住两个并发请求。 | 只做“先查再写”，并发时两个请求都查不到并同时插入。 | [`applications/service.py`](apps/api/app/domains/applications/service.py)、[`applications/model.py`](apps/api/app/domains/applications/model.py) |
| 外键删除策略 | 文档删除时 Chunk/Embedding 使用 CASCADE；职位被申请引用时使用 RESTRICT，避免求职历史被静默删除。删除策略由数据语义决定，而不是统一级联。 | 所有关联都 CASCADE，删除一个职位顺带抹掉审计历史；或全部 RESTRICT，产生大量无法维护的手工清理。 | [`documents/model.py`](apps/api/app/domains/documents/model.py)、[`applications/model.py`](apps/api/app/domains/applications/model.py) |
| UTC 时间 | Model 统一生成带时区 UTC 时间，API/前端展示时再转用户时区，避免服务器部署区域改变业务时间。 | 存无时区的本地时间，夏令时或跨区部署后无法判断真实时刻。 | [`jobs/model.py`](apps/api/app/domains/jobs/model.py)、[`applications/model.py`](apps/api/app/domains/applications/model.py) |
| Schema 演进 | 初始表、知识库、检索、Agent 等变更由独立 Alembic 版本顺序表达，部署时先迁移再启动 API。 | 只改 ORM 或线上手工改表，其他环境无法复现且回滚困难。 | [`migrations/versions`](apps/api/migrations/versions/)、[`infra/docker-compose.yml`](infra/docker-compose.yml) |

### 4.3 RAG 与向量数据库

- Embedding 的维度、归一化、距离函数和模型版本必须与索引一致；
- pgvector HNSW 用更多内存和构建时间换较快近似查询；
- 小规模数据可以精确搜索，规模增长后再根据 Recall/延迟调 HNSW 参数；
- 元数据过滤应在候选生成前完成，不能取回所有用户数据后再在内存过滤；
- 文档结构、Embedding、召回、融合和重排必须通过消融分别比较；
- 合成数据用于跑通管线，模型选型最终需要真实 JD 和真实查询。

#### 项目内示例

| 知识点 | 本项目中的示例与设计理由 | 常见错误 | 代码位置 |
|---|---|---|---|
| Embedding Adapter | 业务层依赖统一 `embed()` 协议；测试用 1024 维确定性哈希向量保证离线、快速、可重复，真实部署可切换 Sentence Transformer。 | 把某个模型 SDK 写死在 Service 中，测试必须联网且换模型要改业务代码。 | [`retrieval/embeddings.py`](apps/api/app/domains/retrieval/embeddings.py) |
| 向量契约 | Embedding 记录模型名，向量维度在适配层统一；更换模型时应重建索引，不能用新查询向量搜索旧模型向量。 | 只改配置里的模型名而保留旧索引，距离值失去可比性且精度无声下降。 | [`ChunkEmbedding`](apps/api/app/domains/documents/model.py)、[`retrieval/embeddings.py`](apps/api/app/domains/retrieval/embeddings.py) |
| 召回前过滤 | 检索 SQL 带 `user_id`，并排除被内容安全扫描标记的文档，保证权限与安全过滤发生在候选生成阶段。 | 先从全库取 Top K 再在内存过滤，既可能串库，也会因过滤后候选不足而降低召回。 | [`retrieval/repository.py`](apps/api/app/domains/retrieval/repository.py)、[`core/content_security.py`](apps/api/app/core/content_security.py) |
| 混合检索 | BM25 捕获 `FastAPI`、`Vue 3` 等精确词，Dense 捕获“后端接口框架”这类改写，RRF 用名次融合，最后仅重排候选集。 | 对全库运行 Cross Encoder，成本和延迟不可控；或直接相加不同尺度的原始分数。 | [`retrieval/ranking.py`](apps/api/app/domains/retrieval/ranking.py)、[`retrieval/service.py`](apps/api/app/domains/retrieval/service.py) |
| 结构感知切分 | 评测同时包含 fixed、title-aware、parent-child 策略，用指标验证是否需要保留标题与父级上下文。 | 凭感觉把 chunk size 定为一个数字，只看单次搜索结果就宣称最佳。 | [`documents/parser.py`](apps/api/app/domains/documents/parser.py)、[`retrieval/evaluation.py`](apps/api/app/domains/retrieval/evaluation.py) |
| 离线评测与门禁 | 实验比较 Recall、MRR、NDCG 与 P95，并用回归脚本阻止指标跌破阈值；失败报告继续查看哪些查询排错。 | 只报告平均 Recall，掩盖第一名质量、长尾查询与延迟退化。 | [`run_retrieval_eval.py`](apps/api/scripts/run_retrieval_eval.py)、[`check_retrieval_regression.py`](apps/api/scripts/check_retrieval_regression.py)、[`week7_failure_analysis.md`](evals/reports/week7_failure_analysis.md) |

### 4.4 Agent 工程化

- Agent 是带状态的受控工作流，不是无限循环调用模型；
- Tool 输入输出需要 Schema，权限和事务仍由业务 Service 控制；
- 只读操作和写操作具有不同风险等级；
- 最大步数、超时、人工确认、Checkpoint、幂等和审计事件共同构成可靠性；
- 生成内容必须携带可验证证据，无证据时应返回不确定而不是补写事实。

#### 项目内示例

| 知识点 | 本项目中的示例与设计理由 | 常见错误 | 代码位置 |
|---|---|---|---|
| LangChain Tool | `job_search`、`match_report`、`skill_gap` 通过 `StructuredTool` 暴露 Schema 化工具，但内部复用现有 Service 和权限边界。 | Tool 直接写 SQL 或信任模型提供的 `user_id`，绕过业务校验和租户隔离。 | [`AgentService._build_read_tools()`](apps/api/app/domains/agent/service.py) |
| LangGraph 状态机 | 图显式维护 intent、action、step、approval 等状态并条件路由，使执行路径可测试、可限制，而不是让模型无限自主循环。 | 把全部流程写进一个超长 Prompt，无法稳定复现中断、恢复和失败分支。 | [`WorkflowState`](apps/api/app/domains/agent/graph.py)、[`test_agent_api.py`](apps/api/tests/test_agent_api.py) |
| Human-in-the-loop | 查询类工具直接执行；`create_application`、`update_application` 在落库前 `interrupt`，页面展示准确参数供用户同意或拒绝。 | 让模型仅凭自然语言自动投递，错误参数会产生真实副作用。 | [`ask_for_approval()`](apps/api/app/domains/agent/graph.py)、[`AgentView.vue`](apps/web/src/views/AgentView.vue) |
| 幂等写入 | 每次确认携带幂等键，`ToolReceipt` 对用户与键建立唯一约束；重试返回先前回执，而不是再次写业务表。 | 只在前端禁用按钮；网络超时、重放或多标签页仍能重复提交。 | [`ToolReceipt`](apps/api/app/domains/agent/model.py)、[`agent/service.py`](apps/api/app/domains/agent/service.py) |
| 可恢复与可审计 | Checkpoint 管图执行位置，数据库 Run/Event 管业务状态与事件顺序，SSE 把事件回放给页面。 | 只保存最终文本，失败后不知道执行过哪个工具、也无法解释写操作是否发生。 | [`agent/graph.py`](apps/api/app/domains/agent/graph.py)、[`agent/model.py`](apps/api/app/domains/agent/model.py)、[`api/v1/agent.py`](apps/api/app/api/v1/agent.py) |
| 证据约束 | 个性化材料的每条内容都带 Citation，保存前验证引用归属与原文包含关系；证据不足时拒绝产物。 | 只让模型在提示词中“不要幻觉”，却不对输出证据做程序校验。 | [`applications/service.py`](apps/api/app/domains/applications/service.py)、[`applications/schemas.py`](apps/api/app/domains/applications/schemas.py) |

### 4.5 安全与可观测性

- 密码只保存带盐的慢哈希，Token 签名密钥与密码哈希是不同概念；
- 认证确认“是谁”，授权确认“能访问什么”；所有用户数据查询仍需用户条件；
- Prompt Injection 来自被检索内容，不能因为文档是用户上传的就信任其中指令；
- 限流保护资源但当前内存实现不能跨实例，生产应使用 Redis；
- 日志应记录 Request ID、路由、状态和耗时，不复制简历、Token 或请求正文；
- liveness 判断进程是否存活，readiness 判断依赖是否允许接流量。

#### 项目内示例

| 知识点 | 本项目中的示例与设计理由 | 常见错误 | 代码位置 |
|---|---|---|---|
| 密码与 Token | 注册时保存 PBKDF2 派生结果，登录后签发带过期时间的 HMAC Token；验证使用恒定时间比较降低时序侧信道。 | 可逆保存密码、使用快速哈希，或把默认签名密钥部署到生产。 | [`auth/security.py`](apps/api/app/domains/auth/security.py)、[`core/config.py`](apps/api/app/core/config.py) |
| 认证与对象授权 | 依赖层从 Bearer Token 得到可信用户；各 Repository 再以 `user_id` 过滤对象，跨用户访问表现为 404。 | 直接采用请求体里的用户 ID，或认证后只按资源 ID 查询。 | [`api/dependencies.py`](apps/api/app/api/dependencies.py)、[`jobs/repository.py`](apps/api/app/domains/jobs/repository.py)、[`documents/repository.py`](apps/api/app/domains/documents/repository.py) |
| 内容安全 | 导入时扫描疑似 Prompt Injection 并标记，检索时过滤；这是一层防御，不应替代模型侧指令隔离和输出校验。 | 把 RAG 文档当成系统指令，检索到什么就执行什么。 | [`core/content_security.py`](apps/api/app/core/content_security.py)、[`retrieval/repository.py`](apps/api/app/domains/retrieval/repository.py) |
| 限流 | 认证接口使用更严格的桶，其他 API 使用普通桶，超限返回 429 与 `Retry-After`；当前内存实现适合单进程演示。 | 所有接口共用同一阈值，或在多实例部署时仍假设内存计数是全局的。 | [`main.py`](apps/api/app/main.py)、[`core/rate_limit.py`](apps/api/app/core/rate_limit.py) |
| 请求关联 | 服务接受合法 `X-Request-ID` 或生成新 ID，将它同时写入响应、错误与结构化日志，便于一次请求跨层排查。 | 只打印异常堆栈，没有请求标识；并发日志无法与用户报错对应。 | [`request_boundary()`](apps/api/app/main.py)、[`core/errors.py`](apps/api/app/core/errors.py) |
| 健康检查 | liveness 不访问外部依赖，readiness 执行数据库探测并在失败时返回 503，容器据此决定是否接流量。 | 健康检查永远返回 200，数据库已断开仍继续接收请求。 | [`liveness()` 与 `readiness()`](apps/api/app/main.py)、[`infra/docker-compose.yml`](infra/docker-compose.yml) |

## 5. 三天实战安排

### 第 1 天：FastAPI、REST、数据库与职位纵切

#### 上午：启动和画图

1. 阅读 README 的环境、迁移和启动部分；
2. 启动 PostgreSQL，执行迁移，运行 FastAPI；
3. 打开 Swagger，手工完成注册、登录和职位 CRUD；
4. 画出 `Request → Router → Service → Repository → Database`；
5. 对每层写一句“负责什么”和一句“不应该做什么”。

#### 下午：读透职位 CRUD

1. 按 Schema → Model → Service → Repository → Migration → Test 阅读；
2. 跟踪薪资从 JSON 字符串进入 Pydantic、转为 Decimal、写入 Numeric、再返回 JSON 的过程；
3. 跟踪一次跨用户读取为什么返回 404；
4. 亲手增加一个简单筛选条件，例如远程类型或职位状态：更新 Schema/Router、Repository、测试；
5. 执行后端测试和 `alembic check`。

#### 第 1 天验收

- 能解释 Schema、ORM、Migration 的区别；
- 能说出 201、204、404、409、422 分别在项目中何时出现；
- 能解释为什么 Service 管事务、数据库仍需要唯一约束；
- 能在 10 分钟内定位一个职位接口的完整调用链；
- 形成一页后端分层笔记。

### 第 2 天：知识库、RAG、匹配与 Agent

#### 上午：亲手比较检索模式

1. 导入一份简历、一份 JD 和一份学习笔记；
2. 查看保存的结构化字段、原文和 Chunk；
3. 建立向量，分别执行 Keyword、Dense、Hybrid、Rerank；
4. 记录相同 Query 下各模式 Top 5 的差异；
5. 用两个简短排名列表手算一次 RRF；
6. 运行 24 组评测、回归门禁并阅读失败样例。

#### 下午：匹配与 Agent

1. 生成一次匹配报告，区分 hard gate、技能分和证据；
2. 检查一条生成简历要点的 Citation 是否真的来自用户简历；
3. 运行一个只读 Agent 请求，观察它自动完成；
4. 运行一个创建申请请求，观察暂停、确认和恢复；
5. 使用同一幂等 Key 重复确认，确认没有产生第二条申请；
6. 画出 Agent 状态变化和数据表之间的关系。

#### 第 2 天验收

- 能解释为什么 Hybrid 通常比单一召回更稳，但不保证一定更好；
- 能解释 Recall、MRR、NDCG 各自关注什么；
- 能根据 48 个排序失败说明下一步实验，而不是只背指标；
- 能解释 Checkpoint、人工确认和幂等的差别；
- 能说明如何阻止模型从 JD 反推用户具备某技能。

### 第 3 天：安全、测试、部署与模拟面试

#### 上午：主动制造失败

1. 篡改一个 Token，确认接口返回 401；
2. 使用用户 B 的 Token 访问用户 A 的资源，确认返回 404；
3. 导入包含“忽略之前指令”的文档，确认能查看但不能索引和检索；
4. 连续调用登录接口触发 429，检查 `Retry-After` 和 Request ID；
5. 使用错误确认短语删除账号，确认数据未变；再用正确密码和短语完成删除；
6. 检查日志不包含密码、Token、邮箱正文或简历原文。

#### 下午：完整回归和面试表达

1. 执行后端测试、Ruff、Alembic drift 检查；
2. 执行前端测试、TypeScript 检查和生产构建；
3. 检查 Docker Compose 配置、health/readiness 和初始化数据；
4. 分别录制或练习 30 秒、2 分钟和 5 分钟项目介绍；
5. 使用第二部分的问题进行至少两轮模拟面试：第一轮只讲结论，第二轮接受连续追问；
6. 将答不出的内容记录为“概念不清、实现不清、数据不清、边界不清”四类并补齐。

#### 第 3 天验收

- 不看代码完成 2 分钟项目介绍；
- 能说出至少 5 个设计取舍、3 个真实问题和 3 个尚未完成的生产能力；
- 能从认证、检索、Agent、事务和部署中各回答一个深挖问题；
- 不把合成集指标说成线上效果，不把当前系统说成完全生产级；
- 能现场演示从登录到申请确认的完整链路。

### 三个推荐的亲手改动

#### 改动 A：增加职位远程类型筛选（后端分层练习，约 45 分钟）

1. 在职位列表 Router 增加可选 Query 参数并使用现有枚举校验；
2. 将条件传入 Service/Repository，不在 Router 里过滤结果；
3. 在数据库查询中与用户条件、分页条件一起应用；
4. 增加“命中、无结果、非法枚举、跨用户”API 测试；
5. 验收：Swagger 可选择筛选值，total 与 items 一致，完整后端测试通过。

#### 改动 B：增加一条 Prompt Injection 规则（安全与测试练习，约 30 分钟）

1. 先写一个当前会漏报的中英文攻击样例测试；
2. 增加最小规则并避免匹配正常求职文本；
3. 导入命中文档，检查风险标记；
4. 尝试索引和检索，确认候选仍为零；
5. 验收：恶意样例被隔离，至少一个相似但正常的反例不被隔离。

#### 改动 C：增加只读“申请状态查询”Agent Tool（Agent 边界练习，约 60–90 分钟）

1. 增加明确意图和所需参数；
2. 让 Tool 复用申请业务服务，不直接查询数据库；
3. 将它标记为只读，不进入人工确认；
4. 返回稳定结构化结果并记录摘要事件；
5. 增加“正常查询、资源不存在、跨用户、缺少参数”测试；
6. 验收：只读请求自动完成，事件中没有私人正文，也不会产生新的申请或状态事件。

## 6. 必须亲手执行的命令

### 后端与数据库

```powershell
docker compose -f infra\docker-compose.yml up -d postgres
Set-Location apps\api
..\..\.venv\Scripts\python.exe -m alembic upgrade head
..\..\.venv\Scripts\python.exe -m alembic current
..\..\.venv\Scripts\python.exe -m alembic check
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### 后端质量检查

```powershell
Set-Location apps\api
..\..\.venv\Scripts\python.exe -m pytest
..\..\.venv\Scripts\python.exe -m ruff check app tests scripts migrations
```

### RAG 评测

```powershell
Set-Location D:\AI\Agent
.\.venv\Scripts\python.exe apps\api\scripts\run_retrieval_eval.py
.\.venv\Scripts\python.exe apps\api\scripts\analyze_retrieval_failures.py
.\.venv\Scripts\python.exe apps\api\scripts\check_retrieval_regression.py
```

### 前端最低掌握要求

```powershell
Set-Location apps\web
npm run test
npm run typecheck
npm run build
```

## 7. 面试前自测清单

使用方法：先遮住“示例回答”，在 90 秒内按“结论 → 设计 → 证据 → 边界”回答，再打开答案对照。不要背句子，要能沿着代码位置现场展开。

### 7.1 项目解决什么问题，为什么需要 Agent？

**示例回答：** 这个项目面向寻找 AI 应用开发实习的学生，把分散的职位管理、私人简历知识库、岗位匹配、材料生成和投递状态跟踪串成一条工作流。普通职位管理系统主要做 CRUD，而 Agent 的价值是把“查找职位 → 分析匹配 → 找技能差距 → 生成材料 → 经用户确认后创建申请”编排起来，并保留状态、证据和事件。它不是让大模型无限自主操作：只读工具可自动执行，写操作必须确认，所有权限和事务仍由后端 Service 控制。

**对应代码：** [`agent/graph.py`](apps/api/app/domains/agent/graph.py)、[`agent/service.py`](apps/api/app/domains/agent/service.py)、[`matching/service.py`](apps/api/app/domains/matching/service.py)、[`applications/service.py`](apps/api/app/domains/applications/service.py)

### 7.2 一次 API 请求如何经过各层？

**示例回答：** 以创建职位为例，请求先经过应用中间件，获得 Request ID 并接受限流；Router 用 `JobCreate` 校验输入，通过依赖拿到当前用户和 `JobService`。Service 执行业务用例并控制事务，Repository 将 `user_id` 与查询/写入条件组合，SQLAlchemy Session 把 ORM 变化提交到数据库。成功后 `JobRead` 过滤并序列化输出；业务异常由统一处理器转成稳定错误结构。分层的关键不是文件多，而是让 HTTP、业务规则、数据访问和持久化各自可替换、可测试。

**对应代码：** [`main.py`](apps/api/app/main.py)、[`api/v1/jobs.py`](apps/api/app/api/v1/jobs.py)、[`jobs/service.py`](apps/api/app/domains/jobs/service.py)、[`jobs/repository.py`](apps/api/app/domains/jobs/repository.py)、[`jobs/model.py`](apps/api/app/domains/jobs/model.py)

### 7.3 Pydantic、SQLAlchemy、Alembic 分别解决什么？

**示例回答：** Pydantic 是 API 边界合同，负责请求与响应的类型、枚举、范围和跨字段校验；SQLAlchemy Model 把 Python 对象映射到表、列、外键、索引和约束；Alembic 则记录数据库结构从旧版本到新版本的可执行历史。只改 Pydantic 不会改变数据库，只改 ORM 也不会自动安全更新已有数据库。一次新增字段通常需要同时考虑输入输出 Schema、ORM 映射、Migration 和测试。

**对应代码：** [`jobs/schemas.py`](apps/api/app/domains/jobs/schemas.py)、[`jobs/model.py`](apps/api/app/domains/jobs/model.py)、[`20260729_0001_create_jobs.py`](apps/api/migrations/versions/20260729_0001_create_jobs.py)、[`migrations/env.py`](apps/api/migrations/env.py)

### 7.4 为什么薪资不用 float，状态不能任意传字符串？

**示例回答：** 金额是十进制定点数据，很多十进制小数无法被二进制浮点精确表示，因此项目用 Python `Decimal` 和数据库 `Numeric(12,2)`，保证比较、存储和返回的一致性。申请状态则使用枚举和允许迁移表，因为“保存、已投递、面试、录用、拒绝”不是任意字符串：状态变化会影响时间字段与历史事件，非法跳转应返回 409。类型约束解决格式问题，状态机解决业务时序问题。

**对应代码：** [`jobs/model.py`](apps/api/app/domains/jobs/model.py)、[`jobs/schemas.py`](apps/api/app/domains/jobs/schemas.py)、[`ApplicationStatus`](apps/api/app/domains/applications/model.py)、[`ALLOWED_TRANSITIONS`](apps/api/app/domains/applications/service.py)

### 7.5 为什么知识库保存结构化字段、原文和 Chunk？

**示例回答：** 三种表示服务的查询模式不同。结构化字段适合按技能、城市、经历等做确定性筛选和统计；规范化原文用于展示、审计和解析器升级后的重跑；Chunk 则用于 BM25 和向量检索。项目还保存内容哈希做用户范围内去重，Chunk 保留章节路径和标题上下文，Embedding 单独记录模型版本。这样能复现实验，也能换模型重建向量，而不用丢失原始证据。

**对应代码：** [`documents/model.py`](apps/api/app/domains/documents/model.py)、[`parse_document()` 与 `build_chunks()`](apps/api/app/domains/documents/parser.py)、[`documents/service.py`](apps/api/app/domains/documents/service.py)

### 7.6 Keyword、Dense、RRF、Rerank 的职责与成本是什么？

**示例回答：** Keyword/BM25 对技能名、城市、版本号等精确词稳定且便宜；Dense 把 Query 与 Chunk 编码到同一向量空间，能找语义改写，但增加模型推理和向量索引成本。Hybrid 用 RRF 按排名融合两路候选，避免直接相加不同尺度的 BM25 与余弦分数。Reranker 联合读取 Query 与候选文本，通常头部排序更细，但逐对计算更贵，因此只处理 `candidate_k`，最后返回较小的 `top_k`。

**对应代码：** [`bm25_rank()`、`reciprocal_rank_fusion()` 与 Reranker](apps/api/app/domains/retrieval/ranking.py)、[`retrieval/service.py`](apps/api/app/domains/retrieval/service.py)、[`retrieval/repository.py`](apps/api/app/domains/retrieval/repository.py)

### 7.7 如何解读当前 Recall、MRR 和 NDCG？

**示例回答：** 当前门禁配置在 30 篇匿名合成文档、120 条查询上得到 Recall@5 1.0000、MRR@10 0.7336、NDCG@10 0.8005，P95 约 18 ms。Recall 为 1 只表示相关文档都进入前五，不表示第一名正确；MRR 说明首个相关结果平均仍不够靠前，NDCG 说明分级相关结果的整体顺序仍有优化空间。失败分析找到 48 个“进了 Top 5 但没排第一”的样例，所以优先补困难负例和真实 Reranker 实验，而不是继续扩大召回窗口。最重要的边界是：Hash Embedding 与合成集只证明评测和回归流程，不代表线上准确率。

**对应代码/报告：** [`retrieval/evaluation.py`](apps/api/app/domains/retrieval/evaluation.py)、[`check_retrieval_regression.py`](apps/api/scripts/check_retrieval_regression.py)、[`week3_week4_baseline.json`](evals/reports/week3_week4_baseline.json)、[`week7_failure_analysis.md`](evals/reports/week7_failure_analysis.md)

### 7.8 为什么真实 Embedding 模型不能只看排行榜？

**示例回答：** 公共榜单的数据分布、语言、文本长度和硬件环境不一定等于中文实习 JD 与个人简历。我的选择方法是固定同一批真实 Query/qrels、Chunk 策略、Top K 与过滤条件，对 BGE-M3、Qwen3-Embedding 等模型比较 Recall、MRR、NDCG、P95、索引时间、向量体积、吞吐和部署费用。先设最低质量门槛，再在达标模型里选总成本最低的。换模型必须保存精确版本并重建索引，因为不同模型的向量空间不能混用。目前项目已提供 Adapter 和实验框架，但尚未把 Hash 结果包装成真实模型结论。

**对应代码：** [`EmbeddingAdapter`](apps/api/app/domains/retrieval/embeddings.py)、[`run_retrieval_eval.py`](apps/api/scripts/run_retrieval_eval.py)、[`retrieval_gold.jsonl`](datasets/retrieval_gold.jsonl)、[`ChunkEmbedding`](apps/api/app/domains/documents/model.py)

### 7.9 LangChain 和 LangGraph 分别承担什么？

**示例回答：** LangChain 在这里主要用于 `StructuredTool`：为职位搜索、匹配报告和技能差距等能力定义结构化输入，并把它们适配成 Agent 可调用工具。LangGraph 负责有状态的工作流编排，包括意图路由、动作规划、条件分支、中断确认和恢复。业务 Service 才真正执行查询与写入，因此框架负责“怎么编排”，领域层负责“操作是否合法、事务如何完成”。这种边界让工具也能被普通 REST API 与测试复用。

**对应代码：** [`AgentService._build_read_tools()`](apps/api/app/domains/agent/service.py)、[`agent/graph.py`](apps/api/app/domains/agent/graph.py)、[`matching/service.py`](apps/api/app/domains/matching/service.py)、[`applications/service.py`](apps/api/app/domains/applications/service.py)

### 7.10 Checkpoint、人工确认、幂等分别解决什么故障？

**示例回答：** Checkpoint 保存图执行到哪里，解决暂停或进程中断后的恢复问题；人工确认在写操作前让用户检查工具与参数，解决模型理解错误造成副作用的问题；幂等通过唯一键和工具回执让重试只产生一次写入，解决超时重试、重复点击和消息重放。三者覆盖不同故障，不能互相替代。当前图使用 `InMemorySaver`，适合本地演示但重启会丢，生产应换 PostgreSQL/Redis 等持久 Checkpointer；业务 Run、Event 和 Tool Receipt 已单独持久化。

**对应代码：** [`CHECKPOINTER` 与 `interrupt`](apps/api/app/domains/agent/graph.py)、[`AgentRun`、`AgentEvent`、`ToolReceipt`](apps/api/app/domains/agent/model.py)、[`confirm_run()`](apps/api/app/domains/agent/service.py)、[`test_agent_api.py`](apps/api/tests/test_agent_api.py)

### 7.11 如何证明生成的简历内容没有编造？

**示例回答：** 项目不只在 Prompt 里要求“不要幻觉”，而是让每个生成条目携带结构化 Citation。保存前程序检查用户、简历和职位归属；个人能力引用必须指向当前用户真实 Chunk，且引文确实出现在 Chunk 中；岗位需求引用必须来自当前 JD。空引用、跨用户引用、虚构原文都会返回 422，验证通过的 Citation 与产物一起持久化。这个机制能证明“这句话依据哪段资料”，但不能证明原始简历本身绝对真实，因此仍需要用户审阅。

**对应代码：** [`Citation` 与 `ArtifactItem`](apps/api/app/domains/applications/schemas.py)、[`_validate_citations()`](apps/api/app/domains/applications/service.py)、[`GeneratedArtifact`](apps/api/app/domains/applications/model.py)、[`test_applications_api.py`](apps/api/tests/test_applications_api.py)

### 7.12 如何防止用户数据串库和 Prompt Injection？

**示例回答：** 用户隔离采用纵深防御：Token 只提供可信用户身份，Repository 的每个读取和列表 SQL 都带 `user_id`，跨用户对象统一按不存在处理，避免泄露 ID 是否存在；相关唯一约束也包含用户维度。Prompt Injection 方面，上传内容始终视为不可信数据，导入时扫描可疑指令并标记，检索候选阶段排除被标记文档，生成结果还要经过 Citation 校验。扫描不是万能防线，生产中还应增加模型指令隔离、输出 Schema、权限最小化与对抗评测。

**对应代码：** [`api/dependencies.py`](apps/api/app/api/dependencies.py)、[`documents/repository.py`](apps/api/app/domains/documents/repository.py)、[`core/content_security.py`](apps/api/app/core/content_security.py)、[`retrieval/repository.py`](apps/api/app/domains/retrieval/repository.py)、[`test_week7_security.py`](apps/api/tests/test_week7_security.py)

### 7.13 事务、约束、外键与应用校验如何配合？

**示例回答：** 应用层校验用于尽早返回人能理解的错误，例如薪资下限不能大于上限、状态迁移是否合法、申请是否重复；但“先查再写”存在并发窗口，所以数据库唯一约束负责最终一致性。外键保证引用对象存在，并按业务选择 CASCADE 或 RESTRICT。Service 把一个用例内的多次写入放在同一事务，捕获 `IntegrityError` 后先 rollback，再转换为稳定的 409 等业务错误。例如创建申请同时写当前状态与首条事件，要么一起成功，要么都不落库。

**对应代码：** [`jobs/service.py`](apps/api/app/domains/jobs/service.py)、[`applications/service.py`](apps/api/app/domains/applications/service.py)、[`applications/model.py`](apps/api/app/domains/applications/model.py)、[`documents/model.py`](apps/api/app/domains/documents/model.py)

### 7.14 健康检查、结构化日志和 Request ID 有什么作用？

**示例回答：** liveness 判断进程是否还活着，失败通常触发重启；readiness 还检查数据库，失败时返回 503，让流量入口暂时摘除实例。请求中间件接受合法的 `X-Request-ID` 或生成新 ID，并把它写回响应、错误和 JSON 日志；日志同时记录路由、状态码和耗时，便于从用户报错定位到服务端请求及慢点。日志刻意不记录 Token、简历正文和请求体，避免可观测性系统成为敏感数据副本。

**对应代码：** [`request_boundary()`、`liveness()` 与 `readiness()`](apps/api/app/main.py)、[`core/observability.py`](apps/api/app/core/observability.py)、[`core/errors.py`](apps/api/app/core/errors.py)、[`infra/docker-compose.yml`](infra/docker-compose.yml)

### 7.15 为什么当前系统不能直接宣称生产级？流量扩大十倍先改什么？

**示例回答：** 当前系统已经有迁移、鉴权、事务、测试、限流、健康检查和审计等工程基础，但仍是作品级实现：Agent Checkpointer 和限流器在单进程内存中，前端 Token 放 Session Storage，耗时 Embedding/评测是同步路径，检索结论来自小型合成集和 Hash Adapter，多实例事件流与完整部署压测也未验证。十倍流量下我先通过日志和指标确认瓶颈，再把 Checkpointer/限流/事件流迁到共享存储，将解析与 Embedding 放到队列 Worker，批处理和缓存向量请求，基于真实数据调 pgvector 索引，并补连接池、负载测试、告警与灾备。顺序由实际 P95、错误率、队列积压和数据库负载决定，而不是先盲目拆微服务。

**对应代码/说明：** [`agent/graph.py`](apps/api/app/domains/agent/graph.py)、[`core/rate_limit.py`](apps/api/app/core/rate_limit.py)、[`auth-storage.ts`](apps/web/src/auth-storage.ts)、[`retrieval/service.py`](apps/api/app/domains/retrieval/service.py)、[`week7_failure_analysis.md`](evals/reports/week7_failure_analysis.md)

### 7.16 你本人完成了什么，最困难的问题是什么，如何证明？

**示例回答：** 这是我的个人项目，我从需求拆分、数据建模、FastAPI 分层、私人知识库、混合检索、匹配与材料证据约束，一直实现到 LangGraph 确认/恢复/幂等、Vue 联调和 Docker Compose。最困难的不是接入某个模型，而是让检索与 Agent 的质量可验证：我建立了 30 篇匿名合成文档、120 条查询的可复现实验，比较 24 组配置，并增加指标回归门禁与失败样本分析。当前门禁配置 Recall@5 为 1.0000，但 48 个头部排序错误让我没有宣称检索“已经优化完成”；工程侧有 48 个后端测试覆盖 CRUD、隔离、事务、Token、注入、限流和 Agent 重试。若面试官继续追问，我会主动说明 Hash Adapter、合成数据和内存组件的边界，再展示下一轮真实模型/真实 JD 实验计划。

**对应代码/证据：** [`README.md 的第七周交付`](README.md#第七周交付)、[`apps/api/tests`](apps/api/tests/)、[`week3_week4_baseline.json`](evals/reports/week3_week4_baseline.json)、[`week7_failure_analysis.md`](evals/reports/week7_failure_analysis.md)、[`check_retrieval_regression.py`](apps/api/scripts/check_retrieval_regression.py)

## 8. 三天后应该留下的学习成果

1. 一张后端分层与核心数据流架构图；
2. 一张 RAG 检索链路和指标解释图；
3. 一张 Agent 状态、确认、恢复、幂等关系图；
4. 一份亲手修改过且测试通过的小功能；
5. 一份 Keyword/Dense/Hybrid/Rerank 对比记录；
6. 一份至少包含 20 个问题的模拟面试录音或文字复盘；
7. 一版按目标岗位裁剪、每个数字都能解释来源的简历项目描述。

# 第二部分：简历项目说明与模拟面试

## 1. 简历可直接使用版本（推荐）

### CareerPilot｜可恢复、可评测的求职 Agent（个人项目）

**项目角色：** AI 应用开发 / Python 后端开发　　**时间：** `[20XX.XX–20XX.XX]`  
**技术栈：** Python、FastAPI、SQLAlchemy、PostgreSQL/pgvector、LangChain、LangGraph、Vue 3、TypeScript、Docker Compose

- 独立设计并实现面向 AI 应用开发实习求职场景的全栈 Agent，使用 FastAPI、SQLAlchemy 与 PostgreSQL 搭建分层 RESTful API，完成职位管理、私人知识库、岗位匹配、材料生成和申请跟踪，并使用 Vue + TypeScript 实现可视化操作界面。
- 围绕简历与 JD 检索设计“结构化字段 + 规范化原文 + 标题感知 Chunk”的 RAG 数据链路，结合全文检索、向量召回、RRF 融合与候选重排兼顾精确术语和语义改写，并建立覆盖召回质量、排序效果和响应延迟的离线评测及回归门禁。
- 使用 LangChain 封装职位检索、匹配分析和技能差距等结构化工具，基于 LangGraph 编排意图路由、任务计划和恢复流程；区分只读与写操作风险，为申请创建和状态更新增加人工确认、运行事件与幂等保护。
- 完成 Token 身份认证、密码安全存储、用户级数据隔离、Prompt Injection 文档过滤、请求限流和健康检查，并使用 Docker Compose 串联数据库迁移、API 与前端服务，形成可复现的工程交付流程。

## 2. 不同岗位的定向精简版本

### AI 应用开发实习

- 使用 LangChain 将职位检索、匹配报告和技能差距分析封装为结构化 Tool，基于 LangGraph 编排意图路由、任务计划、中断确认和恢复流程，并通过幂等回执与审计事件约束写操作副作用。
- 构建全文检索、向量召回、RRF 融合与候选重排组成的混合检索链路，通过消融实验比较 Embedding、切分策略和检索模式，建立覆盖召回、排序与延迟的自动回归门禁和失败样例分析。
- 对私人知识库执行 Prompt Injection 扫描和检索隔离，生成材料必须携带可验证 Citation，使个人能力描述能够回溯至用户原始资料，降低恶意上下文和无证据生成风险。

### Python 后端实习

- 使用 FastAPI、Pydantic、SQLAlchemy、Alembic 与 PostgreSQL 设计前后端分离的求职管理服务，按 Router、Service、Repository 划分 HTTP 合同、业务逻辑和数据访问，完成职位、知识库、申请状态机及 Agent 运行记录等 RESTful API。
- 通过应用层校验、事务、唯一约束和外键共同处理非法状态迁移、并发重复提交与关联删除，实现 Bearer Token、密码安全存储、用户级查询隔离、账号数据原子删除和差异化限流。
- 统一输出业务错误码与 Request ID，记录脱敏结构化日志，并使用 Docker Compose 编排 API、前端服务和向量数据库，结合自动迁移、幂等初始化及存活/就绪探针完成可复现部署。

### AI 全栈实习

- 使用 Vue Composition API、TypeScript、Vue Router、Axios 与 Element Plus 开发求职 Agent 工作台，实现职位管理、私人知识库、检索实验室、Agent 写操作确认和申请看板，并通过领域 API 封装与后端 OpenAPI 合同对齐。
- 后端基于 FastAPI、PostgreSQL/pgvector、LangChain 与 LangGraph，打通“导入简历 → 结构化解析与切分 → 混合检索 → 可解释匹配 → Agent 确认 → 申请时间线”的完整业务链路。
- 前端统一处理身份凭证注入、未授权跳转、加载与异常状态，通过后端自动测试、Vue 组件测试、TypeScript 类型检查和生产构建验证核心交互与交付质量。

> 简历中不写入合成数据规模、实验组数或离线指标数值；面试追问时再结合评测报告说明实验设计、结果和数据边界。

## 3. 面试口述版本

### 30 秒版本

我做了一个面向 AI 应用开发实习求职的全栈 Agent。它不只是套 LangChain，而是把简历和 JD 做结构化、标题感知切分，再用关键词、向量、RRF 和重排检索，并用 120 条 qrels 做回归。Agent 用 LangGraph 显式状态机实现，写申请前必须人工确认，重试有幂等保护。第 7 周又补了真实鉴权、用户隔离、提示词注入隔离、限流、可观测日志和 Docker 一键启动，所以它能展示从 AI 效果到后端工程化的完整能力。

### 2 分钟版本

这个项目解决的是求职信息分散、职位判断缺乏证据、Agent 写操作不安全三个问题。数据层没有只存向量，而是同时保存可筛选的结构化字段、用于追溯的规范化原文和用于语义检索的 Chunk。检索链路先做关键词与向量召回，再用 RRF 融合和轻量 Rerank；我建立了 30 篇匿名合成文档、120 条 qrels，跑 24 组消融，并把 Recall、MRR、NDCG 和 P95 延迟做成自动门禁。当前失败主要是相关结果没有排第一，而不是 Top 5 漏召回，所以后续重点是困难负例和真实 Cross-Encoder，而不是盲目增大 Top K。

Agent 层使用 LangGraph 显式区分路由、计划、等待确认和结束状态。搜索、匹配等只读 Tool 可以自动运行，创建或更新申请会中断等待用户确认；数据库保存 Run、事件和 Pending Action，幂等回执与业务唯一约束防止网络重试产生重复申请。安全方面，服务端验证 Bearer Token，所有 Repository 查询按用户过滤；疑似 Prompt Injection 的文档仍可审查，但默认不建向量也不进入 RAG；账号删除会在一个事务中清理职位、文档、向量、申请、产物和 Agent 记录。最后用 Docker Compose 串起数据库健康检查、迁移、初始化数据、API readiness 和 Vue/Nginx，使别人可以复现运行。

## 4. 基于简历的模拟面试问答

### 4.1 回答方法

面试官通常只看过简历，不知道仓库内部结构。回答时按以下顺序组织：

1. 先说要解决的业务或工程问题；
2. 再说采用了什么设计，以及为什么没有选择更简单的方案；
3. 给出可验证的结果，例如测试、指标或失败样例；
4. 最后主动说明局限和下一步，避免把入门项目包装成线上生产系统。

不要用“代码里有一个类/函数”作为主要回答。可以谈 Router、Service、Repository、状态机、事务等通用设计，但要先让面试官理解它们解决了什么问题。

### 4.2 项目概览与个人贡献

#### Q1：请先介绍一下这个项目。

**参考回答：** 这是一个面向 AI 应用开发实习求职的全栈 Agent。用户可以保存职位和私人简历资料，系统会把资料结构化并建立可检索知识库，然后结合关键词、向量和重排生成带证据的岗位匹配报告。Agent 可以继续帮助用户创建或更新申请记录，但所有写操作都必须经过人工确认。项目的重点不是做一个聊天页面，而是把 RAG 效果评测、Agent 副作用控制、用户数据安全和后端工程化放在同一条业务链路中。

#### Q2：这个项目具体解决了哪些问题？

**参考回答：** 我把问题分成三类。第一，职位、简历和学习资料分散，用户难以统一检索和管理；第二，普通大模型给出的“匹配”容易缺少证据，甚至把岗位要求误当成用户能力；第三，Agent 如果直接写入申请或修改状态，会有误操作和重复执行风险。因此系统同时提供结构化管理、带引用的检索与匹配，以及可暂停、可确认、可恢复的 Agent 工作流。

#### Q3：你在项目中的主要工作是什么？

**参考回答：** 这是个人项目，我完成了从架构、数据模型、REST API、RAG 评测到 Agent 和安全交付的完整设计与实现。后端是主要投入，包括 FastAPI 分层、数据库事务与迁移、混合检索、评测门禁、LangGraph 状态机、鉴权和数据隔离；前端完成了能够演示业务闭环的 Vue 页面。我也保留了测试、失败样例和未完成能力，确保简历上的每个指标都能说明数据来源和验证方式。

#### Q4：这个项目最核心的一条用户链路是什么？

**参考回答：** 用户登录后导入简历和目标岗位，系统保存结构化字段、原文和语义片段；随后建立向量并执行混合检索，生成硬条件、技能差距和证据引用组成的匹配报告。用户如果决定准备申请，可以让 Agent 生成申请操作，Agent 会在写数据库前暂停并展示参数，用户确认后才写入申请状态和时间线。整个过程都在用户数据范围内运行，并能通过事件记录追踪。

#### Q5：为什么采用前后端分离和分层后端？

**参考回答：** 前后端分离让 Vue 只依赖稳定的 HTTP 合同，后端可以独立测试和演进。后端分层是为了把 HTTP 语义、业务规则、数据访问和 AI 工作流分开：接口层负责参数和状态码，业务层负责事务和规则，数据层负责查询与隔离，Agent 只能复用受控业务能力。这样可以避免权限、事务和 Prompt 混在路由里，也便于单独测试每个边界。

#### Q6：你认为这个项目最难的部分是什么？

**参考回答：** 最难的不是接入某个模型，而是让“效果”和“工程可靠性”同时可验证。检索上需要区分召回和排序问题，不能凭几个问题主观判断；Agent 上需要处理暂停、恢复和重复确认；数据上要保证任何查询都不会串用户；生成内容还必须证明来源。因此我把评测集、失败样例、事务约束、幂等和引用校验都作为一等能力，而不是最后补几个演示页面。

### 4.3 FastAPI、REST 与数据库

#### Q7：为什么选择 FastAPI，而不是 Flask 或 Django？

**参考回答：** 这个项目有较多结构化输入输出、枚举、跨字段约束和 AI Tool Schema，FastAPI 与 Pydantic 的结合可以让校验、类型提示和 OpenAPI 合同保持一致，开发反馈比较快。相比 Flask，它减少了手工维护校验和文档的工作；相比 Django，它更适合当前这种 API 优先、领域相对清晰的轻量服务。不过选择 FastAPI 不等于所有接口都应该异步，数据库和本地模型调用仍要根据底层是否真正支持异步来设计。

#### Q8：Pydantic、SQLAlchemy 和 Alembic 分别负责什么？

**参考回答：** Pydantic 是系统边界的数据合同，负责请求校验、响应序列化和避免返回内部字段；SQLAlchemy 描述运行时如何把领域数据映射到数据库表，并提供查询和事务操作；Alembic 保存数据库结构从一个版本演进到下一个版本的历史。只修改 ORM 不会自动安全地修改已有数据库，所以任何字段或约束变化都必须有迁移，并通过漂移检查确认模型与真实数据库一致。

#### Q9：你如何设计 RESTful API？

**参考回答：** 我把职位、文档、申请和 Agent Run 视为资源，使用复数名词和统一版本前缀。GET 读取，POST 创建或触发明确操作，PATCH 做部分更新，DELETE 删除；创建返回 201，无响应体删除返回 204，资源不存在返回 404，业务冲突返回 409，参数问题返回 422，限流返回 429。错误响应包含稳定错误码、可读消息和 Request ID，便于前端处理和日志关联，而不是所有失败都返回 200。

#### Q10：为什么 Router、Service、Repository 要分开？

**参考回答：** 这三层的变化原因不同。HTTP 状态码或认证方式变化不应影响业务规则；申请状态机和事务变化不应迫使我重写路由；数据库查询或索引变化也不应改变业务用例。分开后，Service 成为业务规则和事务边界，Repository 强制数据访问范围，Router 保持轻量。代价是文件和抽象更多，所以我只在有真实业务边界的地方分层，没有为每个简单函数都创建接口。

#### Q11：项目如何处理事务和并发一致性？

**参考回答：** 业务层把一个完整用例放在同一事务中，例如创建申请时同时写当前状态和时间线事件，账号删除时一次清理所有用户数据；异常则整体回滚。应用层会提前检查并返回友好错误，但并发请求可能同时通过检查，所以数据库还使用唯一约束、外键和必要的行锁作为最终保护。我的原则是应用校验改善体验，数据库约束保证事实。

#### Q12：为什么薪资使用 Decimal/Numeric，而不是 float？

**参考回答：** 二进制浮点不能精确表示很多十进制小数，金额比较、范围校验和数据库往返可能出现不可见误差。薪资属于需要精确比较的数据，所以接口和业务层使用十进制定点数，数据库使用 Numeric，并限制小数位。即使当前实习日薪大多是整数，也不应该因为样例简单就建立错误的数据类型基础。

#### Q13：为什么申请状态需要状态机？

**参考回答：** 如果允许前端提交任意状态，就会产生不可能的历史，例如已经拒绝后直接回到收藏。系统定义允许的状态转换，当前状态用于高效查询看板，事件时间线用于审计每次变化，两者在同一事务更新。前端可以只显示合法选项，但最终规则必须在后端，因为调用者可以绕过页面直接请求 API。

#### Q14：为什么职位存在申请历史后不允许直接删除？

**参考回答：** 职位是来源数据，申请和面试时间线是用户行为历史。如果级联删除职位，会悄悄破坏用户的求职记录。因此已有申请时系统返回业务冲突，数据库外键也使用限制删除作为并发下的最终保护。更成熟的方案可以对职位做软删除并保存职位快照，但不能用清理职位库的动作删除用户历史。

#### Q15：分页和筛选为什么应该在数据库完成？

**参考回答：** 如果先读取全部数据再在应用内筛选，会浪费内存和网络，也可能先读取到不属于当前用户的数据。系统把用户范围、状态、城市、关键词和分页条件下推数据库，只返回当前页面。随着数据增大，还需要根据查询计划增加复合索引，并避免无界 page size。

### 4.4 用户身份、权限与删除

#### Q16：系统如何保证用户数据不会串库？

**参考回答：** 生产模式只接受服务端可验证的登录凭证，验证签名、过期时间和 Token 版本后得到可信用户身份。之后每个数据访问入口仍显式带用户条件，认证回答“是谁”，数据层过滤回答“能访问哪一条”。跨用户访问返回 404，既阻止访问，也避免泄露资源是否存在。测试会使用两个真实身份创建和访问资源，而不是只检查前端有没有隐藏按钮。

#### Q17：为什么不能让前端直接传 user_id？

**参考回答：** 浏览器中的 Header、JavaScript 和请求参数都可以被用户修改。如果后端相信前端提供的 user_id，攻击者只需要替换一个字符串就可能读取其他人的简历。开发环境可以保留显式演示身份方便练习，但生产启动时必须关闭，并从签名凭证中取得身份。

#### Q18：账号全量删除是怎么保证一致性的？

**参考回答：** 删除前要求重新验证密码和输入精确确认短语，减少误操作。真正删除时按外键依赖顺序，在一个数据库事务中清理职位、文档、Chunk、向量、申请、生成产物和 Agent 记录；任何一步失败都会回滚。不能让前端依次调用多个删除接口，因为中途断网会留下半删除状态。

#### Q19：密码和 Token 是如何处理的？

**参考回答：** 密码不会加密后保存，而是使用随机盐和计算成本较高的单向哈希保存，登录时对输入执行同样计算后做恒定时间比较。Token 使用服务端密钥签名，并包含用户、过期时间和版本；签名防篡改，过期时间限制泄露窗口，版本可以支持让旧 Token 整体失效。当前实现是短期 Access Token，完整生产系统还需要刷新、撤销、密钥轮换和安全 Cookie。

### 4.5 私人知识库与数据建模

#### Q20：为什么同一份简历或 JD 要保存三种表示？

**参考回答：** 三种表示解决不同问题。结构化字段用于城市、时间、技能和状态等精确过滤；原文用于展示、审计、引用和以后更换解析器重新处理；Chunk 用于关键词和语义检索。只存向量无法可靠做金额和城市过滤，也无法解释结果；只存结构化字段会丢失大量描述语义；只存原文则每次查询都要重新解析。

#### Q21：文档需要结构化到什么程度？

**参考回答：** 我只结构化会参与过滤、排序、去重、权限或统计的稳定字段，例如职位、公司、城市、远程类型、实习时长、薪资、技能和来源信息。公司介绍、软技能描述和一次性生成内容保留为文本。过度结构化会增加解析错误和迁移成本，所以判断标准不是“能不能抽出来”，而是“业务是否会稳定使用它”。

#### Q22：你的 Chunk 策略是什么，为什么不固定长度切分？

**参考回答：** 简历按教育、项目、实习和技能切分，JD 按职责、要求和加分项切分，并保留章节路径。子片段会补充文档标题和父章节，使它脱离全文后仍知道属于哪个职位或项目。固定长度实现简单，但可能把一个要求截断或把多个主题混在一个向量中；结构化切分更符合用户查询的证据粒度。仍需通过评测选择长度，不能只凭直觉认为结构切分一定更好。

#### Q23：如何处理重复文档和重新索引？

**参考回答：** 规范化文本后计算内容哈希，在同一用户范围内去重，避免相同内容重复生成 Chunk 和向量。文档保存解析版本、索引版本和 Embedding 模型版本；解析策略变化时可以基于原文重新生成，而不是覆盖后失去来源。更新索引时旧 Chunk 和相关向量需要一致替换，不能留下多个版本混用。

### 4.6 RAG 检索设计

#### Q24：为什么不只用向量检索？

**参考回答：** 求职场景同时包含精确实体和语义表达。技能名、城市、框架版本更适合关键词检索，而“做过类似智能问答项目”这类改写更适合 Dense Embedding。单一向量检索可能把语义相近但硬条件错误的职位排前，所以系统先做结构化过滤，再并行执行关键词和向量召回，然后融合和重排。

#### Q25：为什么用 RRF，而不是直接把两个分数相加？

**参考回答：** BM25 分数和余弦相似度的尺度、分布都不同，直接相加需要针对模型和数据调权重，模型一换可能失效。RRF 只依赖候选在各自列表中的排名，对尺度不敏感，也让同时被两路召回的结果自然获益。它不是理论上永远最好，但适合作为稳定、可解释、容易复现的融合基线，后续可以再和学习排序比较。

#### Q26：Reranker 的作用是什么？为什么不直接对所有文档重排？

**参考回答：** Embedding 适合大范围快速召回，但一个向量压缩全文后可能丢失细节。Cross-Encoder 可以同时阅读 Query 和候选文本，通常排序更准，但计算成本高。因此只对几十个融合候选重排，再返回 Top K。对全部文档重排会让延迟和费用随文档规模线性增长，失去两阶段检索的意义。

#### Q27：不同 Embedding 模型对精度影响有多大？你如何选择？

**参考回答：** 影响取决于领域、语言、Query 指令、Chunk 和相似度方法，没有一个固定百分比。中文技能、英文框架名和长 JD 的混合场景，模型的中英能力和指令遵循都会影响排序。我先用低成本确定性基线验证完整实验管线，再在同一 Gold Set 上比较 BGE、Qwen、E5 等候选的 Recall、MRR、NDCG、P95、吞吐、显存和存储，不能只看公开排行榜。当前仓库的 Hash 指标只用于回归流程，不代表真实模型质量。

#### Q28：向量维度越高越好吗？

**参考回答：** 不一定。维度高可能保留更多表达能力，但会增加存储、内存带宽、索引构建时间和检索成本；如果模型训练质量不够，单纯增加维度也不会提高业务精度。选择时应在同一数据上比较效果与资源，并保证写入、查询和索引声明使用相同维度和距离函数。

#### Q29：为什么选择 pgvector，而不是独立向量数据库？

**参考回答：** 当前规模不大，而且结构化职位、用户权限、申请状态和向量之间有强关系。pgvector 让关系数据、过滤条件和向量处于同一事务与权限边界，部署和备份也更简单。若未来达到超大规模、需要多租户资源隔离或更复杂的分布式向量检索，再评估专用系统；现在引入独立向量数据库会增加一致性和运维成本，收益有限。

#### Q30：HNSW 索引解决什么问题？参数怎么考虑？

**参考回答：** HNSW 是近似最近邻索引，用额外内存和构建时间换更低查询延迟。图连接度和构建搜索范围越大，通常召回更高，但索引更大、构建更慢；查询搜索范围也会在延迟和召回间取舍。小数据量不一定需要近似索引，应该先用精确检索作为基线，再根据真实数据规模和 Recall/延迟曲线调整，而不是照搬默认参数。

### 4.7 RAG 评测与指标

#### Q31：你的评测集是怎么建立的？

**参考回答：** 当前入门集包含 30 篇匿名合成语料和 120 个查询，每个查询标注相关文档和分级相关性，其中一部分做了双重复核。实验固定数据版本，对模型、切分策略和检索模式组成 24 组消融，并记录质量、延迟和失败样例。它适合验证评测管线和防止代码回退，但规模和真实性不足，所以不能当成线上业务结论。

#### Q32：Recall@5、MRR@10 和 NDCG@10 分别说明什么？

**参考回答：** Recall@5 关注相关文档是否进入前五，适合衡量召回有没有漏掉；MRR 看第一个相关结果排在多前，和用户是否能第一眼看到正确答案有关；NDCG 支持多级相关性，并对靠前结果给予更高权重。三者组合能区分“根本没召回”“召回但排得靠后”和“多个结果顺序不合理”。

#### Q33：Recall@5 已经是 1.0，为什么还要优化？

**参考回答：** 因为小型合成集的 Top 5 已经饱和，不代表第一名正确。当前 MRR@10 是 0.7336，并有 48 个查询的相关结果没有排第一，这说明主要瓶颈是排序而不是召回。下一步应该加入同技能、同城市但条件不同的困难负例，使用真实 Embedding 和 Cross-Encoder，重点观察 MRR/NDCG，而不是把 Top K 继续调大来维持漂亮的 Recall。

#### Q34：如何确认某次 RAG 优化真的有效？

**参考回答：** 固定数据集和随机性，每次只改变一个主要变量，例如只换 Embedding 或只换 Chunk，记录模型版本、Query 前缀、Top K、索引参数、硬件和成本。除了比较总体指标，还要查看新增和修复的失败样例，并设置自动门禁。如果同时更换模型、切分和重排，即使指标上涨也无法知道原因，也难以复现。

#### Q35：如何控制检索的延迟和成本？

**参考回答：** 先用结构化条件减少搜索空间，关键词与向量只取有限候选，融合后再对更小集合做重排；文档导入时批量生成向量并缓存模型版本，避免查询时重复处理；用 P50/P95 而不是只看平均延迟。真实模型还要记录 GPU/CPU、吞吐、每万 Chunk 索引成本和每千次查询费用，达到规模后再考虑异步任务和缓存。

### 4.8 LangChain、LangGraph 与 Agent 可靠性

#### Q36：LangChain 和 LangGraph 在项目中分别做什么？

**参考回答：** LangChain 更适合提供模型、Embedding、Reranker、结构化 Tool 和可替换 Adapter 等能力；LangGraph负责有状态工作流，把路由、计划、等待确认、执行和结束表示为显式节点。项目没有让框架接管权限和事务，Tool 最终仍调用已有业务服务。这样既利用 AI 框架的编排能力，又保留后端边界和可测试性。

#### Q37：为什么要用状态机，而不是一个循环 Agent？

**参考回答：** 求职 Agent 包含写数据库的副作用，必须知道当前处于计划、等待确认还是已执行。显式状态机让每个节点的输入输出、允许跳转和失败状态都可检查，可以设置最大步数并保存事件。自由循环实现简单，但容易重复调用 Tool、难以恢复，也很难证明某次写入确实经过确认。

#### Q38：哪些操作需要人工确认，为什么？

**参考回答：** 搜索职位、查看匹配和生成只读报告不会改变外部状态，可以自动执行；创建申请、更新申请状态等会改变用户记录，必须在执行前暂停并展示准确参数。确认围绕副作用边界设置，而不是每个思考步骤都弹窗。这样兼顾安全和使用效率，未来若涉及发送邮件或真实投递，确认和权限要求还要更严格。

#### Q39：Checkpoint、业务状态和事件日志有什么区别？

**参考回答：** Checkpoint 保存工作流运行到哪个节点以及恢复所需状态；业务 Run 保存用户、意图、当前状态、待确认动作和最终结果，支持查询和跨进程审计；事件日志按顺序记录状态变化，供 UI 重放和问题定位。只用内存 Checkpoint 无法抵抗进程重启，只存最终业务状态又无法恢复节点，所以三者承担不同职责。

#### Q40：如何避免用户重复点击确认导致重复申请？

**参考回答：** 前端禁用按钮只能改善交互，网络超时、重试和多实例仍可能重复执行。系统要求确认请求带幂等 Key，将它与用户和请求内容绑定并保存结果；相同请求重试返回已有结果，不同内容复用同一个 Key 会被拒绝。数据库对“用户 + 职位”的申请还有业务唯一约束，必要时使用行锁，因此应用幂等和数据库约束形成双层保护。

#### Q41：Agent 失败或服务重启后如何恢复？

**参考回答：** 每次运行有稳定 Run ID，保存当前节点、待确认动作、步数和事件。恢复时不重新猜测之前要做什么，而是从持久化状态检查待执行动作和用户归属，再继续工作流；最大步数防止异常循环。当前图级 Checkpointer仍有单进程限制，生产环境应换持久化 Checkpointer并由 Worker 获取任务和锁。

#### Q42：如何避免 Agent 生成虚假简历经历？

**参考回答：** 生成器只能使用当前用户简历中选出的证据片段，每条生成结果都携带来源、片段 ID 和原文引用。保存前验证来源属于当前用户和指定简历，并要求 Quote 真正存在于保存的证据中；任一引用无效就整批拒绝。JD 可以用于分析技能缺口，但不能作为用户具备技能的证据。这个方法能阻止无来源文本，但语义改写仍需要进一步的事实一致性评测。

### 4.9 安全、限流与可观测性

#### Q43：RAG Prompt Injection 是什么？项目如何防护？

**参考回答：** Prompt Injection 不只来自用户当前输入，也可能藏在被检索的简历、JD 或学习资料中，例如要求忽略系统规则或泄露提示词。系统把所有导入文档视为不可信数据，扫描常见中英文攻击模式并保存风险标记；命中文档仍可供用户审查，但默认不生成向量、不进入检索上下文。隔离只是第一层，写 Tool 仍要最小权限、结构化参数和人工确认。

#### Q44：为什么发现可疑文档后不直接删除？

**参考回答：** 检测规则存在误报，直接删除会破坏用户数据，也失去复核和审计依据。隔离能先切断它进入模型上下文的路径，同时保留原文和命中原因供人工判断。更成熟的方案应增加人工解除隔离、规则版本和重新扫描；如果新规则命中，已放行文档也应重新评估。

#### Q45：限流是怎么设计的？有什么局限？

**参考回答：** 登录注册的暴力尝试风险高，所以使用比普通 API 更严格的来源限额；超限返回 429、Retry-After 和 Request ID。普通业务请求按匿名化身份划分窗口，不把 Token 写入日志。当前固定窗口保存在单进程内存中，适合演示和单实例，但多个 Worker 会各自计数；生产应使用 Redis 原子计数，并明确 Redis 故障时是放行还是拒绝。

#### Q46：日志如何兼顾排障和隐私？

**参考回答：** 日志记录 Request ID、HTTP 方法、路由模板、状态码、耗时、匿名化用户标识和错误类型，足够定位哪个请求在哪个环节失败。它不记录请求正文、查询中的私人内容、密码、Token 或完整简历。Agent 事件也只保存状态和证据标识，不复制原文。原则是日志回答“发生了什么”，而不是建立第二份私人数据库；部署平台还应统一补充标准时间戳、服务名和环境字段。

#### Q47：liveness 和 readiness 有什么区别？

**参考回答：** liveness 只判断应用进程是否活着，失败通常意味着编排器应该重启；readiness 判断应用现在是否能安全接流量，例如数据库是否连接、向量扩展是否就绪。数据库短暂抖动时 readiness 可以失败并摘除流量，但不应因此反复重启仍在正常恢复的进程。

### 4.10 测试、部署与扩展性

#### Q48：项目如何测试？

**参考回答：** 测试分为规则单元测试、API/事务测试、检索离线评测和前端组件测试。后端覆盖参数校验、状态码、分页、用户隔离、状态转换、Agent 确认与幂等、Token 篡改、提示词注入和删除；检索使用固定数据跑 24 组实验并设置指标门禁；数据库迁移还会检查 ORM 漂移。测试默认不依赖付费模型，使用确定性适配器保证可重复。

#### Q49：SQLite 测试通过是否说明 PostgreSQL 一定没问题？

**参考回答：** 不能。SQLite 单元测试速度快，但类型、并发、全文检索、向量索引和锁行为与 PostgreSQL 不同。项目在 SQLite 测试中主动开启外键减少假安全，同时用真实 pgvector PostgreSQL验证迁移、健康检查、登录和数据隔离。完整工程还应增加独立 PostgreSQL 测试数据库上的并发与向量查询集成测试。

#### Q50：Docker Compose 做了什么？

**参考回答：** Compose 编排 PostgreSQL/pgvector、FastAPI 和 Vue/Nginx。数据库先通过健康检查，API 再自动执行迁移和幂等初始化，readiness 成功后前端才启动。这样新环境不需要手工猜启动顺序。当前默认账号和密钥只适合本地演示，公开部署必须改成 Secret 管理、TLS、备份、最小权限和独立数据库凭证。

#### Q51：如果流量增长十倍，你会先改什么？

**参考回答：** 我会先基于指标找瓶颈，而不是直接拆微服务。高概率优先项包括把 Embedding、Rerank 和 Agent 长任务放入异步 Worker；把内存限流和事件发布迁移到 Redis；使用持久化 Checkpointer；给常用用户过滤和状态查询增加复合索引；对模型结果和稳定检索做缓存；限制上传大小和并发。数据库与向量仍可先共用 PostgreSQL，达到实际容量瓶颈再拆分。

#### Q52：为什么没有使用微服务？

**参考回答：** 当前团队和数据规模都很小，职位、知识库、申请和用户权限之间事务关系强。模块化单体可以保持清晰领域边界，同时部署、调试和事务更简单。微服务会引入网络失败、分布式事务、服务发现和监控成本，暂时没有业务收益。如果未来模型任务需要独立 GPU 扩缩容，我会先把异步模型 Worker 拆出，而不是为了技术栈展示全部拆开。

#### Q53：前端部分你做了什么？

**参考回答：** 前端使用 Vue 3 和 TypeScript 实现职位、知识库、检索实验、Agent 确认和申请看板，并通过统一 Axios 层调用后端。页面处理 loading、empty 和 error，生产模式有登录守卫和 401 跳转。我的主要深度在后端，前端目标是完整展示业务和 API 合同；当前仍有包体较大的构建警告，后续会用路由懒加载和组件按需引入优化。

#### Q54：为什么你没有把项目称为生产级？

**参考回答：** 当前已经有真实鉴权、事务、用户隔离、测试、健康检查和容器化，但仍存在明确边界：浏览器 Token 不是 HttpOnly Cookie，限流不能跨实例，Checkpoint 不是完整多实例方案，模型任务仍可能同步阻塞，评测集主要是合成数据，也没有完成真实压力测试、告警、备份恢复和密钥托管。因此我会称它为“具备生产意识、可继续演进的实习项目”，而不是已经承载线上用户的生产系统。

#### Q55：如果重新做一次，你会优先改进什么？

**参考回答：** 我会更早收集真实匿名 JD 和用户查询，先建立困难负例，再决定 Embedding 和切分；工程上会从一开始使用持久化任务队列和 Checkpointer，并用 HttpOnly Cookie 完成 Web 认证；前端类型会从 OpenAPI 自动生成。我仍会保留模块化单体、关系数据与 pgvector 共库、显式状态机和人工确认，因为这些选择符合当前规模并显著降低一致性风险。

### 4.11 压力追问：避免“只会背项目”

#### Q56：你这个项目是不是只是把很多技术栈拼在一起？

**参考回答：** 如果只是把框架接起来，确实没有价值，所以我用业务问题约束技术选择。PostgreSQL同时承载结构化过滤和向量是为了事务与权限一致；RRF 是为解决异构分数尺度；LangGraph 是为处理暂停和恢复；幂等与唯一约束是为处理重复确认；Prompt Injection 隔离是为保护 Tool 边界。每项技术都有对应测试或指标，也有明确未解决的问题，不是因为招聘 JD 出现了名字就加入。

#### Q57：你的指标这么好，是不是数据太简单？

**参考回答：** 是的，Recall@5 达到 1.0 很大程度上来自只有 30 篇文档的合成入门集，所以我没有把它当成模型效果亮点。更有信息量的是 MRR 只有 0.7336，并暴露了 48 个排序错误。这正说明评测集需要加入真实职位、同义技能、否定条件和近似岗位等困难负例。当前价值是评测流程、门禁和失败分析可复现，而不是数字本身很高。

#### Q58：如果不用 LangGraph，能不能实现？

**参考回答：** 可以，用数据库状态机和任务队列也能实现，而且在简单流程中可能更轻。选择 LangGraph 是因为它原生表达节点、条件跳转、暂停和恢复，适合展示 Agent 状态控制。但业务 Run、权限、事务和幂等仍由自己的后端负责，这样未来即使替换框架，关键业务语义不会丢失。

#### Q59：如果模型不可用，系统还能做什么？

**参考回答：** 职位 CRUD、申请状态、结构化过滤、关键词检索、规则解析、硬条件 Gate 和确定性匹配仍可工作。真实 Embedding 或生成模型故障时应返回明确降级状态，可以只使用关键词结果，而不能悄悄伪造 AI 输出。当前测试适配器也让核心流程不依赖外部付费服务，便于开发和回归。

#### Q60：你从这个项目中最大的收获是什么？

**参考回答：** 最大收获是 AI 应用的难点不只在 Prompt。真正决定系统质量的是数据表示、评测集、权限、事务、副作用、失败恢复和边界表达。一个模型回答看起来不错并不能证明检索有效，一个确认按钮也不能证明写操作幂等。把这些问题转化为指标、数据库约束和自动测试，是我在项目中最重要的工程训练。

## 5. 投递前替换清单

- 把项目时间替换为本人实际开发时间；
- 增加真实 GitHub 地址：`[GitHub URL]`；
- 若确实部署，再增加演示地址：`[Demo URL]`，未部署不要填写；
- 根据岗位 JD 只保留最相关的 3–4 条，不要把三种岗位版本全部堆进一页简历；
- 若后续跑了真实 BGE/Qwen/Cross-Encoder，用同一评测集的新结果替换 Hash 基线，并同时写明设备、数据规模和延迟口径；
- 面试前亲自运行一次登录、导入、检索、Agent 确认、删除账号和 Docker 启动链路，确保每个简历表述都能打开代码解释。

