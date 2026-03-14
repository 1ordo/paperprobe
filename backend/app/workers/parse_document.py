import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.services.document_parser import parse_document, chunk_text
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

sync_engine = create_engine(settings.database_url_sync, pool_size=5)
SyncSession = sessionmaker(bind=sync_engine)


@celery_app.task(bind=True, name="parse_document_task")
def parse_document_task(self, paper_id: str, task_id: str):
    from app.models.paper import Paper
    from app.models.document import DocumentSection, DocumentChunk
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

        self.update_state(state="PROGRESS", meta={"step": "parsing", "progress": 0.1})

        # Parse the document
        parsed = parse_document(paper.file_path)

        # Update paper metadata
        paper.title = parsed.title or paper.title
        paper.authors = parsed.authors
        paper.year = parsed.year
        paper.page_count = parsed.page_count
        paper.status = "parsed"
        session.flush()

        self.update_state(state="PROGRESS", meta={"step": "sections", "progress": 0.4})

        # Store sections
        section_map = {}
        for sec in parsed.sections:
            db_section = DocumentSection(
                paper_id=paper.id,
                section_type=sec.section_type,
                heading=sec.heading,
                content=sec.content,
                page_start=sec.page_start,
                page_end=sec.page_end,
                position_order=sec.position_order,
            )
            session.add(db_section)
            session.flush()
            section_map[sec.position_order] = db_section

        self.update_state(state="PROGRESS", meta={"step": "chunking", "progress": 0.6})

        # Chunk each section
        chunk_index = 0
        for sec in parsed.sections:
            db_section = section_map.get(sec.position_order)
            chunks = chunk_text(sec.content, chunk_size=512, overlap=50)
            for chunk in chunks:
                db_chunk = DocumentChunk(
                    paper_id=paper.id,
                    section_id=db_section.id if db_section else None,
                    chunk_text=chunk["text"],
                    chunk_index=chunk_index,
                    page_number=sec.page_start,
                    char_start=chunk["char_start"],
                    char_end=chunk["char_end"],
                )
                session.add(db_chunk)
                chunk_index += 1

        paper.status = "parsed"
        if task:
            task.status = "completed"
            task.progress = 1.0
            task.completed_at = datetime.now(timezone.utc)
        session.commit()

        logger.info(f"Parsed paper {paper_id}: {len(parsed.sections)} sections, {chunk_index} chunks")
        return {"paper_id": paper_id, "sections": len(parsed.sections), "chunks": chunk_index}

    except Exception as e:
        session.rollback()
        logger.error(f"Parse failed for paper {paper_id}: {e}")
        try:
            if task:
                task = session.get(BackgroundTask, task_id)
                if task:
                    task.status = "failed"
                    task.error_message = str(e)[:1000]
                    task.completed_at = datetime.now(timezone.utc)
            paper = session.get(Paper, paper_id)
            if paper:
                paper.status = "parse_failed"
            session.commit()
        except Exception:
            session.rollback()
        raise
    finally:
        session.close()
