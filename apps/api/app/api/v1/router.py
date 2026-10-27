from fastapi import APIRouter

from app.api.v1.agent import router as agent_router
from app.api.v1.applications import router as applications_router
from app.api.v1.assistant import router as assistant_router
from app.api.v1.auth import router as auth_router
from app.api.v1.documents import router as documents_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.matching import router as matching_router
from app.api.v1.reminders import router as reminders_router
from app.api.v1.resumes import router as resumes_router
from app.api.v1.retrieval import router as retrieval_router
from app.api.v1.settings import router as settings_router
from app.api.v1.workspace import router as workspace_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(workspace_router)
router.include_router(reminders_router)
router.include_router(settings_router)
router.include_router(assistant_router)
router.include_router(jobs_router)
router.include_router(matching_router)
router.include_router(documents_router)
router.include_router(resumes_router)
router.include_router(retrieval_router)
router.include_router(applications_router)
router.include_router(agent_router)
