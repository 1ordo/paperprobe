import os
import uuid as uuid_mod
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models import Paper, Project, DocumentSection, DocumentChunk
from app.schemas.paper import PaperOut, PaperUpdate

router = APIRouter()


@router.get("/by-project/{project_id}", response_model=list[PaperOut])
async def list_papers(project_id: UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(Paper).where(Paper.project_id == project_id).order_by(Paper.created_at.desc())
    result = await db.execute(stmt)
    return [PaperOut.model_validate(p) for p in result.scalars().all()]


@router.post("/upload/{project_id}", response_model=PaperOut, status_code=201)
async def upload_paper(project_id: UUID, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else ""
    if ext not in ("pdf", "docx"):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

    file_id = str(uuid_mod.uuid4())
    save_dir = os.path.join(settings.upload_dir, str(project_id))
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, f"{file_id}.{ext}")

    content = await file.read()
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds {settings.max_upload_size_mb}MB limit")

    with open(file_path, "wb") as f:
        f.write(content)

    paper = Paper(
        project_id=project_id,
        filename=file.filename or f"{file_id}.{ext}",
        file_path=file_path,
        file_type=ext,
        status="uploaded",
    )
    db.add(paper)
    await db.flush()
    await db.refresh(paper)

    # Create background task record and trigger parsing
    from app.models.task import BackgroundTask as BgTask
    bg_task = BgTask(paper_id=paper.id, task_type="parse", status="pending")
    db.add(bg_task)
    await db.flush()
    await db.refresh(bg_task)

    from app.workers.parse_document import parse_document_task
    celery_result = parse_document_task.delay(str(paper.id), str(bg_task.id))
    bg_task.celery_task_id = celery_result.id

    paper.status = "parsing"
    await db.flush()
    await db.refresh(paper)

    return PaperOut.model_validate(paper)


@router.get("/{paper_id}", response_model=PaperOut)
async def get_paper(paper_id: UUID, db: AsyncSession = Depends(get_db)):
    paper = await db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return PaperOut.model_validate(paper)


@router.put("/{paper_id}", response_model=PaperOut)
async def update_paper(paper_id: UUID, data: PaperUpdate, db: AsyncSession = Depends(get_db)):
    paper = await db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(paper, field, value)
    await db.flush()
    await db.refresh(paper)
    return PaperOut.model_validate(paper)


@router.delete("/{paper_id}", status_code=204)
async def delete_paper(paper_id: UUID, db: AsyncSession = Depends(get_db)):
    paper = await db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    if os.path.exists(paper.file_path):
        os.remove(paper.file_path)
    await db.delete(paper)


@router.get("/{paper_id}/file")
async def serve_paper_file(paper_id: UUID, db: AsyncSession = Depends(get_db)):
    paper = await db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    if not os.path.exists(paper.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    media_type = "application/pdf" if paper.file_type == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(paper.file_path, media_type=media_type, filename=paper.filename)


@router.get("/{paper_id}/sections")
async def get_paper_sections(paper_id: UUID, db: AsyncSession = Depends(get_db)):
    stmt = select(DocumentSection).where(DocumentSection.paper_id == paper_id).order_by(DocumentSection.position_order)
    result = await db.execute(stmt)
    sections = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "section_type": s.section_type,
            "heading": s.heading,
            "content": s.content,
            "page_start": s.page_start,
            "page_end": s.page_end,
            "position_order": s.position_order,
        }
        for s in sections
    ]


@router.get("/{paper_id}/chunks")
async def get_paper_chunks(paper_id: UUID, page: int | None = Query(None), db: AsyncSession = Depends(get_db)):
    stmt = select(DocumentChunk).where(DocumentChunk.paper_id == paper_id)
    if page is not None:
        stmt = stmt.where(DocumentChunk.page_number == page)
    stmt = stmt.order_by(DocumentChunk.chunk_index)
    result = await db.execute(stmt)
    chunks = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "chunk_text": c.chunk_text,
            "chunk_index": c.chunk_index,
            "page_number": c.page_number,
            "char_start": c.char_start,
            "char_end": c.char_end,
        }
        for c in chunks
    ]
