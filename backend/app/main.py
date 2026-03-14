import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.upload_dir, exist_ok=True)

    # Auto-create tables and seed COSMIN checklist
    from app.database import engine, async_session
    from app.database import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        from app.cosmin_data.seed import seed_cosmin_checklist_async
        try:
            await seed_cosmin_checklist_async(session)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"COSMIN seed skipped: {e}")

    yield


app = FastAPI(
    title="COSMIN Risk of Bias Checker",
    description="AI-assisted COSMIN Risk of Bias assessment platform for systematic reviews",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

if os.path.isdir(settings.upload_dir):
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "cosmin-checker"}
