# CareerPilot 开发约束

CareerPilot 是个人求职系统，核心业务是职位管理、简历与项目材料管理、检索、匹配分析、申请跟踪和求职 Agent。

## 边界

- 职位、文档、申请和 Agent 数据按 `user_id` 隔离。
- Agent 只能通过领域 Service 使用职位、文档、匹配和申请能力，不能直接操作数据库。
- 外部副作用（例如创建申请或改变申请状态）必须经过显式确认，并记录可复盘事件。
- 检索结果必须保留来源文档和 Chunk 引用，生成内容不能超出证据。
- 求职系统的 jobs、documents、retrieval、matching、applications 和 agent 代码属于核心功能，修改时必须先确认调用链。

## 验收

后端改动运行 `pytest` 和 `ruff check .`；前端改动运行 `npm run test`、`npm run typecheck` 和 `npm run build`。涉及数据库模型或迁移时额外运行 Alembic 检查。

## 命名

产品名统一使用 `CareerPilot`，后端包名保持 `careerpilot-api`，配置变量保持 `CAREERPILOT_` 前缀。
