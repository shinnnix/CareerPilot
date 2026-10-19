# CareerPilot

CareerPilot 是一个面向 AI 实习求职的个人工作台：导入简历、项目材料和职位 JD，建立可检索的知识库，解释职位匹配度与技能差距，并跟踪申请进度。

## 项目结构

- `apps/api`：FastAPI、SQLAlchemy、Alembic 及后端测试
- `apps/web`：Vue 3、TypeScript 和前端测试
- `apps/api/app/domains/jobs`：职位 CRUD
- `apps/api/app/domains/documents`：简历、JD 和学习材料导入、解析、分块
- `apps/api/app/domains/retrieval`：关键词/向量检索与排序
- `apps/api/app/domains/matching`：职位与简历的可解释匹配
- `apps/api/app/domains/applications`：申请状态、时间线和反馈
- `apps/api/app/domains/agent`：求职决策 Agent、确认和事件记录
- `apps/autofill-extension`：Manifest V3 review-first 网申字段填写扩展
- `AI_INTERNSHIP_AGENT_ARCHITECTURE.md`：求职系统架构说明

网申填写扩展会扫描当前页面，调用 CareerPilot 生成带来源和置信度的 Autofill Plan，只填写高置信字段；开放题、文件上传和未知字段必须人工审核，扩展不会自动提交。

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
