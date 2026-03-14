from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import PaperAssessment, StandardRating, RatingEvidence, BoxRating, Paper
from app.schemas.assessment import AssessmentOut, StandardRatingOut, RatingUpdate, BoxRatingOut

router = APIRouter()


@router.get("/by-paper/{paper_id}", response_model=AssessmentOut)
async def get_assessment(paper_id: UUID, db: AsyncSession = Depends(get_db)):
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
        raise HTTPException(status_code=404, detail="No assessment found for this paper")
    return AssessmentOut.model_validate(assessment)


@router.get("/by-paper/{paper_id}/summary")
async def get_assessment_summary(paper_id: UUID, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(PaperAssessment)
        .options(selectinload(PaperAssessment.box_ratings))
        .where(PaperAssessment.paper_id == paper_id)
    )
    result = await db.execute(stmt)
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="No assessment found")
    return {
        "assessment_id": str(assessment.id),
        "status": assessment.status,
        "relevant_boxes": assessment.relevant_boxes,
        "box_ratings": [BoxRatingOut.model_validate(br) for br in assessment.box_ratings],
    }


@router.patch("/{assessment_id}/ratings/{standard_id}", response_model=StandardRatingOut)
async def update_rating(assessment_id: UUID, standard_id: int, data: RatingUpdate, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(StandardRating)
        .options(selectinload(StandardRating.evidence))
        .where(StandardRating.assessment_id == assessment_id, StandardRating.standard_id == standard_id)
    )
    result = await db.execute(stmt)
    rating = result.scalar_one_or_none()
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(rating, field, value)

    if data.reviewer1_rating is not None:
        rating.reviewer1_at = datetime.utcnow()
    if data.reviewer2_rating is not None:
        rating.reviewer2_at = datetime.utcnow()
    if data.final_rating is not None:
        rating.finalized_at = datetime.utcnow()

    await db.flush()
    await db.refresh(rating)
    return StandardRatingOut.model_validate(rating)


@router.post("/{assessment_id}/finalize")
async def finalize_assessment(assessment_id: UUID, db: AsyncSession = Depends(get_db)):
    assessment = await db.get(PaperAssessment, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    assessment.status = "finalized"
    await db.flush()
    return {"status": "finalized", "assessment_id": str(assessment_id)}
