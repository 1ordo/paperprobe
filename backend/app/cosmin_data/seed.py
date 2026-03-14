"""Seed the database with COSMIN checklist data."""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cosmin import CosminBox, CosminSubBox, CosminStandard
from app.cosmin_data.checklist_v2 import COSMIN_BOXES

logger = logging.getLogger(__name__)


def seed_cosmin_checklist(session: Session):
    """Insert all COSMIN boxes, sub-boxes, and standards into the database."""
    existing = session.execute(select(CosminBox)).scalars().all()
    if existing:
        logger.info(f"COSMIN checklist already seeded ({len(existing)} boxes). Skipping.")
        return

    total_standards = 0
    for box_data in COSMIN_BOXES:
        box = CosminBox(
            box_number=box_data["box_number"],
            name=box_data["name"],
            description=box_data.get("description"),
            prerequisite=box_data.get("prerequisite"),
        )
        session.add(box)
        session.flush()

        for sb_data in box_data["sub_boxes"]:
            sub_box = CosminSubBox(
                box_id=box.id,
                sub_box_code=sb_data["sub_box_code"],
                name=sb_data["name"],
                section_group=sb_data.get("section_group"),
                sort_order=sb_data["sort_order"],
            )
            session.add(sub_box)
            session.flush()

            for std_data in sb_data["standards"]:
                standard = CosminStandard(
                    sub_box_id=sub_box.id,
                    standard_number=std_data["standard_number"],
                    question_text=std_data["question_text"],
                    section_group=std_data.get("section_group"),
                    rating_very_good=std_data.get("rating_very_good"),
                    rating_adequate=std_data.get("rating_adequate"),
                    rating_doubtful=std_data.get("rating_doubtful"),
                    rating_inadequate=std_data.get("rating_inadequate"),
                    na_allowed=std_data.get("na_allowed", False),
                    has_sub_criteria=std_data.get("has_sub_criteria", False),
                    sub_criteria_json=std_data.get("sub_criteria_json"),
                    sort_order=std_data["sort_order"],
                )
                session.add(standard)
                total_standards += 1

    session.commit()
    logger.info(f"Seeded COSMIN checklist: {len(COSMIN_BOXES)} boxes, {total_standards} standards")


async def seed_cosmin_checklist_async(async_session):
    """Async wrapper that uses sync seed inside a run_sync call."""
    from sqlalchemy import select as sa_select
    from app.models.cosmin import CosminBox as CB

    # Check if already seeded
    result = await async_session.execute(sa_select(CB))
    if result.scalars().first():
        logger.info("COSMIN checklist already seeded. Skipping.")
        return

    # For async, we add objects directly to the async session
    total_standards = 0
    for box_data in COSMIN_BOXES:
        box = CosminBox(
            box_number=box_data["box_number"],
            name=box_data["name"],
            description=box_data.get("description"),
            prerequisite=box_data.get("prerequisite"),
        )
        async_session.add(box)
        await async_session.flush()

        for sb_data in box_data["sub_boxes"]:
            sub_box = CosminSubBox(
                box_id=box.id,
                sub_box_code=sb_data["sub_box_code"],
                name=sb_data["name"],
                section_group=sb_data.get("section_group"),
                sort_order=sb_data["sort_order"],
            )
            async_session.add(sub_box)
            await async_session.flush()

            for std_data in sb_data["standards"]:
                standard = CosminStandard(
                    sub_box_id=sub_box.id,
                    standard_number=std_data["standard_number"],
                    question_text=std_data["question_text"],
                    section_group=std_data.get("section_group"),
                    rating_very_good=std_data.get("rating_very_good"),
                    rating_adequate=std_data.get("rating_adequate"),
                    rating_doubtful=std_data.get("rating_doubtful"),
                    rating_inadequate=std_data.get("rating_inadequate"),
                    na_allowed=std_data.get("na_allowed", False),
                    has_sub_criteria=std_data.get("has_sub_criteria", False),
                    sub_criteria_json=std_data.get("sub_criteria_json"),
                    sort_order=std_data["sort_order"],
                )
                async_session.add(standard)
                total_standards += 1

    await async_session.commit()
    logger.info(f"Seeded COSMIN checklist: {len(COSMIN_BOXES)} boxes, {total_standards} standards")
