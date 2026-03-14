import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.services.ai_client import AIClient
from app.services.vector_store import VectorStore
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

sync_engine = create_engine(settings.database_url_sync, pool_size=5)
SyncSession = sessionmaker(bind=sync_engine)


def _run_async(coro):
    """Run an async function from sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _embed_paper(paper_id: str, session=None):
    """Core embedding logic, callable from other tasks or standalone."""
    from app.models.document import DocumentChunk

    own_session = session is None
    if own_session:
        session = SyncSession()

    try:
        chunks = (
            session.query(DocumentChunk)
            .filter(DocumentChunk.paper_id == paper_id)
            .order_by(DocumentChunk.chunk_index)
            .all()
        )

        if not chunks:
            logger.warning(f"No chunks found for paper {paper_id}")
            return 0

        ai_client = AIClient()
        vector_store = VectorStore()

        batch_size = 32
        all_point_ids = []
        total = len(chunks)

        for i in range(0, total, batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c.chunk_text for c in batch]

            embeddings = _run_async(ai_client.create_embeddings_batch(texts))

            chunk_dicts = [
                {
                    "text": c.chunk_text,
                    "chunk_index": c.chunk_index,
                    "page_number": c.page_number,
                    "char_start": c.char_start,
                    "char_end": c.char_end,
                    "section_type": None,
                }
                for c in batch
            ]

            point_ids = vector_store.upsert_chunks(chunk_dicts, embeddings, paper_id)
            all_point_ids.extend(point_ids)

            for chunk, pid in zip(batch, point_ids):
                chunk.embedding_id = pid

        session.commit()
        logger.info(f"Embedded {len(all_point_ids)} chunks for paper {paper_id}")
        return len(all_point_ids)

    except Exception:
        if own_session:
            session.rollback()
        raise
    finally:
        if own_session:
            session.close()


@celery_app.task(bind=True, name="embed_document_task")
def embed_document_task(self, paper_id: str, task_id: str | None = None):
    from app.models.task import BackgroundTask

    session = SyncSession()
    try:
        if task_id:
            task = session.get(BackgroundTask, task_id)
            if task:
                task.status = "running"
                task.started_at = datetime.now(timezone.utc)
                session.commit()
        else:
            task = None

        self.update_state(state="PROGRESS", meta={"step": "embedding", "progress": 0.2})
        embedded = _embed_paper(paper_id, session)

        if task:
            task.status = "completed"
            task.progress = 1.0
            task.completed_at = datetime.now(timezone.utc)
            session.commit()

        return {"paper_id": paper_id, "embedded": embedded}

    except Exception as e:
        session.rollback()
        logger.error(f"Embedding failed for paper {paper_id}: {e}")
        try:
            if task_id:
                task = session.get(BackgroundTask, task_id)
                if task:
                    task.status = "failed"
                    task.error_message = str(e)[:1000]
                    task.completed_at = datetime.now(timezone.utc)
                session.commit()
        except Exception:
            session.rollback()
        raise
    finally:
        session.close()
