from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Paper, PaperAssessment, BackgroundTask

router = APIRouter()


@router.post("/paper/{paper_id}/analyze")
async def trigger_analysis(paper_id: UUID, db: AsyncSession = Depends(get_db)):
    paper = await db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    if paper.status not in ("parsed", "embedded", "analyzed", "analysis_failed"):
        raise HTTPException(status_code=400, detail=f"Paper must be parsed first. Current status: {paper.status}")

    # Create background task record first, then dispatch celery
    bg_task = BackgroundTask(
        paper_id=paper_id,
        task_type="analyze",
        status="pending",
    )
    db.add(bg_task)
    await db.flush()
    await db.refresh(bg_task)

    from app.workers.run_analysis import run_analysis_task
    celery_result = run_analysis_task.delay(str(paper_id), str(bg_task.id))
    bg_task.celery_task_id = celery_result.id
    bg_task.status = "running"

    paper.status = "analyzing"
    await db.flush()
    await db.refresh(bg_task)

    return {
        "task_id": str(bg_task.id),
        "celery_task_id": celery_result.id,
        "status": "running",
    }


@router.get("/paper/{paper_id}/status")
async def get_analysis_status(paper_id: UUID, db: AsyncSession = Depends(get_db)):
    paper = await db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    stmt = (
        select(BackgroundTask)
        .where(BackgroundTask.paper_id == paper_id)
        .order_by(BackgroundTask.created_at.desc())
        .limit(5)
    )
    result = await db.execute(stmt)
    tasks = result.scalars().all()

    # Try to get live Celery task progress for running tasks
    celery_meta = {}
    for t in tasks:
        if t.status == "running" and t.celery_task_id:
            try:
                from app.workers.celery_app import celery_app
                async_result = celery_app.AsyncResult(t.celery_task_id)
                if async_result.state == "PROGRESS":
                    celery_meta[str(t.id)] = async_result.info or {}
                elif async_result.state in ("SUCCESS", "FAILURE"):
                    celery_meta[str(t.id)] = {"step": async_result.state.lower(), "progress": 1.0 if async_result.state == "SUCCESS" else 0}
            except Exception:
                pass

    return {
        "paper_id": str(paper_id),
        "paper_status": paper.status,
        "tasks": [
            {
                "id": str(t.id),
                "task_type": t.task_type,
                "status": t.status,
                "progress": celery_meta.get(str(t.id), {}).get("progress", t.progress),
                "step": celery_meta.get(str(t.id), {}).get("step"),
                "error_message": t.error_message,
                "started_at": t.started_at.isoformat() if t.started_at else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in tasks
        ],
    }
