from fastapi import APIRouter

from app.api.projects import router as projects_router
from app.api.papers import router as papers_router
from app.api.cosmin_checklist import router as cosmin_router
from app.api.assessments import router as assessments_router
from app.api.analysis import router as analysis_router
from app.api.export import router as export_router

api_router = APIRouter()

api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(papers_router, prefix="/papers", tags=["papers"])
api_router.include_router(cosmin_router, prefix="/cosmin", tags=["cosmin"])
api_router.include_router(assessments_router, prefix="/assessments", tags=["assessments"])
api_router.include_router(analysis_router, prefix="/analysis", tags=["analysis"])
api_router.include_router(export_router, prefix="/export", tags=["export"])
