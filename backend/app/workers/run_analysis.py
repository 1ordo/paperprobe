import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

sync_engine = create_engine(settings.database_url_sync, pool_size=5)
SyncSession = sessionmaker(bind=sync_engine)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="run_analysis_task")
def run_analysis_task(self, paper_id: str, task_id: str):
    from app.models.paper import Paper
    from app.models.assessment import PaperAssessment
    from app.models.task import BackgroundTask

    session = SyncSession()
    try:
        task = session.get(BackgroundTask, task_id)
        if task:
            task.status = "running"
            task.started_at = datetime.now(timezone.utc)
            session.commit()

        paper = session.get(Paper, paper_id)
        if not paper:
            raise ValueError(f"Paper {paper_id} not found")

        # Ensure document is parsed first
        if paper.status not in ("parsed", "embedded", "analyzing", "analyzed", "analysis_failed"):
            raise ValueError(f"Paper {paper_id} must be parsed before analysis (status: {paper.status})")

        paper.status = "analyzing"
        session.commit()

        self.update_state(state="PROGRESS", meta={"step": "embedding", "progress": 0.05})

        # Step 1: Embed the document if not already done
        try:
            from app.workers.embed_document import _embed_paper
            _embed_paper(paper_id, session)
            logger.info(f"Embedding complete for paper {paper_id}")
        except Exception as e:
            logger.warning(f"Embedding failed for paper {paper_id}, continuing without vectors: {e}")

        self.update_state(state="PROGRESS", meta={"step": "initializing", "progress": 0.15})

        # Step 2: Run the AI analysis pipeline
        from app.agents.pipeline import AnalysisPipeline

        pipeline = AnalysisPipeline(paper_id=str(paper.id), session=session)
        result = _run_async(pipeline.run(progress_callback=lambda step, pct: self.update_state(
            state="PROGRESS", meta={"step": step, "progress": pct}
        )))

        paper.status = "analyzed"
        if task:
            task.status = "completed"
            task.progress = 1.0
            task.completed_at = datetime.now(timezone.utc)
        session.commit()

        logger.info(f"Analysis complete for paper {paper_id}")
        return {"paper_id": paper_id, "result": result}

    except Exception as e:
        session.rollback()
        logger.error(f"Analysis failed for paper {paper_id}: {e}")
        try:
            task = session.get(BackgroundTask, task_id)
            if task:
                task.status = "failed"
                task.error_message = str(e)[:1000]
                task.completed_at = datetime.now(timezone.utc)
            paper = session.get(Paper, paper_id)
            if paper:
                paper.status = "analysis_failed"
            session.commit()
        except Exception:
            session.rollback()
        raise
    finally:
        session.close()
