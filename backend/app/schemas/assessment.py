from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class EvidenceOut(BaseModel):
    id: UUID
    evidence_text: str
    page_number: int | None
    char_start: int | None
    char_end: int | None
    relevance_score: float | None
    source: str

    model_config = {"from_attributes": True}


class StandardRatingOut(BaseModel):
    id: UUID
    standard_id: int
    ai_rating: str | None
    ai_confidence: float | None
    ai_reasoning: str | None
    reviewer1_rating: str | None
    reviewer1_notes: str | None
    reviewer2_rating: str | None
    reviewer2_notes: str | None
    final_rating: str | None
    final_notes: str | None
    is_skipped: bool
    evidence: list[EvidenceOut] = []

    model_config = {"from_attributes": True}


class BoxRatingOut(BaseModel):
    id: UUID
    box_id: int
    sub_box_id: int | None
    ai_worst_score: str | None
    final_worst_score: str | None

    model_config = {"from_attributes": True}


class AssessmentOut(BaseModel):
    id: UUID
    paper_id: UUID
    status: str
    relevant_boxes: dict | None
    ai_started_at: datetime | None
    ai_completed_at: datetime | None
    standard_ratings: list[StandardRatingOut] = []
    box_ratings: list[BoxRatingOut] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class RatingUpdate(BaseModel):
    reviewer1_rating: str | None = None
    reviewer1_notes: str | None = None
    reviewer2_rating: str | None = None
    reviewer2_notes: str | None = None
    final_rating: str | None = None
    final_notes: str | None = None
