from uuid import UUID
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Paper, PaperAssessment, StandardRating, RatingEvidence, BoxRating, CosminStandard, CosminSubBox, CosminBox
from app.services.export_service import generate_excel_export, generate_csv_export

router = APIRouter()


@router.get("/paper/{paper_id}")
async def export_paper(paper_id: UUID, format: str = Query("xlsx"), db: AsyncSession = Depends(get_db)):
    paper = await db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    stmt = (
        select(PaperAssessment)
        .options(
            selectinload(PaperAssessment.standard_ratings).selectinload(StandardRating.evidence),
            selectinload(PaperAssessment.box_ratings),
        )
        .where(PaperAssessment.paper_id == paper_id)
    )
    result = await db.execute(stmt)
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="No assessment found")

    # Get all standards for context
    std_stmt = (
        select(CosminStandard)
        .join(CosminSubBox, CosminStandard.sub_box_id == CosminSubBox.id)
        .join(CosminBox, CosminSubBox.box_id == CosminBox.id)
        .order_by(CosminBox.box_number, CosminSubBox.sort_order, CosminStandard.sort_order)
    )
    std_result = await db.execute(std_stmt)
    standards = std_result.scalars().all()

    if format == "csv":
        output = generate_csv_export(paper, assessment, standards)
        return StreamingResponse(
            BytesIO(output.encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={paper.filename}_cosmin.csv"},
        )
    else:
        output = generate_excel_export(paper, assessment, standards)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={paper.filename}_cosmin.xlsx"},
        )
