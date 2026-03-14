from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import CosminBox, CosminSubBox, CosminStandard
from app.schemas.cosmin import CosminBoxOut, CosminSubBoxOut, CosminStandardOut

router = APIRouter()


@router.get("/boxes", response_model=list[CosminBoxOut])
async def list_boxes(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(CosminBox)
        .options(selectinload(CosminBox.sub_boxes).selectinload(CosminSubBox.standards))
        .order_by(CosminBox.box_number)
    )
    result = await db.execute(stmt)
    boxes = result.scalars().unique().all()
    return [CosminBoxOut.model_validate(b) for b in boxes]


@router.get("/boxes/{box_number}", response_model=CosminBoxOut)
async def get_box(box_number: int, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(CosminBox)
        .options(selectinload(CosminBox.sub_boxes).selectinload(CosminSubBox.standards))
        .where(CosminBox.box_number == box_number)
    )
    result = await db.execute(stmt)
    box = result.scalar_one_or_none()
    if not box:
        raise HTTPException(status_code=404, detail=f"Box {box_number} not found")
    return CosminBoxOut.model_validate(box)


@router.get("/standards", response_model=list[CosminStandardOut])
async def list_standards(box_number: int | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(CosminStandard)
    if box_number is not None:
        stmt = (
            stmt.join(CosminSubBox, CosminStandard.sub_box_id == CosminSubBox.id)
            .join(CosminBox, CosminSubBox.box_id == CosminBox.id)
            .where(CosminBox.box_number == box_number)
        )
    stmt = stmt.order_by(CosminStandard.sort_order)
    result = await db.execute(stmt)
    return [CosminStandardOut.model_validate(s) for s in result.scalars().all()]
