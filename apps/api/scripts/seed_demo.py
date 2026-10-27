import os

from sqlalchemy import select

from app.db.session import SessionLocal
from app.domains.auth.model import User
from app.domains.auth.schemas import RegisterRequest
from app.domains.auth.service import AuthService
from app.domains.jobs.model import Job
from app.domains.jobs.schemas import JobCreate
from app.domains.jobs.service import JobService
from app.domains.resumes.model import Resume, ResumeTemplate
from app.domains.resumes.schemas import ResumeImportText
from app.domains.resumes.service import ResumeService

DEMO_JOBS = [
    {
        "title": "AI 应用开发实习生",
        "company_name": "星河智能",
        "city": "上海",
        "remote_type": "hybrid",
        "salary_min": "200",
        "salary_max": "300",
        "internship_days_per_week": 4,
        "internship_months": 4,
        "required_skills": ["Python", "FastAPI", "RAG"],
        "preferred_skills": ["Vue 3", "LangChain"],
        "source_url": "https://example.com/jobs/ai-application-intern",
        "raw_text": (
            "参与 AI 应用产品的设计与开发，使用 Python、FastAPI 和 RAG 构建后端能力，"
            "并与 Vue 前端协作完成面向用户的智能产品。"
        ),
    },
    {
        "title": "大模型平台研发实习生",
        "company_name": "云帆科技",
        "city": "北京",
        "remote_type": "onsite",
        "salary_min": "250",
        "salary_max": "400",
        "internship_days_per_week": 5,
        "internship_months": 6,
        "required_skills": ["Python", "PostgreSQL", "Docker"],
        "preferred_skills": ["LangGraph", "pgvector"],
        "source_url": "https://example.com/jobs/llm-platform-intern",
        "raw_text": (
            "参与大模型应用平台后端研发，建设任务编排、模型服务和可观测性能力，"
            "要求具备 Python Web、关系数据库与容器化基础。"
        ),
    },
    {
        "title": "AI 产品全栈实习生",
        "company_name": "青屿实验室",
        "city": "杭州",
        "remote_type": "remote",
        "salary_min": "180",
        "salary_max": "280",
        "internship_days_per_week": 4,
        "internship_months": 3,
        "required_skills": ["TypeScript", "Vue 3", "REST API"],
        "preferred_skills": ["FastAPI", "LLM"],
        "source_url": "https://example.com/jobs/ai-fullstack-intern",
        "raw_text": (
            "负责 AI 产品原型和全栈功能开发，使用 Vue 3、TypeScript 与 REST API，"
            "有 Python 或 FastAPI 项目经验者优先。"
        ),
    },
]


DEMO_RESUME = """沈鑫
19923458371
shenxin@example.com

教育经历
西安石油大学 | 新能源科学与工程 · 本科 | 2019.09 - 2023.06
- 专业成绩：综测排名前 50%
- 主修课程：计算机网络基础、数据结构、线性代数、概率论

南京信息工程大学 | 计算机技术 · 硕士 | 2024.09 - 2027.06
- 学校层次：双一流
- 专业成绩：综测排名前 30%
- 主修课程：机器学习、线性系统理论、算法设计与分析

项目经历
AI 求职规划与岗位匹配 Agent | 技术栈：Python、FastAPI、SQLAlchemy、PostgreSQL、LangChain、LangGraph、Vue 3、Docker
- 使用 LangChain 将职位检索、匹配分析和技能差距分析封装为结构化 Tool，并基于 LangGraph 编排意图路由、任务计划、人工确认和恢复流程。
- 围绕简历与 JD 设计标题感知 Chunk 的 RAG 数据链路，结合全文检索、向量召回、RRF 融合与重排做覆盖排名与语义改写。
- 对私人知识库执行 Prompt Injection 扫描和检索隔离，生成材料携带可验证 Citation。

MiniOpenClaw-Agent 编程助手 | 技术栈：Python、asyncio、PyTest、SSE、MCP、JSONL
- 基于 Python 搭建支持 CLI 与飞书 IM 双入口的 AI Agent 编程助手，采用模型接口层、Agent 编排层和应用能力层三层架构。
- 实现 ReAct 的多轮 Agent Loop，支持 Thinking 过程展示、SSE 流式事件分发与工具串行执行。
- 设计基于消息数与 token 阈值的上下文压缩，结合 LLM 摘要、指数退避重试和会话分叉树结构。

专业技能
语言能力：已通过英语 CET-4、CET-6
- 熟练使用 Python、SQL、Docker、Git 相关命令；能够运用 Pytest、Postman 等工具编写自动化测试脚本。

自我评价
有较强的工程落地能力，喜欢把复杂问题拆成可验证的小步骤。
"""


def main() -> None:
    with SessionLocal() as session:
        seed_email = os.getenv("CAREERPILOT_SEED_EMAIL")
        if seed_email:
            user = session.scalar(select(User).where(User.email == seed_email.lower()))
            if user is None:
                token = AuthService(session).register(
                    RegisterRequest(
                        email=seed_email,
                        password=os.getenv("CAREERPILOT_SEED_PASSWORD", "CareerPilot-demo-2026"),
                    )
                )
                user_id = token.user.id
            else:
                user_id = user.id
        else:
            user_id = "demo-user"
        exists = session.scalar(select(Job.id).where(Job.user_id == user_id).limit(1))
        if exists:
            print("Demo jobs already exist; skipping job seed.")
        else:
            service = JobService(session)
            for item in DEMO_JOBS:
                service.create_job(user_id=user_id, payload=JobCreate(**item))
            print(f"Seeded {len(DEMO_JOBS)} demo jobs.")

        existing_resume = session.scalar(
            select(Resume.id).where(Resume.user_id == user_id).limit(1)
        )
        if existing_resume:
            print("Demo resume workspace already exists; nothing to seed.")
            return
        target_job = session.scalar(
            select(Job).where(Job.user_id == user_id).order_by(Job.created_at).limit(1)
        )
        ResumeService(session).import_text(
            user_id=user_id,
            payload=ResumeImportText(
                display_name="示例简历",
                raw_text=DEMO_RESUME,
                template=ResumeTemplate.modern,
                target_job_id=target_job.id if target_job is not None else None,
            ),
        )
        print("Seeded 1 demo resume workspace.")


if __name__ == "__main__":
    main()
