# CareerPilot

CareerPilot 是一个面向 AI 实习求职的个人工作台：收录职位公告、管理投递进展、维护可编辑简历，并用可解释的匹配与 AI 建议解释「差在哪、下一步做什么」。

## 项目结构

- `apps/api`：FastAPI、SQLAlchemy、Alembic 及后端测试
- `apps/web`：Vue 3、TypeScript 和前端测试
- `apps/api/app/domains/jobs`：职位目录（公司 → 招聘公告 → 岗位）、导入候选队列、公众号文章适配器
- `apps/api/app/domains/documents`：简历、JD 和学习材料导入、解析、分块
- `apps/api/app/domains/resumes`：可编辑简历工作台、AI 简历优化（匹配报告、建议稿、应用与撤销）
- `apps/api/app/domains/applications`：投递记录、完成态状态机、阶段详情（笔试/面试/Offer）与时间线
- `apps/api/app/domains/retrieval`：关键词/向量检索与排序
- `apps/api/app/domains/matching`：职位与简历的可解释匹配
- `apps/api/app/domains/ai`：OpenAI / Anthropic 双格式客户端、可选抽取增强、调用指标（凭据不落库）
- `apps/api/app/domains/agent`：求职决策 Agent、确认和事件记录
- `apps/autofill-extension`：Manifest V3 review-first 网申字段填写扩展
- `AI_INTERNSHIP_AGENT_ARCHITECTURE.md`：求职系统架构说明

## 主要能力

- **职位信息**（`/workspace/jobs`）：公告级列表 + 基础/高级筛选 + 列设置（服务端持久化）+ 导入（粘贴/文件/公众号链接）+ 公告详情与岗位清单。
- **投递记录**（`/workspace/applications`）：搜索、状态筛选、手动新增、分页；状态只有完成态（`未投递/已投递/已笔试/已面试/面试通过/已挂/已放弃`），面试排期写在「已面试」的补充详情里；误操作可把终态修正回「已投递」。
- **提醒中心**：顶栏铃铛汇总跟进到期、面试临近、久无回音与 Offer 答复截止，可完成/稍后提醒/忽略；投递进入终态会自动关闭待办。
- **我的简历**（`/workspace/resumes`）：模板切换、章节编辑、实时预览、AI 优化、导出；可把某条公告设为目标岗位；投递时会锁定当时的简历快照，之后改简历也能回放「投出去的是哪一版」。
- **更多工具**：网申个人信息（仅浏览器本地）、网申填写插件、资料库、证据检索、求职 Agent、AI 与设置（OpenAI/Anthropic 双格式，Key 只留本地）。
- 后端接口以 `/api/v1/workspace/*` 为主；旧 `/api/v1/applications`、`/api/v1/jobs` 标记为 deprecated，仅保留一版兼容。

设计文档：`docs/CAREERPILOT_REFACTOR_PLAN.md`（改造与偏离记录）、`docs/RESUME_OPTIMIZATION.md`（简历优化）、`docs/BUSINESS_WORKFLOW.md`（业务闭环）。

项目深度解析：`docs/PROJECT_DEEP_DIVE.md`（架构、数据模型、核心链路、工程化专题、73 题面试问答库）。

业务场景学习指南：`docs/PROJECT_STUDY_GUIDE.md`（前后端穿透：六大业务链路按「前端交互 → 接口契约 → 后端分层 → 数据落库 → 异常分支 → 面试深挖」逐层展开）。

网申填写扩展会扫描当前页面，调用 CareerPilot 生成带来源和置信度的 Autofill Plan，只填写高置信字段；开放题、文件上传和未知字段必须人工审核，扩展不会自动提交。

公众号文章导入遵守 `mp.weixin.qq.com/robots.txt`（该站禁止 `/s/…`），默认拒绝抓取并提示改用「粘贴正文」；如你已获得授权，可设置 `CAREERPILOT_WECHAT_RESPECT_ROBOTS=false`。

## 本地运行

后端依赖：

```powershell
.\\.venv\\Scripts\\python.exe -m pip install -e ".\\apps\\api[dev]"
Copy-Item .env.example apps\\api\\.env
```

启动 PostgreSQL 后执行迁移：

```powershell
Set-Location apps\\api
..\\..\\.venv\\Scripts\\python.exe -m alembic upgrade head
Set-Location ..\\..
```

启动 API：

```powershell
Set-Location apps\\api
..\\..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --reload
```

启动前端：

```powershell
Set-Location apps\\web
npm install --cache D:\\AI\\Agent\\.npm-cache
npm run dev
```

默认 API 地址为 `http://127.0.0.1:8000`，前端地址为 `http://127.0.0.1:5173`。

## 验证

```powershell
Set-Location apps\\api
..\\..\\.venv\\Scripts\\python.exe -m pytest
..\\..\\.venv\\Scripts\\python.exe -m ruff check .
Set-Location ..\\web
npm run test
npm run typecheck
npm run build
```

## Docker

```powershell
docker compose -f infra\\docker-compose.yml up --build -d
```

Compose 会启动 PostgreSQL、API 和 Vue/Nginx；访问 `http://localhost:8080`。
