import uuid
from datetime import datetime

from sqlalchemy import String, Text, Float, Integer, Boolean, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PaperAssessment(Base):
    __tablename__ = "paper_assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    relevant_boxes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ai_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    paper = relationship("Paper", back_populates="assessment")
    standard_ratings = relationship("StandardRating", back_populates="assessment", cascade="all, delete-orphan")
    box_ratings = relationship("BoxRating", back_populates="assessment", cascade="all, delete-orphan")


class StandardRating(Base):
    __tablename__ = "standard_ratings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("paper_assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    standard_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # AI output
    ai_rating: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Reviewer 1
    reviewer1_rating: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reviewer1_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer1_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Reviewer 2
    reviewer2_rating: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reviewer2_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer2_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Final consensus
    final_rating: Mapped[str | None] = mapped_column(String(20), nullable=True)
    final_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    assessment = relationship("PaperAssessment", back_populates="standard_ratings")
    evidence = relationship("RatingEvidence", back_populates="rating", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("assessment_id", "standard_id"),
    )


class RatingEvidence(Base):
    __tablename__ = "rating_evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rating_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("standard_ratings.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="ai")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    rating = relationship("StandardRating", back_populates="evidence")


class BoxRating(Base):
    __tablename__ = "box_ratings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("paper_assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    box_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sub_box_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_worst_score: Mapped[str | None] = mapped_column(String(20), nullable=True)
    final_worst_score: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    assessment = relationship("PaperAssessment", back_populates="box_ratings")

    __table_args__ = (
        UniqueConstraint("assessment_id", "box_id", "sub_box_id"),
    )
