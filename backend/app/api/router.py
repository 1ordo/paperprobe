from fastapi import APIRouter, Depends

from app.api.auth import router as auth_router, require_auth
from app.api.projects import router as projects_router
from app.api.papers import router as papers_router
from app.api.cosmin_checklist import router as cosmin_router
from app.api.assessments import router as assessments_router
from app.api.analysis import router as analysis_router
from app.api.export import router as export_router
from app.api.assistant import router as assistant_router

api_router = APIRouter()

# Auth routes are public (no token required)
api_router.include_router(auth_router, tags=["auth"])

# All other routes require authentication
api_router.include_router(projects_router, prefix="/projects", tags=["projects"], dependencies=[Depends(require_auth)])
api_router.include_router(papers_router, prefix="/papers", tags=["papers"], dependencies=[Depends(require_auth)])
api_router.include_router(cosmin_router, prefix="/cosmin", tags=["cosmin"], dependencies=[Depends(require_auth)])
api_router.include_router(assessments_router, prefix="/assessments", tags=["assessments"], dependencies=[Depends(require_auth)])
api_router.include_router(analysis_router, prefix="/analysis", tags=["analysis"], dependencies=[Depends(require_auth)])
api_router.include_router(export_router, prefix="/export", tags=["export"], dependencies=[Depends(require_auth)])
api_router.include_router(assistant_router, tags=["assistant"], dependencies=[Depends(require_auth)])
