import os

from sqlalchemy import select

from app.db.session import SessionLocal
from app.domains.auth.model import User
from app.domains.auth.schemas import RegisterRequest
from app.domains.auth.service import AuthService
from app.domains.jobs.model import Job
from app.domains.jobs.schemas import JobCreate
from app.domains.jobs.service import JobService

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
            print("Demo jobs already exist; nothing to seed.")
            return
        service = JobService(session)
        for item in DEMO_JOBS:
            service.create_job(user_id=user_id, payload=JobCreate(**item))
        print(f"Seeded {len(DEMO_JOBS)} demo jobs.")


if __name__ == "__main__":
    main()
